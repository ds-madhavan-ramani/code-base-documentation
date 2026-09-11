"""Aider-style repo map: real AST parsing + reference-graph ranking.

Two things this replaces:

1. CodeParser's regex-based structure extraction — brittle: multi-line
   signatures, decorators, and nested classes routinely defeat single-line
   regexes. This uses tree-sitter to parse a real syntax tree instead.

2. The old "richness" heuristic for picking which files matter (just a
   count of regex-matched functions/classes per file) — a poor proxy for
   importance. This instead follows Aider's actual repo-map algorithm:
   extract definitions and references as tags, build a directed graph
   where an edge R -> D means "file R calls a symbol defined in file D",
   then run PageRank over that graph. A file many other files depend on
   ranks higher than one that merely contains a lot of code, even if the
   latter has more functions on paper.

Falls back gracefully: a language with no tag query, or a file that fails
to parse, just contributes no tags/edges rather than raising — the
per-file walkthrough and doc-writing stages already handle empty
functions/classes lists fine (see utils/prompts.py's grounding notes).
"""

from __future__ import annotations

import logging
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# tree_sitter_languages 1.10.2 calls the tree-sitter 0.21 Language()
# constructor in a way that's deprecated (but still functional) as of that
# tree-sitter version — harmless, but noisy on every single file parsed.
warnings.filterwarnings("ignore", message=r"Language\(path, name\) is deprecated")

# Maps a file extension to the tree-sitter grammar name in tree_sitter_languages.
EXTENSION_TO_TS_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
}

# One query per language: captures @name.definition.* for things this file
# defines, and @name.reference.call for symbols it calls. Node field names
# differ across grammars (e.g. TSX's class name field is a type_identifier,
# not an identifier), so each language needs its own query text.
TAG_QUERIES = {
    "python": """
        (function_definition name: (identifier) @name.definition.function) @definition.function
        (class_definition name: (identifier) @name.definition.class) @definition.class
        (call function: (identifier) @name.reference.call) @reference.call
        (call function: (attribute attribute: (identifier) @name.reference.call)) @reference.call
        (import_from_statement module_name: (dotted_name) @name.reference.import)
        (import_statement name: (dotted_name) @name.reference.import)
    """,
    "javascript": """
        (function_declaration name: (identifier) @name.definition.function) @definition.function
        (method_definition name: (property_identifier) @name.definition.method) @definition.method
        (class_declaration name: (identifier) @name.definition.class) @definition.class
        (call_expression function: (identifier) @name.reference.call) @reference.call
        (call_expression function: (member_expression property: (property_identifier) @name.reference.call)) @reference.call
        (import_statement source: (string) @name.reference.import)
    """,
    "typescript": """
        (function_declaration name: (identifier) @name.definition.function) @definition.function
        (method_definition name: (property_identifier) @name.definition.method) @definition.method
        (class_declaration name: (type_identifier) @name.definition.class) @definition.class
        (interface_declaration name: (type_identifier) @name.definition.class) @definition.class
        (call_expression function: (identifier) @name.reference.call) @reference.call
        (call_expression function: (member_expression property: (property_identifier) @name.reference.call)) @reference.call
        (import_statement source: (string) @name.reference.import)
    """,
    "tsx": """
        (function_declaration name: (identifier) @name.definition.function) @definition.function
        (method_definition name: (property_identifier) @name.definition.method) @definition.method
        (class_declaration name: (type_identifier) @name.definition.class) @definition.class
        (interface_declaration name: (type_identifier) @name.definition.class) @definition.class
        (call_expression function: (identifier) @name.reference.call) @reference.call
        (call_expression function: (member_expression property: (property_identifier) @name.reference.call)) @reference.call
        (import_statement source: (string) @name.reference.import)
    """,
    "java": """
        (method_declaration name: (identifier) @name.definition.method) @definition.method
        (class_declaration name: (identifier) @name.definition.class) @definition.class
        (method_invocation name: (identifier) @name.reference.call) @reference.call
        (import_declaration (scoped_identifier) @name.reference.import)
    """,
}

_parser_cache = {}
_query_cache = {}


def _get_parser_and_query(language: str):
    """Lazily load and cache the tree-sitter parser/query for a language."""
    if language in _parser_cache:
        return _parser_cache[language], _query_cache.get(language)

    try:
        import tree_sitter_languages as tsl
        parser = tsl.get_parser(language)
        lang = tsl.get_language(language)
        query = lang.query(TAG_QUERIES[language]) if language in TAG_QUERIES else None
    except Exception as e:
        logger.warning(f"tree-sitter unavailable for {language}: {e}")
        parser, query = None, None

    _parser_cache[language] = parser
    _query_cache[language] = query
    return parser, query


def extract_tags(filename: str, content: str) -> Dict[str, List[str]]:
    """Real, AST-derived functions/classes/calls/imports for one file.

    Returns {"functions": [...], "classes": [...], "calls": [...],
    "imports": [...]} — empty lists for a language with no tree-sitter
    query, or a file that fails to parse (never raises).
    """
    empty = {"functions": [], "classes": [], "calls": [], "imports": []}
    language = EXTENSION_TO_TS_LANGUAGE.get(Path(filename).suffix)
    if not language:
        return empty

    parser, query = _get_parser_and_query(language)
    if not parser or not query:
        return empty

    try:
        tree = parser.parse(content.encode("utf-8", errors="ignore"))
        tags = {"functions": [], "classes": [], "calls": [], "imports": []}
        for node, capture_name in query.captures(tree.root_node):
            text = node.text.decode("utf-8", errors="ignore")
            if capture_name in ("name.definition.function", "name.definition.method"):
                tags["functions"].append(text)
            elif capture_name == "name.definition.class":
                tags["classes"].append(text)
            elif capture_name == "name.reference.call":
                tags["calls"].append(text)
            elif capture_name == "name.reference.import":
                tags["imports"].append(text.strip("'\""))
        return tags
    except Exception as e:
        logger.warning(f"tree-sitter parse failed for {filename}: {e}")
        return empty


def rank_files_by_importance(code_files: Dict[str, str], file_structures: Dict[str, dict]) -> Dict[str, float]:
    """Aider's repo-map ranking: PageRank over a "who calls whose
    definitions" graph, so importance reflects real usage, not just how
    much code a file happens to contain.

    Requires file_structures to include a "calls" list per file (from
    extract_tags) — files/languages without it simply contribute no
    edges and rank at the graph's baseline.
    """
    try:
        import networkx as nx
    except ImportError:
        logger.warning("networkx not installed; falling back to uniform file ranking")
        return {f: 0.0 for f in code_files}

    # symbol name -> file(s) that define it
    definers = defaultdict(list)
    for filename, structure in file_structures.items():
        for name in structure.get("functions", []) + structure.get("classes", []):
            definers[name].append(filename)

    graph = nx.MultiDiGraph()
    graph.add_nodes_from(code_files.keys())

    for filename, structure in file_structures.items():
        for called_name in structure.get("calls", []):
            for def_file in definers.get(called_name, []):
                if def_file != filename:
                    graph.add_edge(filename, def_file, weight=1.0)

    if graph.number_of_edges() == 0:
        return {f: 0.0 for f in code_files}

    try:
        return nx.pagerank(graph, weight="weight")
    except Exception as e:
        logger.warning(f"PageRank failed, falling back to uniform ranking: {e}")
        return {f: 0.0 for f in code_files}
