import json
import shutil
from markdown import markdown as md_convert
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DocumentationGenerator:
    def __init__(self, output_dir: str = "./data/outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def markdown_to_html(self, markdown_content: str, title: str = "Documentation") -> str:
        """Convert Markdown to styled HTML."""
        try:
            html_body = md_convert(markdown_content, extensions=['fenced_code', 'toc'])
        except Exception as e:
            logger.warning(f"Markdown conversion failed: {e}")
            html_body = md_convert(markdown_content)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin: 30px 0 20px; }}
        h2 {{ color: #34495e; margin: 25px 0 15px; }}
        h3 {{ color: #7f8c8d; margin: 20px 0 10px; }}
        code {{ 
            background: #f4f4f4; 
            padding: 2px 6px; 
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }}
        pre {{ 
            background: #2c3e50; 
            color: #ecf0f1; 
            padding: 15px; 
            border-radius: 5px;
            overflow-x: auto;
            margin: 15px 0;
            line-height: 1.4;
        }}
        pre code {{ background: none; padding: 0; color: inherit; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        blockquote {{ border-left: 4px solid #3498db; padding-left: 15px; margin: 15px 0; color: #666; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #f4f4f4; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        {html_body}
    </div>
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
