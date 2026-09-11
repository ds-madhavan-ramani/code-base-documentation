import re
from pathlib import Path
from typing import Dict
import logging

from core import repo_map

logger = logging.getLogger(__name__)

class CodeParser:
    PATTERNS = {
        "py": {
            "imports": r"^(?:import|from)\s+([a-zA-Z0-9_\.]+)",
            "functions": r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            "classes": r"^class\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        },
        "js": {
            "imports": r"(?:import|require)\s+(?:.*?from\s+)?['\"]([^'\"]+)['\"]",
            "functions": r"(?:function|const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*[=\(]",
            "classes": r"class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)",
        },
        "java": {
            "imports": r"import\s+([a-zA-Z0-9\.]+);",
            "functions": r"(?:public|private|protected)?\s*(?:static)?\s*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            "classes": r"(?:public|private)?\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        },
    }

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def parse_directory(self) -> Dict[str, str]:
        """Read all code files from directory."""
        code_files = {}
        extensions = {".py", ".js", ".ts", ".java", ".cpp", ".go", ".rs", ".tsx", ".jsx"}
        ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}

        for file_path in self.root_dir.rglob("*"):
            if any(ignore in file_path.parts for ignore in ignore_dirs):
                continue
            if file_path.suffix not in extensions:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(file_path.relative_to(self.root_dir))
                code_files[rel_path] = content[:10000]  # Limit to 10K chars
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")

        return code_files

    def extract_structure(self, code: str, language: str) -> Dict:
        """Extract imports, functions, classes from code."""
        if language not in self.PATTERNS:
            return {"imports": [], "functions": [], "classes": []}

        patterns = self.PATTERNS[language]
        structure = {}

        for key, pattern in patterns.items():
            matches = re.findall(pattern, code, re.MULTILINE)
            structure[key] = matches

        return structure

    def get_language_from_extension(self, filename: str) -> str:
        """Map file extension to language."""
        ext_map = {
            ".py": "py", ".js": "js", ".ts": "js", ".tsx": "js", ".jsx": "js",
            ".java": "java", ".cpp": "cpp", ".c": "cpp", ".go": "go", ".rs": "rs",
        }
        ext = Path(filename).suffix
        return ext_map.get(ext, "txt")

    def build_file_structures(self, code_files: Dict[str, str]) -> Dict[str, Dict]:
        """Real functions/classes/imports (+ calls, for repo_map ranking)
        for every file — deterministic ground truth documentation
        generation can cite directly instead of inventing function names.

        Tree-sitter AST parsing (core/repo_map.py) is used for languages it
        has a tag query for (Python, JS/TS/TSX, Java) — it correctly
        handles multi-line signatures, decorators, and nested classes that
        defeat single-line regexes. Anything else falls back to the older
        regex patterns below, which is exactly this method's prior
        behavior for those languages (no regression, just no upgrade).
        """
        structures = {}
        for filename, content in code_files.items():
            if Path(filename).suffix in repo_map.EXTENSION_TO_TS_LANGUAGE:
                structures[filename] = repo_map.extract_tags(filename, content)
            else:
                lang = self.get_language_from_extension(filename)
                structures[filename] = self.extract_structure(content, lang)
                structures[filename].setdefault("calls", [])
        return structures

    def create_file_tree(self, max_depth: int = 3) -> str:
        """Generate file tree structure."""
        tree_lines = []
        ignore_dirs = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}

        def walk(path, prefix="", depth=0):
            if depth > max_depth:
                return
            try:
                items = sorted(path.iterdir())
            except PermissionError:
                return

            dirs = [p for p in items if p.is_dir() and p.name not in ignore_dirs]
            files = [p for p in items if p.is_file() and p.suffix in {
                ".py", ".js", ".ts", ".java", ".cpp", ".go", ".rs", ".md", ".txt"
            }]

            for f in files:
                tree_lines.append(f"{prefix}├─ {f.name}")

            for d in dirs[:5]:
                tree_lines.append(f"{prefix}├─ {d.name}/")
                walk(d, prefix + "│  ", depth + 1)

        walk(self.root_dir)
        return "\n".join(tree_lines)
