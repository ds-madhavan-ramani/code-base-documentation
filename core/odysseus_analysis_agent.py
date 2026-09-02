"""Analysis agent powered by Odysseus Harness for deep code understanding."""

import logging
import tempfile
import json
from pathlib import Path
from typing import Dict, Optional
from odysseus import Harness

logger = logging.getLogger(__name__)


class OdysseusAnalysisAgent:
    """Uses Odysseus Harness to perform deep code analysis."""

    def __init__(self, model: str = "claude-opus-4-1"):
        """
        Initialize Odysseus Analysis Agent.

        Args:
            model: Claude model to use (Odysseus will use ODYSSEUS_MODEL env var by default)
        """
        self.model = model
        self.harness = None

    def _init_harness(self, workdir: str) -> Harness:
        """Initialize Odysseus harness for analysis."""
        if self.harness is None:
            self.harness = Harness(
                workdir=workdir,
                model=self.model,
                budget_tokens=200_000,  # Generous budget for analysis
                max_turns=50,
            )
        return self.harness

    def analyze_deep(
        self, code_files: Dict[str, str], repo_name: str
    ) -> Dict:
        """
        Run deep code analysis using Odysseus Harness.

        Args:
            code_files: Dict of {filename: content}
            repo_name: Repository name for context

        Returns:
            Analysis results with architecture, patterns, dependencies, etc.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Write code files to temp directory for Odysseus to analyze
            for filename, content in code_files.items():
                file_path = tmpdir_path / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)

            try:
                harness = self._init_harness(str(tmpdir_path))

                # Use Odysseus to analyze the codebase
                prompt = self._build_analysis_prompt(repo_name, code_files)
                analysis_result = harness.run(prompt)

                # Parse the analysis result
                analysis = self._parse_analysis(
                    analysis_result, code_files, repo_name
                )
                return analysis

            except Exception as e:
                logger.error(f"Odysseus analysis failed: {e}")
                return self._lightweight_analysis(code_files, repo_name)

    def _build_analysis_prompt(
        self, repo_name: str, code_files: Dict[str, str]
    ) -> str:
        """Build analysis prompt for Odysseus."""
        file_summary = "\n".join(
            f"- {name} ({len(content)} chars)"
            for name, content in list(code_files.items())[:20]
        )

        return f"""Analyze this codebase and provide deep insights:

Repository: {repo_name}

Files ({len(code_files)} total):
{file_summary}

Please analyze and provide:
1. **Architecture**: Overall system design and structure
2. **Key Components**: Main modules, classes, and functions
3. **Dependencies**: External and internal dependencies
4. **Patterns**: Design patterns and architectural patterns used
5. **Data Flow**: How data flows through the system
6. **Key Insights**: Notable patterns, potential issues, strengths

Format your response as JSON with these exact keys:
- architecture (string)
- key_modules (list of strings)
- dependencies (list of strings)
- patterns (list of strings)
- data_flow (string)
- key_insights (string)
- file_tree (string)

Start with {{{{ and end with }}}} for valid JSON parsing."""

    def _parse_analysis(
        self, result: str, code_files: Dict[str, str], repo_name: str
    ) -> Dict:
        """Parse Odysseus analysis result."""
        try:
            # Extract JSON from result
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = result[start:end]
                analysis = json.loads(json_str)
            else:
                analysis = {}
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse JSON from analysis, using fallback")
            analysis = {}

        # Ensure required fields
        return {
            "repo_name": repo_name,
            "architecture": analysis.get(
                "architecture", "Analysis from Odysseus Harness"
            ),
            "key_modules": analysis.get("key_modules", list(code_files.keys())[:10]),
            "dependencies": analysis.get("dependencies", []),
            "patterns": analysis.get("patterns", []),
            "data_flow": analysis.get("data_flow", ""),
            "key_insights": analysis.get("key_insights", ""),
            "file_tree": analysis.get("file_tree", self._build_file_tree(code_files)),
            "metrics": {
                "total_files": len(code_files),
                "total_lines": sum(len(v.split("\n")) for v in code_files.values()),
            },
            "fallback": False,
        }

    def _build_file_tree(self, code_files: Dict[str, str]) -> str:
        """Build a simple file tree representation."""
        return "\n".join(f"  {name}" for name in sorted(code_files.keys())[:20])

    def _lightweight_analysis(self, code_files: Dict[str, str], repo_name: str) -> Dict:
        """Fallback analysis when Odysseus unavailable."""
        imports = set()
        functions = []
        classes = []

        for filename, content in code_files.items():
            if filename.endswith(".py"):
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
            "patterns": [],
            "functions": functions[:30],
            "classes": classes[:20],
            "metrics": {
                "total_files": len(code_files),
                "total_lines": sum(len(v.split("\n")) for v in code_files.values()),
            },
        }

    def generate_system_diagram(self, analysis: Dict) -> str:
        """Generate Mermaid system diagram from analysis."""
        if analysis.get("fallback"):
            return "## System Architecture\n\n(Deep analysis not available)"

        # Build a simple diagram from architecture description
        modules = analysis.get("key_modules", [])
        if not modules:
            return ""

        diagram = "graph TD\n"
        for i, module in enumerate(modules[:5]):
            diagram += f"  M{i}[{module}]\n"

        # Add simple connections
        for i in range(len(modules[:5]) - 1):
            diagram += f"  M{i} --> M{i+1}\n"

        return f"```mermaid\n{diagram}\n```"
