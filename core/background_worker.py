import logging
import threading
import time
import json
from typing import Optional, Dict
from pathlib import Path

from core.job_queue import JobQueue, JobStatus
from core.odysseus_harness import OdysseusHarness
from core.github_client import GitHubClient
from core.code_parser import CodeParser
from core.ollama_client import OllamaClient
from core.doc_generator import DocumentationGenerator
from utils.prompts import PROMPTS

logger = logging.getLogger(__name__)

class BackgroundWorker:
    """Process analysis jobs in background thread."""

    def __init__(self, job_queue: JobQueue, odysseus: OdysseusHarness,
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
            self.job_queue.update_job(job.job_id, status=JobStatus.RUNNING, progress=0)

            # Step 1: Get code files
            if job.source_type == "github":
                code_files, error = self._get_github_code(job.source)
                if error:
                    self.job_queue.update_job(job.job_id, status=JobStatus.FAILED,
                                            error=error)
                    return
            else:
                # For uploads, code_files should be provided in job.source
                code_files = json.loads(job.source)

            self.job_queue.update_job(job.job_id, progress=20)

            # Step 2: Deep analysis with Odysseus Harness
            logger.info(f"Running deep analysis for {job.job_id}...")
            analysis = self.odysseus.analyze_deep(code_files, job.repo_name)
            self.job_queue.update_job(job.job_id, analysis=analysis, progress=50)

            # Step 3: Generate system diagram
            diagram = self.odysseus.generate_system_diagram(analysis)
            analysis["system_diagram"] = diagram

            # Step 4: Generate documentation
            logger.info(f"Generating documentation for {job.job_id}...")
            dev_docs = self._generate_dev_docs(analysis)
            user_docs = self._generate_user_docs(analysis)

            self.job_queue.update_job(job.job_id, progress=80)

            # Step 5: Save results
            results = {
                "dev_docs": dev_docs,
                "user_docs": user_docs,
                "analysis": analysis
            }
            self.doc_gen.save_documentation(job.repo_name, dev_docs, user_docs, analysis)

            self.job_queue.update_job(
                job.job_id,
                status=JobStatus.COMPLETED,
                progress=100,
                analysis=analysis
            )

            logger.info(f"Job {job.job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            self.job_queue.update_job(job.job_id, status=JobStatus.FAILED,
                                    error=str(e))

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

    def _generate_dev_docs(self, analysis: Dict) -> str:
        """Generate developer documentation from analysis."""
        try:
            prompt = PROMPTS.get("dev_docs", "").format(
                file_tree=analysis.get("file_tree", "N/A"),
                code_structure=json.dumps(analysis.get("key_modules", []))[:2000],
                architecture=analysis.get("architecture", "")
            )

            dev_docs = self.ollama.generate(
                self.dev_model,
                prompt,
                context_length=8192
            )
            return dev_docs
        except Exception as e:
            logger.error(f"Dev docs generation failed: {e}")
            return f"# Developer Documentation\n\nGeneration failed: {e}"

    def _generate_user_docs(self, analysis: Dict) -> str:
        """Generate user guide from analysis."""
        try:
            prompt = PROMPTS.get("user_docs", "").format(
                modules=", ".join(analysis.get("key_modules", [])[:5])
            )

            user_docs = self.ollama.generate(
                self.user_model,
                prompt,
                context_length=4096
            )
            return user_docs
        except Exception as e:
            logger.error(f"User docs generation failed: {e}")
            return f"# User Guide\n\nGeneration failed: {e}"
