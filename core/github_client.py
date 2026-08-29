import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Tuple
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
                logger.info(f"Repository already cached: {repo_name}")
                return local_path, None

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

    def get_repo_info(self, repo_path: Path) -> Dict:
        """Extract metadata about repository."""
        try:
            repo_name = repo_path.name

            # Get git info
            git_cmd = ["git", "-C", str(repo_path), "log", "-1", "--format=%ci"]
            result = subprocess.run(git_cmd, capture_output=True, text=True)
            last_commit = result.stdout.strip() if result.returncode == 0 else "unknown"

            # Count commits
            git_cmd = ["git", "-C", str(repo_path), "rev-list", "--count", "HEAD"]
            result = subprocess.run(git_cmd, capture_output=True, text=True)
            commit_count = result.stdout.strip() if result.returncode == 0 else "0"

            # Get branches
            git_cmd = ["git", "-C", str(repo_path), "branch", "-r"]
            result = subprocess.run(git_cmd, capture_output=True, text=True)
            branches = len(result.stdout.strip().split("\n")) if result.returncode == 0 else 0

            return {
                "name": repo_name,
                "last_commit": last_commit,
                "commit_count": commit_count,
                "branches": branches,
                "path": str(repo_path)
            }
        except Exception as e:
            logger.error(f"Failed to get repo info: {e}")
            return {"name": repo_path.name, "error": str(e)}

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

    def is_github_url(self, url: str) -> bool:
        """Check if URL is a GitHub repository."""
        return "github.com" in url.lower() or (
            "/" in url and not url.startswith("http") and "." not in url.split("/")[0]
        )
