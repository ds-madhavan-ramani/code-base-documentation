import streamlit as st
import os
import sys
import tempfile
import zipfile
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.code_parser import CodeParser
from core.ollama_client import OllamaClient
from core.odysseus_analysis_agent import OdysseusAnalysisAgent
from core.github_client import GitHubClient
from core.doc_generator import DocumentationGenerator
from core.job_queue import JobQueue, JobStatus
from core.background_worker import BackgroundWorker
from utils.prompts import (
    DEV_DOCS_SECTIONS,
    USER_DOCS_SECTIONS,
    build_doc_context,
    build_sectioned_doc,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

DEV_MODEL = os.getenv("OLLAMA_DEV_MODEL", "qwen2.5-coder:7b")
USER_MODEL = os.getenv("OLLAMA_USER_MODEL", "qwen2.5-coder:7b")

st.set_page_config(page_title="Codebase Documentor", layout="wide")
st.title("🔍 Codebase Documentation Generator")

st.sidebar.title("⚙️ Configuration")
input_mode = st.sidebar.radio("Input Source", ["📁 Local Upload", "🐙 GitHub Repository", "📋 View Jobs"])

@st.cache_resource
def init_clients():
    ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

    # Initialize Odysseus Analysis Agent (direct harness, no API needed)
    odysseus_model = os.getenv("ODYSSEUS_MODEL", "qwen3:32b")
    odysseus = OdysseusAnalysisAgent(model=odysseus_model)

    ollama = OllamaClient(ollama_url)
    doc_gen = DocumentationGenerator(os.getenv("OUTPUT_DIR", "./data/outputs"))
    job_queue = JobQueue(os.getenv("JOBS_DIR", "./data/jobs"))

    # Start background worker
    worker = BackgroundWorker(job_queue, odysseus, ollama, doc_gen,
                               dev_model=DEV_MODEL, user_model=USER_MODEL)
    worker.start()

    return odysseus, ollama, doc_gen, job_queue, worker

odysseus, ollama, doc_gen, job_queue, worker = init_clients()

st.sidebar.markdown("### Service Status")
col1, col2 = st.sidebar.columns(2)

with col1:
    st.sidebar.success("✓ Odysseus (Direct)")

with col2:
    if ollama.health_check():
        st.sidebar.success("✓ Ollama")
    else:
        st.sidebar.warning("✗ Ollama")

if ollama.health_check():
    models = ollama.list_models()
    st.sidebar.markdown(f"**Available Models:** {len(models)}")
    for model in models[:3]:
        st.sidebar.text(f"  • {model}")

st.markdown("### Upload Code Files")

uploaded_files = st.file_uploader(
    "Upload source files or ZIP",
    accept_multiple_files=True,
    type=["py", "js", "ts", "java", "cpp", "go", "rs", "zip"]
)

if uploaded_files:
    st.info(f"📦 {len(uploaded_files)} file(s) uploaded")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract files
        for file in uploaded_files:
            if file.name.endswith(".zip"):
                with zipfile.ZipFile(file) as zf:
                    zf.extractall(tmpdir_path)
            else:
                (tmpdir_path / file.name).write_bytes(file.getvalue())
        
        st.markdown("### Analysis & Documentation")
        parser = CodeParser(tmpdir_path)
        
        with st.spinner("📂 Parsing code structure..."):
            code_files = parser.parse_directory()
            file_tree = parser.create_file_tree()
        
        st.success(f"Found {len(code_files)} code files")

        repo_name = st.text_input("Repository Name", value="my_project")

        with st.spinner("🧠 Analyzing with Odysseus..."):
            analysis = odysseus.analyze_deep(code_files, repo_name)

        if analysis.get("fallback"):
            st.warning("⚠️ Odysseus not responding - using fallback analysis")
        else:
            st.success("✓ Deep analysis complete")

        if st.button("🚀 Generate Documentation"):
            progress = st.progress(0)

            doc_context = build_doc_context(analysis)
            doc_context["file_tree"] = file_tree  # richer tree from CodeParser than analysis's own
            progress.progress(10)

            with st.spinner("📝 Generating developer documentation (section by section)..."):
                dev_body = build_sectioned_doc(
                    ollama, DEV_MODEL, DEV_DOCS_SECTIONS, doc_context, context_length=8192
                )
                dev_docs = f"# Developer Documentation: {doc_context['repo_name']}\n\n{dev_body}"
            progress.progress(50)

            with st.spinner("📚 Generating user guide (section by section)..."):
                user_body = build_sectioned_doc(
                    ollama, USER_MODEL, USER_DOCS_SECTIONS, doc_context, context_length=4096
                )
                user_docs = f"# User Guide: {doc_context['repo_name']}\n\n{user_body}"
            progress.progress(75)
            
            with st.spinner("💾 Saving documentation..."):
                doc_gen.save_documentation(repo_name, dev_docs, user_docs, analysis)
            progress.progress(100)
            
            st.success("✅ Documentation generated successfully!")
            
            st.markdown("### Preview: Developer Docs")
            st.markdown(dev_docs[:1000] + "...\n\n*[Full documentation saved]*")
            
            st.markdown("### Preview: User Guide")
            st.markdown(user_docs[:1000] + "...\n\n*[Full documentation saved]*")
            
            # Download buttons
            st.markdown("### 📥 Download Documentation")
            output_path = Path(os.getenv("OUTPUT_DIR", "./data/outputs")) / repo_name
            
            if (output_path / "DEVELOPER_DOCS.md").exists():
                with open(output_path / "DEVELOPER_DOCS.md") as f:
                    st.download_button(
                        "📄 Developer Docs (MD)",
                        f.read(),
                        "DEVELOPER_DOCS.md"
                    )
            
            if (output_path / "USER_GUIDE.md").exists():
                with open(output_path / "USER_GUIDE.md") as f:
                    st.download_button(
                        "📘 User Guide (MD)",
                        f.read(),
                        "USER_GUIDE.md"
                    )
            
            if (output_path / "DEVELOPER_DOCS.html").exists():
                with open(output_path / "DEVELOPER_DOCS.html") as f:
                    st.download_button(
                        "🌐 Developer Docs (HTML)",
                        f.read(),
                        "DEVELOPER_DOCS.html"
                    )
            
            if (output_path / "USER_GUIDE.html").exists():
                with open(output_path / "USER_GUIDE.html") as f:
                    st.download_button(
                        "🌐 User Guide (HTML)",
                        f.read(),
                        "USER_GUIDE.html"
                    )

elif input_mode == "🐙 GitHub Repository":
    st.markdown("### Analyze GitHub Repository")
    st.info("🚀 Submit a GitHub repository for deep analysis with Odysseus Harness")

    col1, col2 = st.columns(2)
    with col1:
        repo_url = st.text_input(
            "GitHub URL or Path",
            placeholder="https://github.com/user/repo or user/repo"
        )
    with col2:
        repo_name = st.text_input("Project Name", placeholder="my_project")

    if st.button("📤 Submit for Analysis"):
        if not repo_url or not repo_name:
            st.error("Please fill in all fields")
        else:
            # Create job
            job = job_queue.create_job(repo_name, "github", repo_url)
            st.success(f"✅ Job submitted! ID: `{job.job_id}`")
            st.info("Analysis running in background. Check 'View Jobs' to monitor progress.")

elif input_mode == "📋 View Jobs":
    st.markdown("### Analysis Jobs")

    jobs = job_queue.list_jobs()
    if not jobs:
        st.info("No analysis jobs yet")
    else:
        for job in jobs:
            with st.expander(f"**{job.repo_name}** - {job.status.value.upper()} ({job.progress}%)"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Status", job.status.value)
                with col2:
                    st.metric("Progress", f"{job.progress}%")
                with col3:
                    st.metric("Source", job.source_type)

                if job.error:
                    st.error(f"❌ Error: {job.error}")

                if job.status == JobStatus.COMPLETED:
                    # Show analysis results
                    if job.analysis:
                        st.success("✅ Analysis Complete")
                        with st.expander("📊 Analysis Results"):
                            st.json(job.analysis)

                    # Show download buttons
                    output_path = Path(os.getenv("OUTPUT_DIR", "./data/outputs")) / job.repo_name
                    if (output_path / "DEVELOPER_DOCS.md").exists():
                        with open(output_path / "DEVELOPER_DOCS.md") as f:
                            st.download_button(
                                "📄 Developer Docs",
                                f.read(),
                                f"{job.repo_name}_DEVELOPER_DOCS.md",
                                key=f"dev_{job.job_id}"
                            )

                    if (output_path / "USER_GUIDE.md").exists():
                        with open(output_path / "USER_GUIDE.md") as f:
                            st.download_button(
                                "📘 User Guide",
                                f.read(),
                                f"{job.repo_name}_USER_GUIDE.md",
                                key=f"user_{job.job_id}"
                            )
