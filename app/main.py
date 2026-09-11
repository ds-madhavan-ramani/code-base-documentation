import streamlit as st
import json
import os
import sys
import tempfile
import time
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

DEV_MODEL = os.getenv("OLLAMA_DEV_MODEL", "qwen2.5-coder:7b")
USER_MODEL = os.getenv("OLLAMA_USER_MODEL", "qwen2.5-coder:7b")

DOC_TYPE_OPTIONS = {
    "Both": "both",
    "Developer Docs Only": "dev",
    "End-User Guide Only": "user",
}

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
    job_queue = JobQueue(
        os.getenv("JOBS_DIR", "./data/jobs"),
        upload_dir=os.getenv("UPLOAD_DIR", "./data/uploads")
    )

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

        parser = CodeParser(tmpdir_path)
        with st.spinner("📂 Parsing code structure..."):
            code_files = parser.parse_directory()

        st.success(f"Found {len(code_files)} code files")
        if len(code_files) > 50:
            st.info(
                f"{len(code_files)} files is a large codebase for the deep-analysis "
                "stage to work through — this can take a while. It now runs as a "
                "background job, same as the GitHub Repository route: submit "
                "below, then check 'View Jobs' for live progress."
            )

        with st.form("local_upload_form"):
            repo_name = st.text_input("Repository Name", value="my_project")
            user_context = st.text_area(
                "Project Overview & Use Case (optional, strongly recommended)",
                placeholder=(
                    "What is this tool/project, and what problem does it solve? "
                    "E.g. \"An internal tool for the legal team to extract and "
                    "cross-reference clauses across vendor contracts, replacing "
                    "a manual spreadsheet process.\" Code alone can't explain "
                    "WHY a project exists — this grounds the generated Big "
                    "Picture section instead of leaving the model to guess."
                ),
                height=100,
            )
            doc_type_label = st.radio(
                "Document Type", list(DOC_TYPE_OPTIONS.keys()), horizontal=True
            )
            submitted = st.form_submit_button("🚀 Submit for Analysis")

        if submitted:
            if not repo_name:
                st.error("Please enter a repository name")
            else:
                # Same job pipeline as the GitHub route (background_worker.py),
                # so depth of analysis and progress reporting are identical
                # regardless of whether the code came from a zip or a URL.
                job = job_queue.create_job(
                    repo_name, "upload", code_files,
                    doc_type=DOC_TYPE_OPTIONS[doc_type_label], user_context=user_context
                )
                st.success(f"✅ Job submitted! ID: `{job.job_id}`")
                st.info("Analysis running in background. Check 'View Jobs' to monitor progress.")

elif input_mode == "🐙 GitHub Repository":
    st.markdown("### Analyze GitHub Repository")
    st.info("🚀 Submit a GitHub repository for deep analysis with Odysseus Harness")

    with st.form("github_analysis_form"):
        col1, col2 = st.columns(2)
        with col1:
            repo_url = st.text_input(
                "GitHub URL or Path",
                placeholder="https://github.com/user/repo or user/repo"
            )
        with col2:
            repo_name = st.text_input("Project Name", placeholder="my_project")

        user_context = st.text_area(
            "Project Overview & Use Case (optional, strongly recommended)",
            placeholder=(
                "What is this tool/project, and what problem does it solve? "
                "E.g. \"An internal tool for the legal team to extract and "
                "cross-reference clauses across vendor contracts, replacing "
                "a manual spreadsheet process.\" Code alone can't explain "
                "WHY a project exists — this grounds the generated Big "
                "Picture section instead of leaving the model to guess."
            ),
            height=100,
        )

        doc_type_label = st.radio(
            "Document Type", list(DOC_TYPE_OPTIONS.keys()), horizontal=True
        )

        submitted = st.form_submit_button("📤 Submit for Analysis")

    if submitted:
        if not repo_url or not repo_name:
            st.error("Please fill in all fields")
        elif not GitHubClient.is_github_url(repo_url):
            st.error(
                "That doesn't look like a GitHub reference — use a full URL "
                "(https://github.com/user/repo) or the 'user/repo' shorthand."
            )
        else:
            # Create job
            job = job_queue.create_job(
                repo_name, "github", repo_url,
                doc_type=DOC_TYPE_OPTIONS[doc_type_label], user_context=user_context
            )
            st.success(f"✅ Job submitted! ID: `{job.job_id}`")
            st.info("Analysis running in background. Check 'View Jobs' to monitor progress.")

elif input_mode == "📋 View Jobs":
    st.markdown("### Analysis Jobs")

    jobs = job_queue.list_jobs()
    if not jobs:
        st.info("No analysis jobs yet")
    else:
        any_active = False
        selected_for_deletion = []
        for job in jobs:
            with st.expander(f"**{job.repo_name}** - {job.status.value.upper()} ({job.progress}%)"):
                col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                with col1:
                    st.metric("Status", job.status.value)
                with col2:
                    st.metric("Progress", f"{job.progress}%")
                with col3:
                    st.metric("Source", job.source_type)
                with col4:
                    if st.checkbox("🗑️ Select", key=f"select_del_{job.job_id}"):
                        selected_for_deletion.append(job)

                if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
                    any_active = True
                    st.progress(job.progress / 100)
                    st.caption(f"🔄 {job.current_step or 'Waiting...'}")

                if job.error:
                    st.error(f"❌ Error: {job.error}")

                if job.status == JobStatus.COMPLETED:
                    # Show analysis results
                    if job.analysis:
                        st.success("✅ Analysis Complete")
                        coverage = job.analysis.get("coverage")
                        if coverage:
                            eligible = coverage.get("eligible_files", coverage["total_files"])
                            st.caption(
                                f"📈 Coverage: {coverage['files_fully_documented']}/{eligible} eligible files "
                                f"fully documented ({coverage['coverage_pct']}%) — {coverage['total_files']} "
                                "files total; tests, docs, and `__init__.py` files are intentionally excluded "
                                "from the walkthrough and still appear only in the Repository Structure tree."
                            )
                        if st.checkbox("📊 Show Analysis Results (JSON)", key=f"show_analysis_{job.job_id}"):
                            st.json(job.analysis)

                    # Show every output file actually saved for this project
                    output_files = doc_gen.list_output_files(job.repo_name)
                    if output_files:
                        st.caption(f"📁 Saved to: `{doc_gen.output_dir_for(job.repo_name)}`")
                        for output_file in output_files:
                            with open(output_file, "rb") as f:
                                st.download_button(
                                    f"⬇️ {output_file.name}",
                                    f.read(),
                                    f"{job.repo_name}_{output_file.name}",
                                    key=f"dl_{job.job_id}_{output_file.name}"
                                )

                    if doc_gen.load_metadata(job.repo_name) is not None:
                        st.caption(
                            "🔄 Regenerate re-runs only the documentation-writing step, reusing the saved "
                            "analysis above — use it after a template/prompt change, not a code change "
                            "(it will NOT pick up edits to the source itself)."
                        )
                        if st.button("🔄 Regenerate Docs (skip re-analysis)", key=f"regen_{job.job_id}"):
                            try:
                                if job.source_type == "upload":
                                    source = json.loads(Path(job.source).read_text())
                                else:
                                    source = job.source
                                new_job = job_queue.create_job(
                                    job.repo_name, job.source_type, source,
                                    doc_type=job.doc_type, user_context=job.user_context,
                                    use_cached_analysis=True,
                                )
                                st.success(f"✅ Regeneration job submitted! ID: `{new_job.job_id}`")
                                st.rerun()
                            except (OSError, json.JSONDecodeError) as e:
                                st.error(f"Could not reuse this job's original source: {e}")

        if selected_for_deletion:
            st.divider()
            names = ", ".join(f"**{j.repo_name}**" for j in selected_for_deletion)
            st.warning(
                f"⚠️ {len(selected_for_deletion)} job(s) selected: {names}. "
                "Deleting removes the job record AND permanently deletes that "
                "project's generated output files on disk (all files under "
                "`<OUTPUT_DIR>/<project name>/` — if another job shares the "
                "same project name, its output files are removed too, since "
                "output is stored per project name, not per job)."
            )
            confirm_delete = st.checkbox(
                "I understand this permanently deletes the selected job(s) and their output files",
                key="confirm_bulk_delete"
            )
            if st.button("🗑️ Delete Selected", disabled=not confirm_delete):
                for job in selected_for_deletion:
                    doc_gen.delete_output(job.repo_name)
                    job_queue.delete_job(job.job_id)
                st.success(f"Deleted {len(selected_for_deletion)} job(s).")
                st.rerun()

        if any_active:
            time.sleep(2)
            st.rerun()
