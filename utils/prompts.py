"""Section-by-section prompt templates for documentation generation.

Earlier versions asked one model call to write an entire multi-section
document in one shot. A small local model (e.g. qwen2.5-coder:7b) tends to
run out of depth partway through a long completion like that, so both
documents are now built one section at a time: each section gets its own
focused prompt and its own `ollama.generate()` call, then the pieces are
concatenated. See README.md's "Documentation Generation" section for the
flow diagram.
"""

import json
from collections import defaultdict
from typing import Dict, List

DEV_DOCS_SECTIONS: List[Dict[str, str]] = [
    {
        "title": "Big Picture (Reductionist View)",
        "template": """Project: {repo_name}

Big-picture summary from analysis:
{reductionist_view}

Write the opening section of a developer guide, titled "Big Picture". In
plain, simplified language explain WHAT this codebase does, HOW it works
at the highest level, and WHY it is built this way. This is the
reductionist view — strip away detail, don't list files or functions here.

Format: Markdown, 2-4 short paragraphs. Do not add a heading, one will be added.""",
    },
    {
        "title": "Systems View",
        "template": """Project: {repo_name}

Systems-level notes from analysis:
{systems_view}

File tree:
{file_tree}

Write a "Systems View" section explaining how the pieces fit together to
produce the big picture above — name real files/modules and trace how
they connect and hand off to each other (calls, data, control flow).

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

Write an "Architecture & Design Patterns" section: overall design, layers,
and the specific patterns in play, plus how data flows through the system.

Format: Markdown, a short bullet list of patterns followed by narrative
paragraphs. Do not add a heading, one will be added.""",
    },
    {
        "title": "Module & Dependency Map",
        "template": """Project: {repo_name}

Key modules:
{key_modules}

Dependencies:
{dependencies}

Write a "Module & Dependency Map" section: what each key module is
responsible for, and how the external dependencies are used.

Format: Markdown table or bullet list mapping module -> responsibility,
plus a short dependency list. Do not add a heading, one will be added.""",
    },
    {
        "title": "Key APIs, Functions & Classes",
        "template": """Project: {repo_name}

Key modules: {key_modules}
Architecture: {architecture}
Systems view: {systems_view}
Detected functions (if any): {functions}
Detected classes (if any): {classes}

Write a "Key APIs, Functions & Classes" section documenting the most
important functions/classes and what they are likely for, grounded in the
module and architecture context above.

Format: Markdown, grouped by module where possible. Do not add a heading, one will be added.""",
    },
    {
        "title": "Configuration, Setup & Development Workflow",
        "template": """Project: {repo_name}

Key modules: {key_modules}
Dependencies: {dependencies}

Write a "Configuration, Setup & Development Workflow" section: how to
install dependencies, configure the project (env vars/config files implied
by the dependencies), and the typical development loop (run/test/iterate)
for a project shaped like this.

Format: Markdown, a numbered setup list plus a short workflow paragraph.
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

USER_DOCS_SECTIONS: List[Dict[str, str]] = [
    {
        "title": "Big Picture",
        "template": """Big-picture summary from analysis:
{reductionist_view}

Write a short "Big Picture" section for a non-technical user guide: plain
language, what this does and why someone would use it.

Format: Markdown, 2-3 short sentences. Do not add a heading, one will be added.""",
    },
    {
        "title": "Quick Start & Installation",
        "template": """Key modules: {modules}

Write a "Quick Start & Installation" section for a non-technical audience:
install steps (3 steps max) and how to get it running the first time.

Format: Markdown, numbered steps, simple language. Do not add a heading, one will be added.""",
    },
    {
        "title": "Features & Common Workflows",
        "template": """Key modules: {modules}

Write a "Features & Common Workflows" section: the main things a user can
do with this project, plus a couple of everyday usage examples.

Format: Markdown bullet list plus 1-2 short examples, simple language.
Do not add a heading, one will be added.""",
    },
    {
        "title": "FAQ, Troubleshooting & Support",
        "template": """Write a short "FAQ, Troubleshooting & Support" section for this project:
2-3 likely questions a new user would have, plus where to get help.

Format: Markdown Q&A list, simple language. Do not add a heading, one will be added.""",
    },
]


def build_doc_context(analysis: dict) -> dict:
    """Flatten an analysis dict into the string context the section templates format against."""
    return {
        "repo_name": analysis.get("repo_name") or "the project",
        "file_tree": analysis.get("file_tree", "N/A"),
        "architecture": analysis.get("architecture", ""),
        "key_modules": json.dumps(analysis.get("key_modules", []))[:2000],
        "dependencies": json.dumps(analysis.get("dependencies", [])),
        "patterns": json.dumps(analysis.get("patterns", [])),
        "data_flow": analysis.get("data_flow", ""),
        "key_insights": analysis.get("key_insights", ""),
        "reductionist_view": analysis.get("reductionist_view", ""),
        "systems_view": analysis.get("systems_view", ""),
        "functions": json.dumps(analysis.get("functions", []))[:1500],
        "classes": json.dumps(analysis.get("classes", []))[:1500],
        "modules": ", ".join(analysis.get("key_modules", [])[:5]),
    }


def build_sectioned_doc(ollama_client, model: str, sections: List[Dict[str, str]],
                         context: dict, context_length: int = 8192, on_section=None) -> str:
    """Generate a Markdown document one section at a time.

    Each section gets its own model call instead of one shot for the whole
    document, so a smaller local model has room to go deep on each part
    rather than running out of depth over a single giant completion.

    `on_section(index, total, title)`, if given, is called just before each
    section's model call — used to surface live progress (e.g. "section
    3/7: Architecture & Design Patterns") to a caller.
    """
    safe_context = defaultdict(lambda: "N/A", context)
    total = len(sections)
    parts = []
    for index, section in enumerate(sections, start=1):
        if on_section:
            on_section(index, total, section["title"])
        prompt = section["template"].format_map(safe_context)
        body = ollama_client.generate(model, prompt, context_length=context_length).strip()
        parts.append(f"## {section['title']}\n\n{body}")
    return "\n\n".join(parts)
