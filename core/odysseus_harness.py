import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional
import json
import requests

logger = logging.getLogger(__name__)

class OdysseusHarness:
    """Interface to Odysseus Harness for deep code analysis."""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.timeout = 300  # 5 minutes

    def health_check(self) -> bool:
        """Check if Odysseus Harness is available."""
        try:
            resp = requests.get(f"{self.api_url}/health", timeout=5)
            return resp.status_code == 200
        except:
            return False

    def analyze_deep(self, code_files: Dict[str, str], repo_name: str) -> Dict:
        """
        Run deep code analysis using Odysseus Harness.

        Args:
            code_files: Dict of {filename: content}
            repo_name: Repository name for context

        Returns:
            Analysis results with architecture, patterns, dependencies, etc.
        """
        if not self.health_check():
            logger.warning("Odysseus Harness unavailable, using lightweight analysis")
            return self._lightweight_analysis(code_files, repo_name)

        try:
            payload = {
                "task": "comprehensive_analysis",
                "repo_name": repo_name,
                "files": code_files,
                "analysis_type": "deep",
                "features": [
                    "architecture_patterns",
                    "dependency_graph",
                    "code_metrics",
                    "security_insights",
                    "performance_patterns"
                ]
            }

            resp = requests.post(
                f"{self.api_url}/api/analyze",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Odysseus Harness analysis failed: {e}")
            return self._lightweight_analysis(code_files, repo_name)

    def generate_system_diagram(self, analysis: Dict) -> str:
        """Generate Mermaid system diagram from analysis."""
        if not self.health_check():
            return "## System Architecture\n\n(Requires Odysseus Harness)"

        try:
            payload = {
                "task": "diagram_generation",
                "analysis": analysis,
                "format": "mermaid",
                "style": "flowchart TD"
            }

            resp = requests.post(
                f"{self.api_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json().get("diagram", "")
        except Exception as e:
            logger.error(f"Diagram generation failed: {e}")
            return ""

    def _lightweight_analysis(self, code_files: Dict[str, str], repo_name: str) -> Dict:
        """Fallback analysis when Odysseus unavailable."""
        imports = set()
        functions = []
        classes = []

        for filename, content in code_files.items():
            if filename.endswith(".py"):
                # Quick Python analysis
                for line in content.split("\n"):
                    if line.startswith("import ") or line.startswith("from "):
                        imports.add(line.split()[1].split(".")[0])
                    elif line.strip().startswith("def "):
                        func_name = line.split("(")[0].replace("def ", "").strip()
                        functions.append(func_name)
                    elif line.strip().startswith("class "):
                        class_name = line.split("(")[0].replace("class ", "").strip()
                        classes.append(class_name)

        return {
            "repo_name": repo_name,
            "fallback": True,
            "architecture": "Lightweight analysis (Odysseus unavailable)",
            "key_modules": list(code_files.keys())[:10],
            "dependencies": sorted(list(imports))[:20],
            "functions": functions[:30],
            "classes": classes[:20],
            "patterns": [],
            "metrics": {
                "total_files": len(code_files),
                "total_lines": sum(len(v.split("\n")) for v in code_files.values())
            }
        }

    def batch_analyze(self, codebases: Dict[str, Dict[str, str]]) -> Dict[str, Dict]:
        """Analyze multiple codebases in one call."""
        results = {}
        for repo_name, code_files in codebases.items():
            results[repo_name] = self.analyze_deep(code_files, repo_name)
        return results
