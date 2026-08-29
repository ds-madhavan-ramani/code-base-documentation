import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class OdysseusClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.timeout = 120

    def health_check(self) -> bool:
        """Verify Odysseus is running."""
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except:
            return False

    def analyze_codebase(self, code_files: Dict[str, str], max_retries: int = 1) -> Dict:
        """Send code for deep analysis. Falls back if Odysseus unavailable."""
        if not self.health_check():
            logger.warning("Odysseus unavailable, using fallback analysis")
            return self._fallback_analysis(code_files)

        payload = {
            "task": "code_analysis",
            "files": code_files,
            "depth": "comprehensive"
        }

        try:
            resp = self.session.post(
                f"{self.base_url}/api/analyze",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Odysseus analysis failed: {e}, using fallback")
            return self._fallback_analysis(code_files)

    def _fallback_analysis(self, code_files: Dict[str, str]) -> Dict:
        """Fallback when Odysseus unavailable."""
        return {
            "architecture": "Analysis unavailable - Odysseus not responding",
            "key_modules": list(code_files.keys())[:5],
            "dependencies": [],
            "patterns": [],
            "fallback": True
        }

    def generate_architecture_diagram(self, analysis: Dict) -> str:
        """Generate Mermaid diagram from analysis."""
        if not self.health_check() or analysis.get("fallback"):
            return "## Architecture Diagram\n\n(Requires Odysseus running)"

        try:
            payload = {
                "task": "diagram_generation",
                "analysis": analysis,
                "format": "mermaid"
            }
            resp = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            return resp.json().get("diagram", "")
        except Exception as e:
            logger.error(f"Diagram generation failed: {e}")
            return ""
