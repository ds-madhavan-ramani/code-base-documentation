import json
import shutil
from markdown import Markdown, markdown as md_convert
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DocumentationGenerator:
    def __init__(self, output_dir: str = "./data/outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def markdown_to_html(self, markdown_content: str, title: str = "Documentation") -> str:
        """Convert Markdown to a full-width, navigable HTML document.

        Generated docs run to dozens of sections (per-file walkthroughs,
        per-feature guides), so this renders a sticky sidebar table of
        contents — built from the real heading structure via markdown's own
        `toc` extension, so it can never drift out of sync with the actual
        section ids — next to a wide content column, instead of a single
        narrow scrolling page with no way to jump around.
        """
        md = Markdown(
            extensions=['fenced_code', 'tables', 'toc'],
            extension_configs={'toc': {'toc_depth': '2-4', 'permalink': False}},
        )
        try:
            html_body = md.convert(markdown_content)
            toc_html = md.toc if '<li>' in md.toc else ''
        except Exception as e:
            logger.warning(f"Markdown conversion failed: {e}")
            html_body = md_convert(markdown_content)
            toc_html = ''

        nav_content = toc_html or '<p class="sidebar-empty">No sections found.</p>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --accent: #3b82f6;
            --accent-dark: #2563eb;
            --text: #1e293b;
            --text-muted: #64748b;
            --bg: #ffffff;
            --bg-alt: #f8fafc;
            --border: #e2e8f0;
            --code-bg: #0f172a;
            --code-text: #e2e8f0;
            --sidebar-width: 300px;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.65;
            color: var(--text);
            background: var(--bg);
        }}

        /* Mobile nav toggle, pure CSS (no JS dependency for the core interaction) */
        .nav-toggle-state {{ display: none; }}
        .topbar {{
            display: none;
            position: sticky; top: 0; z-index: 20;
            align-items: center; gap: 12px;
            padding: 12px 20px;
            background: var(--bg);
            border-bottom: 1px solid var(--border);
        }}
        .nav-toggle-btn {{
            cursor: pointer; font-size: 20px; line-height: 1;
            padding: 4px 8px; border-radius: 6px; user-select: none;
        }}
        .nav-toggle-btn:hover {{ background: var(--bg-alt); }}
        .topbar-title {{ font-weight: 600; font-size: 15px; color: var(--text); }}

        .layout {{ display: flex; align-items: flex-start; min-height: 100vh; }}

        .sidebar {{
            flex: 0 0 var(--sidebar-width);
            width: var(--sidebar-width);
            position: sticky; top: 0;
            height: 100vh;
            overflow-y: auto;
            padding: 28px 20px;
            background: var(--bg-alt);
            border-right: 1px solid var(--border);
        }}
        .sidebar-title {{
            font-size: 12px; font-weight: 700; letter-spacing: 0.08em;
            text-transform: uppercase; color: var(--text-muted);
            margin-bottom: 14px;
        }}
        .sidebar .toc > ul, .sidebar ul {{ list-style: none; }}
        .sidebar > .toc > ul {{ padding-left: 0; }}
        .sidebar ul ul {{ padding-left: 16px; }}
        .sidebar li {{ margin: 2px 0; }}
        .sidebar a {{
            display: block;
            padding: 6px 10px;
            border-radius: 6px;
            color: var(--text-muted);
            text-decoration: none;
            font-size: 14px;
            line-height: 1.4;
        }}
        .sidebar a:hover {{ background: #eef2ff; color: var(--accent-dark); }}
        .sidebar-empty {{ color: var(--text-muted); font-size: 14px; }}
        .nav-overlay {{ display: none; }}

        .content {{
            flex: 1 1 auto;
            min-width: 0;
            max-width: 1200px;
            margin: 0 auto;
            padding: 48px 64px 96px;
        }}

        h1 {{
            font-size: 32px; font-weight: 800; color: var(--text);
            padding-bottom: 16px; margin-bottom: 28px;
            border-bottom: 3px solid var(--accent);
        }}
        h2 {{
            font-size: 24px; font-weight: 700; color: var(--text);
            margin: 44px 0 16px; padding-top: 8px;
            border-top: 1px solid var(--border);
        }}
        .content > h2:first-of-type {{ border-top: none; padding-top: 0; margin-top: 0; }}
        h3 {{ font-size: 19px; font-weight: 700; color: var(--text); margin: 28px 0 12px; }}
        h4 {{ font-size: 16px; font-weight: 700; color: var(--text-muted); margin: 20px 0 10px; }}
        p, ul, ol {{ margin: 0 0 14px; }}
        ul, ol {{ padding-left: 24px; }}
        li {{ margin: 4px 0; }}
        strong {{ color: var(--text); }}

        code {{
            background: var(--bg-alt);
            border: 1px solid var(--border);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: 13.5px;
        }}
        pre {{
            background: var(--code-bg);
            color: var(--code-text);
            padding: 18px 20px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 18px 0;
            line-height: 1.5;
        }}
        pre code {{ background: none; border: none; padding: 0; color: inherit; }}

        a {{ color: var(--accent-dark); text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}

        blockquote {{
            border-left: 4px solid var(--accent);
            background: var(--bg-alt);
            padding: 12px 18px;
            margin: 18px 0;
            border-radius: 0 8px 8px 0;
            color: var(--text-muted);
        }}
        blockquote p:last-child {{ margin-bottom: 0; }}

        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 18px 0;
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{ border-bottom: 1px solid var(--border); padding: 10px 14px; text-align: left; }}
        th {{ background: var(--bg-alt); font-weight: 700; font-size: 13.5px; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:nth-child(even) td {{ background: #fbfcfe; }}

        .back-to-top {{
            position: fixed; right: 24px; bottom: 24px;
            background: var(--accent); color: white;
            padding: 10px 16px; border-radius: 24px;
            font-size: 13px; font-weight: 600;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 25;
        }}
        .back-to-top:hover {{ background: var(--accent-dark); text-decoration: none; }}

        @media (max-width: 900px) {{
            .topbar {{ display: flex; }}
            .content {{ padding: 32px 24px 96px; }}
            .sidebar {{
                position: fixed; top: 0; left: 0; z-index: 30;
                transform: translateX(-100%);
                transition: transform 0.2s ease;
                box-shadow: 4px 0 16px rgba(0,0,0,0.15);
            }}
            .nav-overlay {{
                display: block;
                position: fixed; inset: 0; z-index: 29;
                background: rgba(15, 23, 42, 0.4);
                opacity: 0; pointer-events: none;
                transition: opacity 0.2s ease;
            }}
            #nav-toggle:checked ~ .layout .sidebar {{ transform: translateX(0); }}
            #nav-toggle:checked ~ .layout .nav-overlay {{ opacity: 1; pointer-events: auto; }}
        }}
    </style>
</head>
<body>
    <a id="top"></a>
    <input type="checkbox" id="nav-toggle" class="nav-toggle-state">
    <header class="topbar">
        <label for="nav-toggle" class="nav-toggle-btn" aria-label="Toggle navigation">&#9776;</label>
        <span class="topbar-title">{title}</span>
    </header>
    <div class="layout">
        <nav class="sidebar">
            <div class="sidebar-title">Contents</div>
            {nav_content}
        </nav>
        <label for="nav-toggle" class="nav-overlay" aria-label="Close navigation"></label>
        <main class="content">
            {html_body}
        </main>
    </div>
    <a href="#top" class="back-to-top">&#8593; Top</a>
</body>
</html>"""

    def save_documentation(self, repo_name: str, dev_docs: str = None,
                           user_docs: str = None, metadata: dict = None):
        """Save whichever documentation files were generated.

        `dev_docs`/`user_docs` may be None when the user only requested one
        document type — in that case its files are simply not written.
        """
        repo_dir = self.output_dir / repo_name
        repo_dir.mkdir(parents=True, exist_ok=True)

        if dev_docs is not None:
            (repo_dir / "DEVELOPER_DOCS.md").write_text(dev_docs)
            dev_html = self.markdown_to_html(dev_docs, "Developer Documentation")
            (repo_dir / "DEVELOPER_DOCS.html").write_text(dev_html)

        if user_docs is not None:
            (repo_dir / "USER_GUIDE.md").write_text(user_docs)
            user_html = self.markdown_to_html(user_docs, "User Guide")
            (repo_dir / "USER_GUIDE.html").write_text(user_html)

        if metadata is not None:
            (repo_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

        logger.info(f"Documentation saved to {repo_dir}")
        return repo_dir

    def output_dir_for(self, repo_name: str) -> Path:
        """Absolute path where a project's generated files are persisted."""
        return self.output_dir / repo_name

    def list_output_files(self, repo_name: str) -> list:
        """Every file actually saved for a project, for display/download."""
        repo_dir = self.output_dir_for(repo_name)
        if not repo_dir.exists():
            return []
        return sorted((p for p in repo_dir.iterdir() if p.is_file()), key=lambda p: p.name)

    def delete_output(self, repo_name: str) -> bool:
        """Permanently delete every generated file for a project.

        Output is keyed by project name, not by job — if multiple jobs
        share a repo_name (re-running the same project), this removes all
        of their generated files, not just one run's.
        """
        repo_dir = self.output_dir_for(repo_name)
        if not repo_dir.exists():
            return False
        shutil.rmtree(repo_dir)
        logger.info(f"Deleted output directory {repo_dir}")
        return True
