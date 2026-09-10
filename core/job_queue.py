import json
import logging
import threading
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Job:
    def __init__(self, job_id: str, repo_name: str, source_type: str, source: str,
                 doc_type: str = "both"):
        self.job_id = job_id
        self.repo_name = repo_name
        self.source_type = source_type  # "upload", "github"
        self.source = source
        self.doc_type = doc_type  # "both", "dev", or "user"
        self.status = JobStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.progress = 0
        self.current_step = "Queued"
        self.analysis = {}
        self.error = None
        self.results = {}

    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "repo_name": self.repo_name,
            "source_type": self.source_type,
            "source": self.source,
            "doc_type": self.doc_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "current_step": self.current_step,
            "analysis": self.analysis,
            "error": self.error,
            "results": self.results
        }

class JobQueue:
    def __init__(self, storage_dir: str = "./data/jobs", upload_dir: str = "./data/uploads"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, Job] = {}
        # Guards self.jobs: the background worker thread now mutates it (via
        # update_job) once per generated section/file — far more often than
        # before — while the Streamlit UI thread concurrently reads it via
        # list_jobs()'s auto-refresh. Without this, a create_job/delete_job
        # resizing the dict mid-iteration in the other thread could raise
        # "dictionary changed size during iteration".
        self._lock = threading.Lock()
        self._load_jobs()

    def create_job(self, repo_name: str, source_type: str, source,
                   doc_type: str = "both") -> Job:
        """Create a new analysis job.

        `source` is a GitHub URL string for source_type="github", or the
        raw {filename: content} dict for source_type="upload" — the latter
        gets written to a sidecar file under upload_dir rather than
        embedded in the job's own status JSON (which update_job() rewrites
        on every progress tick — now once per generated section/file, so
        keeping a large source blob there would mean rewriting it dozens
        of times per job). job.source becomes that sidecar file's path.
        """
        job_id = str(uuid.uuid4())[:8]
        if source_type == "upload":
            sidecar_path = self.upload_dir / f"{job_id}_source.json"
            sidecar_path.write_text(json.dumps(source))
            source_ref = str(sidecar_path)
        else:
            source_ref = source
        job = Job(job_id, repo_name, source_type, source_ref, doc_type=doc_type)
        with self._lock:
            self.jobs[job_id] = job
        self._save_job(job)
        logger.info(f"Created job {job_id} for {repo_name}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve job by ID."""
        with self._lock:
            return self.jobs.get(job_id)

    def update_job(self, job_id: str, status: JobStatus = None, progress: int = None,
                   analysis: Dict = None, error: str = None, current_step: str = None):
        """Update job status and progress."""
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return

            if status:
                job.status = status
                if status == JobStatus.RUNNING and not job.started_at:
                    job.started_at = datetime.now().isoformat()
                elif status == JobStatus.COMPLETED:
                    job.completed_at = datetime.now().isoformat()

            if progress is not None:
                job.progress = progress

            if analysis:
                job.analysis = analysis

            if error:
                job.error = error

            if current_step is not None:
                job.current_step = current_step

        self._save_job(job)

    def delete_job(self, job_id: str) -> bool:
        """Remove a job record, its persisted JSON file, and (for uploads)
        its sidecar source file. Does not touch any generated output files
        — see DocumentationGenerator.delete_output."""
        with self._lock:
            job = self.jobs.pop(job_id, None)
        if job is None:
            return False
        if job.source_type == "upload":
            sidecar_path = Path(job.source)
            if sidecar_path.exists():
                sidecar_path.unlink()
        job_file = self.storage_dir / f"{job_id}.json"
        if job_file.exists():
            job_file.unlink()
        logger.info(f"Deleted job {job_id}")
        return True

    def list_jobs(self, repo_name: str = None) -> List[Job]:
        """List all jobs, optionally filtered by repo."""
        with self._lock:
            jobs = list(self.jobs.values())
        if repo_name:
            jobs = [j for j in jobs if j.repo_name == repo_name]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def _save_job(self, job: Job):
        """Persist job to disk."""
        job_file = self.storage_dir / f"{job.job_id}.json"
        job_file.write_text(json.dumps(job.to_dict(), indent=2))

    def _load_jobs(self):
        """Load all persisted jobs."""
        for job_file in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(job_file.read_text())
                job = Job(data["job_id"], data["repo_name"],
                         data["source_type"], data["source"],
                         doc_type=data.get("doc_type", "both"))
                job.status = JobStatus(data["status"])
                job.created_at = data["created_at"]
                job.started_at = data.get("started_at")
                job.completed_at = data.get("completed_at")
                job.progress = data.get("progress", 0)
                job.current_step = data.get("current_step", "")
                job.analysis = data.get("analysis", {})
                job.error = data.get("error")
                job.results = data.get("results", {})
                self.jobs[job.job_id] = job
            except Exception as e:
                logger.error(f"Failed to load job {job_file}: {e}")
