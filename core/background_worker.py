import logging
import threading
import time
import json
from typing import Optional, Dict
from pathlib import Path

from core.job_queue import JobQueue, JobStatus
from core.odysseus_analysis_agent import OdysseusAnalysisAgent
from core.github_client import GitHubClient
from core.code_parser import CodeParser
from core.ollama_client import OllamaClient
from core.doc_generator import DocumentationGenerator
from utils.prompts import (
    DEV_DOCS_SECTIONS,
    USER_DOCS_SECTIONS,
    build_doc_context,
    build_sectioned_doc,
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
                # For uploads, code_files should be provided in job.source
                code_files = json.loads(job.source)

            # Step 2: Deep analysis with Odysseus Harness
            self.job_queue.update_job(job.job_id, progress=10,
                                       current_step="Running deep analysis with Odysseus...")
            logger.info(f"Running deep analysis for {job.job_id}...")
            analysis = self.odysseus.analyze_deep(code_files, job.repo_name)
            self.job_queue.update_job(job.job_id, analysis=analysis, progress=35,
                                       current_step="Generating system diagram...")

            # Step 3: Generate system diagram
            diagram = self.odysseus.generate_system_diagram(analysis)
            analysis["system_diagram"] = diagram

            # Step 4: Generate documentation, section by section, respecting doc_type
            logger.info(f"Generating documentation for {job.job_id}...")
            want_dev = job.doc_type in ("both", "dev")
            want_user = job.doc_type in ("both", "user")
            sections_total = (len(DEV_DOCS_SECTIONS) if want_dev else 0) + \
                              (len(USER_DOCS_SECTIONS) if want_user else 0)
            done = {"n": 0}

            def report(label, index, total, title):
                done["n"] += 1
                pct = 35 + int(55 * done["n"] / sections_total) if sections_total else 90
                self.job_queue.update_job(
                    job.job_id, progress=pct,
                    current_step=f"{label} — section {index}/{total}: {title}"
                )

            context = build_doc_context(analysis)
            dev_docs = self._generate_dev_docs(
                context, lambda i, t, title: report("Developer docs", i, t, title)
            ) if want_dev else None
            user_docs = self._generate_user_docs(
                context, lambda i, t, title: report("User guide", i, t, title)
            ) if want_user else None

            # Step 5: Save results
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

    def _get_github_code(self, repo_url: str) -> tuple[Optional[Dict[str, str]], Optional[str]]:
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

    def _generate_dev_docs(self, context: Dict, on_section=None) -> str:
        """Generate developer documentation from analysis context, one section at a time."""
        try:
            body = build_sectioned_doc(
                self.ollama, self.dev_model, DEV_DOCS_SECTIONS, context,
                context_length=8192, on_section=on_section
            )
            return f"# Developer Documentation: {context['repo_name']}\n\n{body}"
        except Exception as e:
            logger.error(f"Dev docs generation failed: {e}")
            return f"# Developer Documentation\n\nGeneration failed: {e}"

    def _generate_user_docs(self, context: Dict, on_section=None) -> str:
        """Generate user guide from analysis context, one section at a time."""
        try:
            body = build_sectioned_doc(
                self.ollama, self.user_model, USER_DOCS_SECTIONS, context,
                context_length=4096, on_section=on_section
            )
            return f"# User Guide: {context['repo_name']}\n\n{body}"
        except Exception as e:
            logger.error(f"User docs generation failed: {e}")
            return f"# User Guide\n\nGeneration failed: {e}"
