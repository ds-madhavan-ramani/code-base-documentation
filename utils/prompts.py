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

_LEADING_HEADING_RE = re.compile(r"^#{1,6}[ \t].*\n+", re.MULTILINE)


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


def _safe_generate(ollama_client, model: str, prompt: str, context_length: int, label: str) -> str:
    """Every model call in this module goes through here so that one failed
    call (timeout, Ollama restart, OOM) produces a visible placeholder for
    just that section/file/feature instead of an uncaught exception that
    discards every section already generated in the same document."""
    try:
        text = ollama_client.generate(model, prompt, context_length=context_length).strip()
        return _strip_leading_heading(text)
    except Exception as e:
        logger.error(f"Generation failed for {label}: {e}")
        return f"_(Generation failed for this section — {e})_"

# --------------------------------------------------------------------------
# Tier 1: whole-document, fixed sections (grounded in the Odysseus analysis
# summary — architecture, patterns, dependencies — not per-file source).
# --------------------------------------------------------------------------

DEV_DOCS_TIER1_SECTIONS: List[Dict[str, str]] = [
    {
        "title": "Big Picture",
        "template": """Project: {repo_name}

Big-picture summary from analysis:
{overview}

Write the opening section of a developer guide, titled "Big Picture". In
plain, simplified language explain WHAT this codebase does, HOW it works
at the highest level, and WHY it is built this way. Strip away detail,
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

Write a "Configuration, Setup & Development Workflow" section: how to clone
this exact repository, install these exact dependencies, configure the
project, and the typical development loop (run/test/iterate).

Format: Markdown, a numbered setup list using the real repository URL
above (never invent a different one) plus a short workflow paragraph.
Do not add a heading, one will be added.""",
    },
    {
        "title": "Common Tasks, Examples & Troubleshooting",
        "template": """Project: {repo_name}

Key insights from analysis:
{key_insights}

Write a "Common Tasks, Examples & Troubleshooting" section: 2-3 realistic
usage examples for this codebase, and likely troubleshooting scenarios
given the insights above.

Format: Markdown, with code-style examples where sensible and a short FAQ
list for troubleshooting. Do not add a heading, one will be added.""",
    },
]

USER_DOCS_HEAD_SECTIONS: List[Dict[str, str]] = [
    {
        "title": "Big Picture",
        "template": """Big-picture summary from analysis:
{overview}

Write a short "Big Picture" section for a non-technical user guide: plain
language, what this does and why someone would use it.

Format: Markdown, 2-3 short sentences. Do not add a heading, one will be added.""",
    },
    {
        "title": "Quick Start & Installation",
        "template": """Project: {repo_name}
Repository: {repo_url}

Dependencies: {dependencies}

Write a "Quick Start & Installation" section for a non-technical audience:
install steps (3 steps max) using the real repository URL above (never
invent a different one), and how to get it running the first time.

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


def build_doc_context(analysis: dict, repo_url: Optional[str] = None) -> dict:
    """Flatten an analysis dict (+ the real repo URL) into template context."""
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
        "modules": ", ".join(analysis.get("key_modules", [])[:5]),
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
        body = _safe_generate(ollama_client, model, prompt, context_length, section["title"])
        parts.append(f"## {section['title']}\n\n{body}")
    return "\n\n".join(parts)


# --------------------------------------------------------------------------
# Tier 2/3: dynamic, per-file/per-feature sections grounded in real code —
# the fix for hallucinated function names and feature descriptions.
# --------------------------------------------------------------------------

def select_significant_files(code_files: Dict[str, str], file_structures: Dict[str, dict],
                              key_modules: Optional[List[str]] = None,
                              max_files: int = MAX_WALKTHROUGH_FILES) -> List[str]:
    """Rank files by how much real structure they contain (functions +
    classes found by regex), so per-file walkthrough calls are spent on the
    files that matter instead of trivial config/test files."""
    def richness(filename: str) -> int:
        structure = file_structures.get(filename, {})
        return len(structure.get("functions", [])) + len(structure.get("classes", []))

    ranked = sorted(code_files.keys(), key=richness, reverse=True)
    significant = [f for f in ranked if richness(f) > 0][:max_files]

    # Always include Odysseus's own key modules, even a thin entrypoint/config
    # file the regex extractor found no functions/classes in.
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
    return _safe_generate(ollama_client, model, prompt, context_length, "Feature -> File Map")


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
        body = _safe_generate(ollama_client, model, prompt, context_length, filename)
        parts.append(f"### `{filename}`\n\n{body}")
    return "\n\n".join(parts)


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
Implemented in (for your context only, do not mention file/code details to the reader): {feature.get('files')}
Real capability signals: {feature.get('key_functions')}

Write a short "{name}" section for a non-technical user guide: what this
feature does for the user and how they would use it in practice. Do not
show code or file names to the reader — this is for end users, not
developers. If you can't be certain of exact commands/flags, describe the
workflow conceptually rather than inventing precise syntax.

Format: Markdown, 1-2 short paragraphs or a short bullet list. No top-level heading.

{ANTI_HALLUCINATION_NOTE}"""
        body = _safe_generate(ollama_client, model, prompt, context_length, name)
        parts.append(f"### {name}\n\n{body}")
    return "\n\n".join(parts)
