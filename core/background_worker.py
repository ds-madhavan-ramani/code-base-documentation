import logging
import threading
import time
import json
from typing import Optional, Dict, List
from pathlib import Path

from core.job_queue import JobQueue, JobStatus
from core.odysseus_analysis_agent import OdysseusAnalysisAgent
from core.github_client import GitHubClient
from core.code_parser import CodeParser
from core.ollama_client import OllamaClient
from core.doc_generator import DocumentationGenerator
from utils.prompts import (
    DEV_DOCS_TIER1_SECTIONS,
    DEV_DOCS_TAIL_SECTIONS,
    USER_DOCS_HEAD_SECTIONS,
    USER_DOCS_TAIL_SECTIONS,
    build_doc_context,
    build_sectioned_doc,
    build_repo_structure_section,
    select_significant_files,
    identify_features,
    build_feature_map_section,
    build_file_walkthrough_sections,
    build_user_feature_sections,
)

logger = logging.getLogger(__name__)

class BackgroundWorker:
    """Process analysis jobs in background thread."""

    def __init__(self, job_queue: JobQueue, odysseus: OdysseusAnalysisAgent,
                 ollama: OllamaClient, doc_gen: DocumentationGenerator,
                 dev_model: str = "qwen2.5-coder:7b", user_model: str = "qwen2.5-coder:7b"):
        self.job_queue = job_queue
        self.odysseus = odysseus
        self.ollama = ollama
        self.doc_gen = doc_gen
        self.github = GitHubClient()
        self.github.cleanup_cache()  # advertised as "Auto-cleanup of old caches" but was never called
        self.dev_model = dev_model
        self.user_model = user_model
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """Start background worker thread."""
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        logger.info("Background worker started")

    def stop(self):
        """Stop background worker thread."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Background worker stopped")

    def _worker_loop(self):
        """Main worker loop - processes pending jobs."""
        while self.is_running:
            try:
                pending_jobs = self.job_queue.list_jobs()
                pending_jobs = [j for j in pending_jobs if j.status == JobStatus.PENDING]

                for job in pending_jobs:
                    self._process_job(job)

                time.sleep(5)  # Check for new jobs every 5 seconds
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(10)

    def _process_job(self, job):
        """Process a single analysis job."""
        try:
            self.job_queue.update_job(job.job_id, status=JobStatus.RUNNING, progress=0,
                                       current_step="Starting analysis...")

            # Step 1: Get code files
            if job.source_type == "github":
                self.job_queue.update_job(job.job_id, current_step="Cloning repository...")
                code_files, error = self._get_github_code(job.source)
                if error:
                    self.job_queue.update_job(job.job_id, status=JobStatus.FAILED,
                                               error=error, current_step=f"Failed: {error}")
                    return
            else:
                # For uploads, job.source is a path to a sidecar JSON file
                # (see JobQueue.create_job) holding the {filename: content}
                # dict — kept out of the job's own status JSON so it isn't
                # rewritten on every progress update.
                code_files = json.loads(Path(job.source).read_text())

            # Step 2: Real, regex-extracted per-file structure (ground truth
            # the doc-writing model can cite instead of guessing).
            file_structures = CodeParser(".").build_file_structures(code_files)

            # Step 3: Deep analysis with Odysseus Harness
            self.job_queue.update_job(job.job_id, progress=10,
                                       current_step="Running deep analysis with Odysseus...")
            logger.info(f"Running deep analysis for {job.job_id}...")
            analysis = self.odysseus.analyze_deep(code_files, job.repo_name, user_context=job.user_context)
            self.job_queue.update_job(job.job_id, analysis=analysis, progress=25,
                                       current_step="Generating system diagram...")

            diagram = self.odysseus.generate_system_diagram(analysis)
            analysis["system_diagram"] = diagram

            repo_url = job.source if job.source_type == "github" else None
            context = build_doc_context(analysis, repo_url=repo_url)
            significant_files = select_significant_files(
                code_files, file_structures, key_modules=analysis.get("key_modules")
            )

            # Step 4: Identify real features once, shared by both documents,
            # grounded only in the real files/functions above.
            self.job_queue.update_job(job.job_id, progress=30, current_step="Identifying real features...")
            features = identify_features(self.ollama, self.dev_model, context, significant_files, file_structures)

            # Step 5: Generate documentation, section by section, respecting doc_type
            logger.info(f"Generating documentation for {job.job_id}...")
            want_dev = job.doc_type in ("both", "dev")
            want_user = job.doc_type in ("both", "user")

            sections_total = 0
            if want_dev:
                sections_total += 1 + len(DEV_DOCS_TIER1_SECTIONS) + 1 + len(significant_files) + len(DEV_DOCS_TAIL_SECTIONS)
            if want_user:
                sections_total += len(USER_DOCS_HEAD_SECTIONS) + len(features) + len(USER_DOCS_TAIL_SECTIONS)
            done = {"n": 0}

            def report(label, index, total, title):
                done["n"] += 1
                pct = 30 + int(60 * done["n"] / sections_total) if sections_total else 90
                self.job_queue.update_job(
                    job.job_id, progress=pct,
                    current_step=f"{label} — {index}/{total}: {title}"
                )

            dev_docs = self._generate_dev_docs(
                context, code_files, file_structures, significant_files, features,
                lambda label, i, t, title: report(label, i, t, title)
            ) if want_dev else None
            user_docs = self._generate_user_docs(
                context, features,
                lambda label, i, t, title: report(label, i, t, title)
            ) if want_user else None

            # Step 6: Save results
            self.job_queue.update_job(job.job_id, progress=95, current_step="Saving documentation...")
            self.doc_gen.save_documentation(job.repo_name, dev_docs, user_docs, analysis)

            self.job_queue.update_job(
                job.job_id,
                status=JobStatus.COMPLETED,
                progress=100,
                analysis=analysis,
                current_step="Completed"
            )

            logger.info(f"Job {job.job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            self.job_queue.update_job(job.job_id, status=JobStatus.FAILED,
                                    error=str(e), current_step=f"Failed: {e}")

    def _get_github_code(self, repo_url: str) -> tuple:
        """Clone GitHub repo and extract code files."""
        repo_path, error = self.github.clone_repository(repo_url)
        if error:
            return None, error

        try:
            parser = CodeParser(repo_path)
            code_files = parser.parse_directory()
            return code_files, None
        except Exception as e:
            return None, f"Failed to parse repository: {str(e)}"

    def _generate_dev_docs(self, context: Dict, code_files: Dict[str, str],
                            file_structures: Dict[str, dict], significant_files: List[str],
                            features: List[Dict], on_step=None) -> str:
        """Developer Docs: high-level flow, then feature->file map, then a
        grounded per-file walkthrough, then setup/troubleshooting."""
        try:
            if on_step:
                on_step("Developer docs", 1, 1, "Repository Structure")
            repo_structure = build_repo_structure_section(
                self.ollama, self.dev_model, context, code_files, file_structures, significant_files,
                context_length=8192,
            )
            tier1 = build_sectioned_doc(
                self.ollama, self.dev_model, DEV_DOCS_TIER1_SECTIONS, context, context_length=8192,
                on_section=lambda i, t, title: on_step and on_step("Developer docs", i, t, title)
            )
            feature_map = build_feature_map_section(self.ollama, self.dev_model, context, features, context_length=8192)
            if on_step:
                on_step("Developer docs", 1, 1, "Feature -> File Map")

            walkthroughs = build_file_walkthrough_sections(
                self.ollama, self.dev_model, code_files, file_structures, significant_files, context,
                context_length=8192,
                on_file=lambda i, t, filename: on_step and on_step("Developer docs — file walkthrough", i, t, filename)
            )
            tail = build_sectioned_doc(
                self.ollama, self.dev_model, DEV_DOCS_TAIL_SECTIONS, context, context_length=8192,
                on_section=lambda i, t, title: on_step and on_step("Developer docs", i, t, title)
            )
            body = "\n\n".join([
                "## Repository Structure\n\n" + repo_structure,
                tier1,
                "## Feature → File Map\n\n" + feature_map,
                "## Per-File Code Walkthrough\n\n" + walkthroughs,
                tail,
            ])
            return f"# Developer Documentation: {context['repo_name']}\n\n{body}"
        except Exception as e:
            logger.error(f"Dev docs generation failed: {e}")
            return f"# Developer Documentation\n\nGeneration failed: {e}"

    def _generate_user_docs(self, context: Dict, features: List[Dict], on_step=None) -> str:
        """User Guide: big picture, install, then usage-level per-feature
        sections grounded in the same feature list as the dev docs, then FAQ."""
        try:
            head = build_sectioned_doc(
                self.ollama, self.user_model, USER_DOCS_HEAD_SECTIONS, context, context_length=4096,
                on_section=lambda i, t, title: on_step and on_step("User guide", i, t, title)
            )
            feature_sections = build_user_feature_sections(
                self.ollama, self.user_model, context, features, context_length=4096,
                on_feature=lambda i, t, name: on_step and on_step("User guide — feature", i, t, name)
            )
            tail = build_sectioned_doc(
                self.ollama, self.user_model, USER_DOCS_TAIL_SECTIONS, context, context_length=4096,
                on_section=lambda i, t, title: on_step and on_step("User guide", i, t, title)
            )
            body = "\n\n".join([
                head,
                "## Features & How to Use Them\n\n" + feature_sections,
                tail,
            ])
            return f"# User Guide: {context['repo_name']}\n\n{body}"
        except Exception as e:
            logger.error(f"User docs generation failed: {e}")
            return f"# User Guide\n\nGeneration failed: {e}"
