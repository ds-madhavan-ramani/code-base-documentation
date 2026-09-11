"""Grounded, section-by-section documentation generation.

Two lessons learned from real output produced by small local models
(qwen2.5-coder:7b / qwen3:32b via Ollama):

1. One model call per whole document runs out of depth partway through —
   so each document is built section by section (`build_sectioned_doc`),
   each section getting its own focused prompt and its own call.

2. A model asked to write about "the codebase" in the abstract, with no
   real file content in front of it, invents plausible-sounding details it
   has no way to know — a repo URL, a contact email, function signatures
   that don't exist. The fix isn't a better prompt, it's giving the model
   the real thing to describe: real file content, real regex-extracted
   function/class names (`code_parser.build_file_structures`), and the
   real repo URL, with an explicit instruction not to fill gaps with
   invented specifics.

See README.md's "Documentation Generation" section for the full flow
diagram, including the Feature -> File Map and Per-File Walkthrough tiers.
"""

import json
import logging
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

ANTI_HALLUCINATION_NOTE = (
    "Only state facts given to you above. Do not invent repository URLs, "
    "email addresses, contact details, or function/class/file names that "
    "are not explicitly given. If something isn't given, write a neutral "
    "note like \"(see this project's own repository)\" instead of making "
    "one up."
)

# How many source files get their own dedicated walkthrough call in the
# Developer Docs. Override via env var for very large or very small repos.
MAX_WALKTHROUGH_FILES = int(os.environ.get("DEV_DOCS_MAX_FILES", "12"))
MAX_CHARS_PER_WALKTHROUGH_FILE = 6000

# identify_features() only needs a short JSON call, not one call per file
# (unlike the walkthrough), so it can safely see far more candidate files
# than MAX_WALKTHROUGH_FILES. Without this, a real feature whose file
# ranks just outside the (small) walkthrough cut gets wrongly pinned to
# an unrelated file that did make the cut — e.g. an "Email Notifications"
# feature landing on a network-map file because the real email service
# file wasn't in the pool the model was choosing from.
MAX_FEATURE_CANDIDATE_FILES = int(os.environ.get("DEV_DOCS_MAX_FEATURE_FILES", "40"))

_LEADING_HEADING_RE = re.compile(r"^#{1,6}[ \t].*\n+", re.MULTILINE)
_HEADING_LINE_RE = re.compile(r"^(#{1,6})([ \t].*)$", re.MULTILINE)
_LEADING_BOLD_RE = re.compile(r"^\*\*([^\n*]+)\*\*[ \t]*\n+")


def _strip_leading_heading(text: str) -> str:
    """Models routinely restate their own title as the first line despite
    being told not to (e.g. a "# Big Picture" right before the "## Big
    Picture" heading we already add), producing visibly duplicated
    headings. Strip any heading line(s) at the very start of the text."""
    stripped = text.lstrip()
    match = _LEADING_HEADING_RE.match(stripped)
    while match:
        stripped = stripped[match.end():].lstrip()
        match = _LEADING_HEADING_RE.match(stripped)
    return stripped


def _normalize_title_text(text: str) -> str:
    text = text.strip().strip("`").rstrip(":").strip()
    text = text.replace("->", "→")
    return " ".join(text.lower().split())


def _strip_restated_bold_title(text: str, title: str) -> str:
    """Models sometimes restate their own section title as a bold
    paragraph instead of literal '#' heading syntax (which
    _strip_leading_heading already catches) — e.g. a "**How It's Put
    Together**" paragraph directly under the real heading we already add.
    Strips it only on an exact (case/punctuation-insensitive) match
    against the known title or its basename, so a legitimate short bold
    lead-in sentence is never touched."""
    match = _LEADING_BOLD_RE.match(text)
    if not match:
        return text
    candidate = _normalize_title_text(match.group(1))
    known_titles = {_normalize_title_text(title), _normalize_title_text(title.rsplit("/", 1)[-1])}
    if candidate in known_titles:
        return text[match.end():].lstrip()
    return text


def _normalize_headings(text: str, min_level: int = 3, title: Optional[str] = None) -> str:
    """Strips a restated leading title (as a heading or as a bold
    paragraph — see _strip_leading_heading/_strip_restated_bold_title),
    then clamps any OTHER heading the model added mid-body to at least
    min_level. Models routinely give internal sub-structure like "Key
    Functions" a heading level with no regard for what it's nested under
    (e.g. "## Key Functions" inside a file walkthrough already wrapped in
    "### filename"), so a sub-section visually outranks its own parent.
    Clamping (not stripping) preserves the sub-structure, just nests it
    correctly."""
    text = _strip_leading_heading(text)
    if title:
        text = _strip_restated_bold_title(text, title)

    def clamp(match: "re.Match") -> str:
        hashes, rest = match.group(1), match.group(2)
        if len(hashes) < min_level:
            hashes = "#" * min_level
        return hashes + rest

    return _HEADING_LINE_RE.sub(clamp, text)


def _safe_generate(ollama_client, model: str, prompt: str, context_length: int, label: str,
                    min_heading_level: int = 3) -> str:
    """Every model call in this module goes through here so that one failed
    call (timeout, Ollama restart, OOM) produces a visible placeholder for
    just that section/file/feature instead of an uncaught exception that
    discards every section already generated in the same document. Also
    normalizes any heading the model wrote to nest under min_heading_level
    (see _normalize_headings) — the model doesn't know how deep its output
    will be wrapped, so it can't be trusted to pick a compatible level.
    `label` doubles as the section's own display title at every call site
    in this module, so it's also used to catch a restated bold title."""
    try:
        text = ollama_client.generate(model, prompt, context_length=context_length).strip()
        return _normalize_headings(text, min_heading_level, title=label)
    except Exception as e:
        logger.error(f"Generation failed for {label}: {e}")
        return f"_(Generation failed for this section — {e})_"

# --------------------------------------------------------------------------
# Repository Structure: a real directory tree, built deterministically from
# the actual file list (zero hallucination risk on structure), annotated
# with one grounded LLM call for one-line purpose comments on files that
# matter — mapped by exact file path so a comment can never land on the
# wrong file or corrupt the tree itself.
# --------------------------------------------------------------------------

def _build_tree_lines(code_files: Dict[str, str]) -> List[tuple]:
    """Renders the real file list as `tree`-style lines. Returns
    (rendered_line, full_path) pairs — full_path is None for directory
    lines, since only files get purpose comments."""
    root: dict = {}
    for path in sorted(code_files.keys()):
        parts = path.split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None

    results = []

    def render(node: dict, prefix: str, path_prefix: str):
        entries = sorted(node.items(), key=lambda kv: (kv[1] is None, kv[0]))
        for index, (name, child) in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            is_file = child is None
            full_path = f"{path_prefix}{name}" if is_file else None
            suffix = "" if is_file else "/"
            results.append((f"{prefix}{connector}{name}{suffix}", full_path))
            if not is_file:
                extension = "    " if is_last else "│   "
                render(child, prefix + extension, f"{path_prefix}{name}/")

    render(root, "", "")
    return results


def build_repo_tree(code_files: Dict[str, str]) -> str:
    """A real, deterministic directory tree from the actual uploaded/cloned
    files — no LLM involved, so it can't drop, invent, or misplace a file."""
    return "\n".join(line for line, _ in _build_tree_lines(code_files))


def identify_repo_structure_comments(ollama_client, model: str, context: dict,
                                      significant_files: List[str], file_structures: Dict[str, dict],
                                      context_length: int = 8192) -> Dict[str, str]:
    """One grounded call: a short one-line purpose comment for each
    significant file, like an annotated `tree` listing. Grounded only in
    real function/class names — files not covered here simply get no
    comment rather than an invented one."""
    file_summary = "\n".join(
        f"- {f}: functions={file_structures.get(f, {}).get('functions', [])[:8]}, "
        f"classes={file_structures.get(f, {}).get('classes', [])[:8]}"
        for f in significant_files
    )[:4000]

    prompt = f"""Project: {context['repo_name']}
Architecture: {context['architecture']}

Real files and the real functions/classes found in them:
{file_summary}

For EACH file listed above, write a short one-line purpose comment (like
you'd see next to a file in an annotated directory tree, e.g. "Streamlit
web interface" or "Job queue management") — grounded ONLY in the real
functions/classes given for that file. Do not invent a purpose for a file
you have no real signal for.

Respond with JSON only, no markdown fence:
{{"comments": {{"exact/file/path.py": "short one-line comment", ...}}}}

{ANTI_HALLUCINATION_NOTE}"""

    raw = _safe_generate(ollama_client, model, prompt, context_length, "repo structure comments")
    try:
        start, end = raw.find("{"), raw.rfind("}") + 1
        data = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        comments = data.get("comments") or {}
        if isinstance(comments, dict):
            return {k: v for k, v in comments.items() if isinstance(v, str)}
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Could not parse repo structure comments JSON: {e}")
    return {}


def build_repo_structure_section(ollama_client, model: str, context: dict, code_files: Dict[str, str],
                                  file_structures: Dict[str, dict], significant_files: List[str],
                                  context_length: int = 8192) -> str:
    """Real directory tree (deterministic) plus short purpose comments on
    the files that matter (one grounded call, JSON-mapped by exact path so
    a comment can't land on the wrong file or corrupt the tree)."""
    lines = _build_tree_lines(code_files)
    comments = identify_repo_structure_comments(
        ollama_client, model, context, significant_files, file_structures, context_length
    )
    annotated = [
        f"{line}  # {comments[path]}" if path and path in comments else line
        for line, path in lines
    ]
    return "```\n" + "\n".join(annotated) + "\n```"


# --------------------------------------------------------------------------
# Real-code grounding for the Common Tasks section, which otherwise only
# sees a dependency-name list and architecture prose — nothing it could
# actually cite — and ends up inventing a plausible-looking parallel API
# (e.g. a fabricated `com.example.common.utils.Normalise.stripAndLowercase()`
# call contradicting the real, correctly-grounded Normalise.java walkthrough
# a few sections earlier in the very same document).
# --------------------------------------------------------------------------

_JAVA_SRC_ROOTS = ("src/main/java/", "src/main/kotlin/", "src/test/java/", "src/test/kotlin/")


def _infer_module_path(filename: str) -> Optional[str]:
    """Best-effort REAL import/module path for a file, computed
    deterministically from its actual path — never invented. Handles the
    Java/Kotlin Maven/Gradle layout (package = directory path under
    src/main/java) and Python's dotted-module convention; other languages
    (JS/TS import paths depend on bundler aliases/tsconfig we don't have)
    return None, and the prompt is told to reference the file by its real
    path instead of guessing an import statement."""
    normalized = filename.replace("\\", "/")
    for root in _JAVA_SRC_ROOTS:
        idx = normalized.find(root)
        if idx != -1:
            remainder = re.sub(r"\.(java|kt)$", "", normalized[idx + len(root):])
            return remainder.replace("/", ".")
    if normalized.endswith(".py"):
        return normalized[:-3].replace("/", ".")
    return None


def _real_code_touchpoints(file_structures: Dict[str, dict], significant_files: List[str],
                            max_files: int = 4, max_names_per_file: int = 6) -> str:
    """A short, real grounding block: exact file path, real import/module
    path (only when derivable, see _infer_module_path), and real
    function/class names — so a Common Tasks code example either uses
    something real or the prompt can tell it to describe the task in
    prose instead of inventing a parallel fictional API."""
    lines = []
    for filename in significant_files[:max_files]:
        structure = file_structures.get(filename, {})
        names = (structure.get("classes", []) + structure.get("functions", []))[:max_names_per_file]
        if not names:
            continue
        module_path = _infer_module_path(filename)
        location = f"path: {filename}" + (f", real import path: {module_path}" if module_path else "")
        lines.append(f"- {location} — real names: {', '.join(names)}")
    return "\n".join(lines) if lines else "(no real per-file signatures available for this repo)"


# --------------------------------------------------------------------------
# Tier 1: whole-document, fixed sections (grounded in the Odysseus analysis
# summary — architecture, patterns, dependencies — not per-file source).
# --------------------------------------------------------------------------

DEV_DOCS_TIER1_SECTIONS: List[Dict[str, str]] = [
    {
        "title": "Big Picture",
        "template": """Project: {repo_name}

The project's own author describes it as:
{user_context}

Big-picture summary from code analysis:
{overview}

Write the opening section of a developer guide, titled "Big Picture". In
plain, simplified language explain WHAT this codebase does, HOW it works
at the highest level, and WHY it is built this way. If the author's own
description above is given, treat it as authoritative for WHAT/WHY — don't
contradict it, use the code analysis to fill in HOW. Strip away detail,
don't list files or functions here.

Format: Markdown, 2-4 short paragraphs. Do not add a heading, one will be added.""",
    },
    {
        "title": "How It's Put Together",
        "template": """Project: {repo_name}

Notes on how the pieces fit together, from analysis:
{how_it_works}

File tree:
{file_tree}

Write a "How It's Put Together" section explaining how the pieces fit
together to produce the big picture above — name real files/modules and
trace how they connect and hand off to each other (calls, data, control
flow).

Format: Markdown. A short bullet list of file/module -> responsibility,
then 1-2 paragraphs on how they interact. Do not add a heading, one will be added.""",
    },
    {
        "title": "Architecture & Design Patterns",
        "template": """Project: {repo_name}

Architecture notes:
{architecture}

Detected patterns:
{patterns}

Data flow:
{data_flow}

External dependencies actually used by this project:
{dependencies}

Write an "Architecture & Design Patterns" section: overall design, layers,
the specific patterns in play, how data flows through the system, and how
the external dependencies above are used.

Format: Markdown, a short bullet list of patterns followed by narrative
paragraphs. Do not add a heading, one will be added.""",
    },
]

DEV_DOCS_TAIL_SECTIONS: List[Dict[str, str]] = [
    {
        "title": "Configuration, Setup & Development Workflow",
        "template": """Project: {repo_name}
Repository: {repo_url}

Dependencies: {dependencies}

Write a "Configuration, Setup & Development Workflow" section: how to get
and install this project, install these exact dependencies, configure it,
and the typical development loop (run/test/iterate).

If Repository above is a real URL, use it for a "git clone <that exact
URL>" step — never invent a different URL. If Repository above says this
was analyzed from a local upload (no hosted URL), do NOT invent a git
clone URL or placeholder repository link of any kind — instead say the
project files should be obtained from wherever this upload/archive came
from, and start the steps from "extract/obtain the project files" rather
than "clone".

Format: Markdown, a numbered setup list plus a short workflow paragraph.
Do not add a heading, one will be added.""",
    },
    {
        "title": "Common Tasks, Examples & Troubleshooting",
        "template": """Project: {repo_name}

Architecture: {architecture}
Dependencies actually used by this project: {dependencies}

Key insights from analysis:
{key_insights}

Real files, with their real import/module path (only given when it can be
derived from the actual path — for other languages, cite the file path
itself, never a guessed import) and real function/class names you may
ground a code example in:
{real_code_touchpoints}

Write a "Common Tasks, Examples & Troubleshooting" section: 2-3 realistic
usage examples for this codebase, and likely troubleshooting scenarios
given the insights above. Code examples MUST be written in the same
language and use the same libraries/frameworks as the dependencies listed
above — do not default to Python (or any other language) unless that's
actually what this project uses.

If a code example references a class, method, package, or import, it MUST
use an exact real name/path from the list above — never invent a class,
package, or method that isn't listed there or elsewhere in this document.
If none of the real names above fit the example you want to show, describe
the task in prose instead of writing fabricated code.

Format: Markdown. Put each code example in its own fenced code block as
its own paragraph — never nested inside a numbered or bulleted list item,
since that breaks rendering. Introduce each example with a bold title
line, then the fenced block below it on its own. Follow with a short FAQ
list for troubleshooting. Do not add a heading, one will be added.""",
    },
]

USER_DOCS_HEAD_SECTIONS: List[Dict[str, str]] = [
    {
        "title": "Big Picture",
        "template": """The project's own author describes it as:
{user_context}

Big-picture summary from code analysis:
{overview}

Write a short "Big Picture" section for a non-technical user guide: plain
language, what this does and why someone would use it. If the author's own
description above is given, ground your answer in it rather than the code
analysis alone.

Format: Markdown, 2-3 short sentences. Do not add a heading, one will be added.""",
    },
    {
        "title": "Quick Start & Installation",
        "template": """Project: {repo_name}
Repository: {repo_url}

Dependencies: {dependencies}

Write a "Quick Start & Installation" section for a non-technical audience:
install steps (3 steps max) and how to get it running the first time.

If Repository above is a real URL, use it for the download/clone step —
never invent a different URL. If Repository above says this was analyzed
from a local upload (no hosted URL), don't invent a URL or repository
link of any kind — just say to get the project files from wherever this
upload/archive came from, and start from there.

Format: Markdown, numbered steps, simple language. Do not add a heading, one will be added.""",
    },
]

USER_DOCS_TAIL_SECTIONS: List[Dict[str, str]] = [
    {
        "title": "FAQ, Troubleshooting & Support",
        "template": """Project: {repo_name}
Repository: {repo_url}

Write a short "FAQ, Troubleshooting & Support" section for this project:
2-3 likely questions a new user would have, plus where to get help. For
support, point to the repository above — do not invent a contact email or
support address.

Format: Markdown Q&A list, simple language. Do not add a heading, one will be added.""",
    },
]


def build_doc_context(analysis: dict, repo_url: Optional[str] = None,
                       file_structures: Optional[Dict[str, dict]] = None,
                       significant_files: Optional[List[str]] = None) -> dict:
    """Flatten an analysis dict (+ the real repo URL) into template context.

    `file_structures`/`significant_files`, when given, ground the Common
    Tasks section in real per-file signatures (see _real_code_touchpoints)
    instead of leaving it with only a dependency-name list to work from.
    """
    resolved_repo_url = (
        repo_url
        or analysis.get("repo_url")
        or "N/A — analyzed from a local upload, not a hosted repository"
    )
    return {
        "repo_name": analysis.get("repo_name") or "the project",
        "repo_url": resolved_repo_url,
        "file_tree": analysis.get("file_tree", "N/A"),
        "architecture": analysis.get("architecture", ""),
        "key_modules": json.dumps(analysis.get("key_modules", []))[:2000],
        "dependencies": json.dumps(analysis.get("dependencies", [])),
        "patterns": json.dumps(analysis.get("patterns", [])),
        "data_flow": analysis.get("data_flow", ""),
        "key_insights": analysis.get("key_insights", ""),
        "overview": analysis.get("overview", ""),
        "how_it_works": analysis.get("how_it_works", ""),
        "user_context": analysis.get("user_context") or "(not provided)",
        "modules": ", ".join(analysis.get("key_modules", [])[:5]),
        "real_code_touchpoints": (
            _real_code_touchpoints(file_structures, significant_files)
            if file_structures and significant_files
            else "(no real per-file signatures available for this repo)"
        ),
    }


def build_sectioned_doc(ollama_client, model: str, sections: List[Dict[str, str]],
                         context: dict, context_length: int = 8192, on_section=None) -> str:
    """Generate a Markdown document one section at a time.

    `on_section(index, total, title)`, if given, is called just before each
    section's model call — used to surface live progress.
    """
    safe_context = defaultdict(lambda: "N/A", context)
    total = len(sections)
    parts = []
    for index, section in enumerate(sections, start=1):
        if on_section:
            on_section(index, total, section["title"])
        prompt = section["template"].format_map(safe_context) + f"\n\n{ANTI_HALLUCINATION_NOTE}"
        # Wrapped at "## title" (level 2) -> anything the model adds nests at >=3.
        body = _safe_generate(ollama_client, model, prompt, context_length, section["title"],
                               min_heading_level=3)
        parts.append(f"## {section['title']}\n\n{body}")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------
# Tier 2/3: dynamic, per-file/per-feature sections grounded in real code —
# the fix for hallucinated function names and feature descriptions.
# --------------------------------------------------------------------------

def select_significant_files(code_files: Dict[str, str], file_structures: Dict[str, dict],
                              key_modules: Optional[List[str]] = None,
                              max_files: int = MAX_WALKTHROUGH_FILES) -> List[str]:
    """Rank files by real importance — Aider's repo-map algorithm: PageRank
    over a "file R calls a symbol defined in file D" graph (see
    core/repo_map.py) — so per-file walkthrough calls are spent on files
    other code actually depends on, not just ones with a lot of code on
    paper. Falls back to a functions+classes count as a tie-breaker and
    for languages/files with no graph signal."""
    from core.repo_map import rank_files_by_importance

    ranks = rank_files_by_importance(code_files, file_structures)

    def richness(filename: str) -> int:
        structure = file_structures.get(filename, {})
        return len(structure.get("functions", [])) + len(structure.get("classes", []))

    def score(filename: str):
        return (ranks.get(filename, 0.0), richness(filename))

    ranked = sorted(code_files.keys(), key=score, reverse=True)
    significant = [f for f in ranked if score(f) > (0.0, 0)][:max_files]

    # Always include Odysseus's own key modules, even a thin entrypoint/config
    # file with no detected functions/classes/calls of its own.
    for module in (key_modules or []):
        if module in code_files and module not in significant and len(significant) < max_files:
            significant.append(module)

    return significant


def identify_features(ollama_client, model: str, context: dict,
                       significant_files: List[str], file_structures: Dict[str, dict],
                       context_length: int = 8192) -> List[Dict]:
    """One grounded call: name the real features this codebase implements,
    each backed by real files/functions actually given to the model."""
    file_summary = "\n".join(
        f"- {f}: functions={file_structures.get(f, {}).get('functions', [])}, "
        f"classes={file_structures.get(f, {}).get('classes', [])}"
        for f in significant_files
    )[:4000]

    prompt = f"""Project: {context['repo_name']}
The project's own author describes it as: {context['user_context']}
Architecture: {context['architecture']}
How it works: {context['how_it_works']}

Real files and the real functions/classes found in them:
{file_summary}

Identify the distinct user-facing features or capabilities this codebase
implements, using ONLY the files and functions/classes listed above — do
not invent files or functions that are not in this list.

Respond with JSON only, no markdown fence:
{{"features": [{{"name": "short feature name", "files": ["exact filenames from the list above"], "key_functions": ["exact function/class names from the list above"]}}]}}

{ANTI_HALLUCINATION_NOTE}"""

    raw = _safe_generate(ollama_client, model, prompt, context_length, "feature identification")
    try:
        start, end = raw.find("{"), raw.rfind("}") + 1
        data = json.loads(raw[start:end]) if start >= 0 and end > start else {}
        features = data.get("features") or []
        if features:
            return features
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Could not parse features JSON, falling back to one feature per file: {e}")

    # Deterministic fallback: never return zero features just because the
    # model's JSON didn't parse.
    if significant_files:
        return [
            {"name": f, "files": [f], "key_functions": file_structures.get(f, {}).get("functions", [])}
            for f in significant_files
        ]
    return [{"name": context["repo_name"], "files": [], "key_functions": []}]


def build_feature_map_section(ollama_client, model: str, context: dict,
                               features: List[Dict], context_length: int = 8192) -> str:
    """Tier 2 (Developer Docs): for each real feature, what to touch to change it."""
    features_json = json.dumps(features)[:4000]
    prompt = f"""Project: {context['repo_name']}

Real identified features, each with the real files/functions that implement it:
{features_json}

Write a "Feature -> File Map" section for developers: for EACH feature
listed above, explain in 1-3 sentences what a developer would need to
touch (which file(s), and which function/class within it) to modify or
extend that feature. Use ONLY the files/functions given — do not invent
others.

Format: Markdown, one subheading per feature. Do not add a top-level
heading, one will be added.

{ANTI_HALLUCINATION_NOTE}"""
    # Wrapped externally as "## Feature -> File Map" (level 2); its own
    # "one subheading per feature" should nest at >=3.
    return _safe_generate(ollama_client, model, prompt, context_length, "Feature -> File Map",
                           min_heading_level=3)


def build_file_walkthrough_sections(ollama_client, model: str, code_files: Dict[str, str],
                                     file_structures: Dict[str, dict], significant_files: List[str],
                                     context: dict, context_length: int = 8192,
                                     max_chars_per_file: int = MAX_CHARS_PER_WALKTHROUGH_FILE,
                                     on_file=None) -> str:
    """Tier 3 (Developer Docs): one call per significant file, grounded in
    that file's real source — the model can't invent a function it's
    literally looking at."""
    total = len(significant_files)
    parts = []
    for index, filename in enumerate(significant_files, start=1):
        if on_file:
            on_file(index, total, filename)
        content = code_files.get(filename, "")[:max_chars_per_file]
        structure = file_structures.get(filename, {})
        prompt = f"""Project: {context['repo_name']}
File: {filename}

Real functions detected in this file: {structure.get('functions', [])}
Real classes detected in this file: {structure.get('classes', [])}
Real imports detected in this file: {structure.get('imports', [])}

Actual source code of this file:
```
{content}
```

Explain this specific file for a developer who needs to extend it: what it
does, how its key functions/classes work, and what to watch out for when
modifying it. Ground every function/class name you mention in the real
code above — do not invent ones that aren't in it.

Format: Markdown, no top-level heading (one will be added).

{ANTI_HALLUCINATION_NOTE}"""
        # Wrapped at "### `filename`" (level 3) -> internal sub-structure
        # (Key Functions, Imports, ...) should nest at >=4.
        body = _safe_generate(ollama_client, model, prompt, context_length, filename,
                               min_heading_level=4)
        parts.append(f"### `{filename}`\n\n{body}")
    return "\n\n".join(parts)


_USER_GUIDE_LEAK_HEADING_RE = re.compile(
    r"^[ \t]*#{0,6}[ \t]*\**"
    r"(real capability signals|key (?:functions|classes|methods)|"
    r"internal (?:functions|signals|details)|implementation details)"
    r"\**[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def _strip_leaked_internal_section(text: str) -> str:
    """User Guide feature prompts are given real function/class names as
    background grounding only, with an explicit "never repeat this to the
    reader" instruction — but a model sometimes echoes that grounding back
    verbatim anyway, as its own heading (or bold line) followed by a raw
    method dump (e.g. "Real Capability Signals" -> getId, setId,
    getSection1, ...). Strip such a heading/line and the list block
    directly under it as a second line of defense — none of it belongs in
    end-user-facing docs regardless of how the prompt is worded."""
    lines = text.split("\n")
    out: List[str] = []
    skipping = False
    for line in lines:
        if _USER_GUIDE_LEAK_HEADING_RE.match(line):
            skipping = True
            continue
        if skipping:
            if line.strip() == "":
                continue
            if re.match(r"^[ \t]*([-*•]|\d+[.)])\s", line):
                continue
            skipping = False
        out.append(line)
    return "\n".join(out)


def build_user_feature_sections(ollama_client, model: str, context: dict,
                                 features: List[Dict], context_length: int = 4096,
                                 on_feature=None) -> str:
    """User Guide: one call per real feature, usage-level (no code/files
    shown to the reader), grounded in the same feature list as the dev docs
    so both documents describe a consistent set of capabilities."""
    total = len(features)
    parts = []
    for index, feature in enumerate(features, start=1):
        name = feature.get("name", f"Feature {index}")
        if on_feature:
            on_feature(index, total, name)
        prompt = f"""Project: {context['repo_name']}

Feature: {name}

(Background only, for your understanding — never repeat any of this to
the reader, and never turn it into a heading or list of its own: this
feature's real implementation touches {feature.get('files')} and involves
functions/classes named {feature.get('key_functions')}.)

Write a short "{name}" section for a non-technical user guide: what this
feature does for the user and how they would use it in practice. Do not
show code, file names, or function/method names to the reader — this is
for end users, not developers. Never create a heading or bullet list of
function or method names. If you can't be certain of exact commands/flags,
describe the workflow conceptually rather than inventing precise syntax.

Format: Markdown, 1-2 short paragraphs or a short bullet list. No top-level heading.

{ANTI_HALLUCINATION_NOTE}"""
        # Wrapped at "### {name}" (level 3) -> anything internal nests at >=4.
        body = _safe_generate(ollama_client, model, prompt, context_length, name,
                               min_heading_level=4)
        body = _strip_leaked_internal_section(body)
        parts.append(f"### {name}\n\n{body}")
    return "\n\n".join(parts)
