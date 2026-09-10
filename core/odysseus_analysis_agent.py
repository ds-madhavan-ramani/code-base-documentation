"""Analysis agent powered by Odysseus Harness using local Ollama models.

Uses Odysseus to orchestrate deep code analysis with open-source LLMs,
keeping everything local and offline.
"""

import logging
import os
import tempfile
import json
from pathlib import Path
from typing import Dict, Optional
import sys

logger = logging.getLogger(__name__)

# Import our custom Ollama provider for Odysseus
from core.odysseus_ollama_provider import (
    health_check,
    list_available_models,
    complete,
    OLLAMA_URL,
    DEFAULT_MODEL,
)

# Dynamically inject our provider into Odysseus
import odysseus.provider as provider_module

provider_module.complete = complete
provider_module.DEFAULT_MODEL = DEFAULT_MODEL


class OdysseusAnalysisAgent:
    """Uses Odysseus Harness with Ollama models for deep code analysis."""

    def __init__(self, model: str = None, max_turns: int = None, budget_tokens: int = None):
        """
        Initialize Odysseus Analysis Agent with Ollama backend.

        Args:
            model: Ollama model name (e.g., "qwen2.5-coder:32b")
                  Defaults to ODYSSEUS_MODEL env var or qwen2.5-coder:32b
            max_turns: Cap on the agentic loop's turns. Defaults to
                  ODYSSEUS_MAX_TURNS env var, or 100 — higher means the
                  Harness can read/grep more of the repo before answering,
                  at the cost of a much longer analysis phase.
            budget_tokens: Conversation token budget before old turns get
                  compacted into a summary. Defaults to
                  ODYSSEUS_BUDGET_TOKENS env var, or 300_000 — raise this
                  alongside max_turns so a longer conversation doesn't get
                  summarized away before it's used. Also needs Ollama's own
                  num_ctx (see odysseus_ollama_provider.NUM_CTX) to be large
                  enough, or individual calls get truncated regardless.
        """
        self.model = model or DEFAULT_MODEL
        self.ollama_url = OLLAMA_URL
        self.max_turns = max_turns or int(os.environ.get("ODYSSEUS_MAX_TURNS", "100"))
        self.budget_tokens = budget_tokens or int(os.environ.get("ODYSSEUS_BUDGET_TOKENS", "300000"))
        self._verify_ollama()

    def _verify_ollama(self):
        """Verify Ollama is running and model is available."""
        if not health_check():
            raise RuntimeError(
                f"Ollama not responding at {self.ollama_url}. "
                "Start it with: ollama serve"
            )

        models = list_available_models()
        if not models:
            raise RuntimeError(
                f"No models available in Ollama at {self.ollama_url}. "
                f"Pull a model: ollama pull {self.model}"
            )

        if self.model not in models:
            logger.warning(
                f"Model '{self.model}' not found in Ollama. "
                f"Available: {models[:3]}"
            )

    def analyze_deep(self, code_files: Dict[str, str], repo_name: str) -> Dict:
        """
        Run deep code analysis using Odysseus with Ollama models.

        Args:
            code_files: Dict of {filename: content}
            repo_name: Repository name for context

        Returns:
            Analysis results with architecture, patterns, dependencies, etc.
        """
        try:
            from odysseus import Harness

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Write code files to temp directory
                for filename, content in code_files.items():
                    file_path = tmpdir_path / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content)

                # Initialize Odysseus with our Ollama provider
                harness = Harness(
                    workdir=str(tmpdir_path),
                    model=self.model,
                    budget_tokens=self.budget_tokens,
                    max_turns=self.max_turns,
                )

                # Run analysis
                prompt = self._build_analysis_prompt(repo_name, code_files)
                analysis_result = harness.run(prompt)

                # Parse results
                analysis = self._parse_analysis(
                    analysis_result, code_files, repo_name
                )
                return analysis

        except Exception as e:
            logger.error(f"Odysseus analysis failed: {e}")
            logger.info("Using lightweight fallback analysis")
            return self._lightweight_analysis(code_files, repo_name)

    def _build_analysis_prompt(
        self, repo_name: str, code_files: Dict[str, str]
    ) -> str:
        """Build analysis prompt optimized for open-source models."""
        file_summary = "\n".join(
            f"  • {name} ({len(content)} chars)"
            for name, content in list(code_files.items())[:40]
        )

        return f"""Analyze this codebase and provide structured insights.

REPOSITORY: {repo_name}
FILES: {len(code_files)} total

Sample files:
{file_summary}

You have read/grep/ls tools and up to {self.max_turns} turns available in
this workdir — use them. Before answering, actually open and read the
files that matter most (entry points, the largest/most central modules,
anything imported everywhere else), and grep for patterns across the repo
rather than guessing from filenames alone. Spend real turns exploring; a
deeper read produces a better analysis than a fast guess.

TASK: Provide a deep analysis with these sections:

1. **ARCHITECTURE**: Overall system design and layers
2. **KEY_MODULES**: Main components and responsibilities
3. **DEPENDENCIES**: External libraries and internal connections
4. **PATTERNS**: Design patterns, architectural patterns used
5. **DATA_FLOW**: How data moves through the system
6. **KEY_INSIGHTS**: Notable strengths, potential issues, technical highlights
7. **REDUCTIONIST_VIEW**: Strip away the details. In plain language, explain
   WHAT this codebase does, HOW it does it at the highest level, and WHY it
   is built this way — the simplified big picture, as if explaining it to
   someone who will never read the code.
8. **SYSTEMS_VIEW**: Explain how the pieces fit together to produce that big
   picture. Name the actual files/modules/scripts involved and trace how
   they connect and hand off to each other (calls, data, control flow) —
   the code-wise and script-wise view of the whole system.

FORMAT: Respond with valid JSON only (no markdown, no ```json``` wrapper):
{{
  "architecture": "string describing overall design",
  "key_modules": ["list", "of", "main", "modules"],
  "dependencies": ["list", "of", "dependencies"],
  "patterns": ["list", "of", "patterns"],
  "data_flow": "description of data flow",
  "key_insights": "string with key findings",
  "reductionist_view": "big-picture what/how/why in plain language",
  "systems_view": "how each file/module fits together, code-wise and script-wise"
}}

Be concise but insightful. Focus on what makes this codebase unique."""

    def _parse_analysis(
        self, result: str, code_files: Dict[str, str], repo_name: str
    ) -> Dict:
        """Parse analysis result from model."""
        analysis = {}

        try:
            # Extract JSON
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = result[start:end]
                analysis = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Could not parse JSON from analysis, using defaults")

        # Ensure all required fields with fallbacks
        return {
            "repo_name": repo_name,
            "architecture": analysis.get(
                "architecture", "Deep analysis via Odysseus + Ollama"
            ),
            "key_modules": analysis.get("key_modules", list(code_files.keys())[:10]),
            "dependencies": analysis.get("dependencies", []),
            "patterns": analysis.get("patterns", []),
            "data_flow": analysis.get("data_flow", ""),
            "key_insights": analysis.get("key_insights", ""),
            "reductionist_view": analysis.get("reductionist_view", ""),
            "systems_view": analysis.get("systems_view", ""),
            "file_tree": self._build_file_tree(code_files),
            "metrics": {
                "total_files": len(code_files),
                "total_lines": sum(len(v.split("\n")) for v in code_files.values()),
            },
            "model_used": self.model,
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
                        parts = line.split()
                        if len(parts) > 1:
                            imports.add(parts[1].split(".")[0])
                    elif line.strip().startswith("def "):
                        func_name = line.split("(")[0].replace("def ", "").strip()
                        functions.append(func_name)
                    elif line.strip().startswith("class "):
                        class_name = line.split("(")[0].replace("class ", "").strip()
                        classes.append(class_name)

        top_deps = sorted(imports)[:5]
        reductionist_view = (
            f"This codebase spans {len(code_files)} file(s) and revolves around "
            f"{', '.join(top_deps) if top_deps else 'no detected external dependencies'}. "
            f"At a glance it defines {len(classes)} class(es) and {len(functions)} "
            "function(s) that together implement its behavior. "
            "(Heuristic summary — Odysseus was unavailable for a deeper read.)"
        )
        systems_view = (
            "Key files: " + ", ".join(list(code_files.keys())[:10]) + ". "
            "File-to-file wiring (which module calls or imports which) could not "
            "be traced without Odysseus deep analysis; this fallback only lists "
            "the file inventory and top-level imports."
        )

        return {
            "repo_name": repo_name,
            "fallback": True,
            "architecture": "Lightweight fallback analysis (Odysseus unavailable)",
            "key_modules": list(code_files.keys())[:10],
            "dependencies": sorted(list(imports))[:20],
            "patterns": [],
            "functions": functions[:30],
            "classes": classes[:20],
            "reductionist_view": reductionist_view,
            "systems_view": systems_view,
            "metrics": {
                "total_files": len(code_files),
                "total_lines": sum(len(v.split("\n")) for v in code_files.values()),
            },
            "model_used": "fallback",
        }

    def generate_system_diagram(self, analysis: Dict) -> str:
        """Generate Mermaid diagram from analysis."""
        if analysis.get("fallback"):
            return "## System Architecture\n\n(Deep analysis not available)"

        modules = analysis.get("key_modules", [])
        if not modules:
            return ""

        # Build simple diagram
        diagram = "graph TD\n"
        for i, module in enumerate(modules[:5]):
            module_safe = module.replace(".", "_").replace("-", "_")
            diagram += f"  M{i}[{module}]\n"

        # Add connections
        for i in range(len(modules[:5]) - 1):
            diagram += f"  M{i} --> M{i+1}\n"

        return f"```mermaid\n{diagram}\n```"


def get_available_models() -> list[str]:
    """Get list of available Ollama models."""
    return list_available_models()


def check_ollama_health() -> bool:
    """Check if Ollama is running and healthy."""
    return health_check()
