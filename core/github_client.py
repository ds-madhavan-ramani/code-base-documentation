import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class GitHubClient:
    """Clone and extract code from GitHub repositories."""

    def __init__(self, cache_dir: str = "./data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def clone_repository(self, repo_url: str) -> Tuple[Optional[Path], Optional[str]]:
        """
        Clone GitHub repository to cache.

        Args:
            repo_url: GitHub URL (https://github.com/user/repo or user/repo)

        Returns:
            (local_path, error_message)
        """
        try:
            # Parse repository name
            if repo_url.startswith("http"):
                parsed = urlparse(repo_url)
                parts = parsed.path.strip("/").split("/")
                repo_name = parts[-1].replace(".git", "")
                full_url = repo_url
            else:
                repo_name = repo_url.split("/")[-1]
                full_url = f"https://github.com/{repo_url}"

            local_path = self.cache_dir / repo_name
            if local_path.exists():
                logger.info(f"Repository cached at {local_path}, pulling latest changes...")
                pull_result = subprocess.run(
                    ["git", "-C", str(local_path), "pull", "--depth", "1", "--ff-only"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if pull_result.returncode == 0:
                    return local_path, None
                logger.warning(
                    f"git pull failed for cached repo {repo_name} ({pull_result.stderr.strip()}); "
                    "re-cloning fresh instead of analyzing a possibly-stale checkout"
                )
                shutil.rmtree(local_path, ignore_errors=True)

            logger.info(f"Cloning {full_url} to {local_path}...")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", full_url, str(local_path)],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                error = f"Git clone failed: {result.stderr}"
                logger.error(error)
                return None, error

            logger.info(f"Successfully cloned {repo_name}")
            return local_path, None

        except subprocess.TimeoutExpired:
            error = "Repository clone timed out (>120s)"
            logger.error(error)
            return None, error
        except Exception as e:
            error = f"Failed to clone repository: {str(e)}"
            logger.error(error)
            return None, error

    def cleanup_cache(self, max_age_days: int = 7):
        """Remove old cached repositories."""
        import time
        current_time = time.time()
        cutoff_time = current_time - (max_age_days * 86400)

        for repo_dir in self.cache_dir.iterdir():
            if repo_dir.is_dir():
                mod_time = repo_dir.stat().st_mtime
                if mod_time < cutoff_time:
                    logger.info(f"Cleaning up old cache: {repo_dir.name}")
                    shutil.rmtree(repo_dir, ignore_errors=True)

    @staticmethod
    def is_github_url(url: str) -> bool:
        """Check if a string looks like a GitHub reference (full URL or
        'user/repo' shorthand), so a bad submission can be rejected before
        creating a job rather than failing deep inside the background worker."""
        return "github.com" in url.lower() or (
            "/" in url and not url.startswith("http") and "." not in url.split("/")[0]
        )
