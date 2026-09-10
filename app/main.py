import streamlit as st
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
from utils.prompts import (
    DEV_DOCS_TIER1_SECTIONS,
    DEV_DOCS_TAIL_SECTIONS,
    USER_DOCS_HEAD_SECTIONS,
    USER_DOCS_TAIL_SECTIONS,
    build_doc_context,
    build_sectioned_doc,
    select_significant_files,
    identify_features,
    build_feature_map_section,
    build_file_walkthrough_sections,
    build_user_feature_sections,
)

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

        # Cache the (expensive, multi-turn) Odysseus analysis in session state so
        # unrelated reruns — e.g. clicking the Document Type radio below — don't
        # silently re-trigger it. Only repo_name or a new upload invalidates it.
        analysis_cache_key = f"{repo_name}::{len(code_files)}::{sum(len(c) for c in code_files.values())}"
        if st.session_state.get("_analysis_cache_key") != analysis_cache_key:
            with st.spinner("🧠 Analyzing with Odysseus..."):
                st.session_state["_analysis_result"] = odysseus.analyze_deep(code_files, repo_name)
            st.session_state["_analysis_cache_key"] = analysis_cache_key
        analysis = st.session_state["_analysis_result"]

        if analysis.get("fallback"):
            st.warning("⚠️ Odysseus not responding - using fallback analysis")
        else:
            st.success("✓ Deep analysis complete")

        doc_type_label = st.radio(
            "Document Type", list(DOC_TYPE_OPTIONS.keys()), horizontal=True
        )
        doc_type = DOC_TYPE_OPTIONS[doc_type_label]

        if st.button("🚀 Generate Documentation"):
            progress = st.progress(0)
            status_line = st.empty()

            doc_context = build_doc_context(analysis)
            doc_context["file_tree"] = file_tree  # richer tree from CodeParser than analysis's own

            status_line.caption("🔍 Extracting real per-file structure...")
            file_structures = parser.build_file_structures(code_files)
            significant_files = select_significant_files(
                code_files, file_structures, key_modules=analysis.get("key_modules")
            )

            status_line.caption("🔍 Identifying real features...")
            features = identify_features(ollama, DEV_MODEL, doc_context, significant_files, file_structures)

            want_dev = doc_type in ("both", "dev")
            want_user = doc_type in ("both", "user")
            sections_total = 0
            if want_dev:
                sections_total += len(DEV_DOCS_TIER1_SECTIONS) + 1 + len(significant_files) + len(DEV_DOCS_TAIL_SECTIONS)
            if want_user:
                sections_total += len(USER_DOCS_HEAD_SECTIONS) + len(features) + len(USER_DOCS_TAIL_SECTIONS)
            done = {"n": 0}

            def report(label, index, total, title):
                done["n"] += 1
                progress.progress(10 + int(80 * done["n"] / sections_total) if sections_total else 90)
                status_line.caption(f"🔄 {label} — {index}/{total}: {title}")

            progress.progress(10)

            dev_docs = None
            if want_dev:
                tier1 = build_sectioned_doc(
                    ollama, DEV_MODEL, DEV_DOCS_TIER1_SECTIONS, doc_context, context_length=8192,
                    on_section=lambda i, t, title: report("Developer docs", i, t, title)
                )
                feature_map = build_feature_map_section(ollama, DEV_MODEL, doc_context, features, context_length=8192)
                report("Developer docs", 1, 1, "Feature -> File Map")
                walkthroughs = build_file_walkthrough_sections(
                    ollama, DEV_MODEL, code_files, file_structures, significant_files, doc_context,
                    context_length=8192,
                    on_file=lambda i, t, filename: report("Developer docs — file walkthrough", i, t, filename)
                )
                tail = build_sectioned_doc(
                    ollama, DEV_MODEL, DEV_DOCS_TAIL_SECTIONS, doc_context, context_length=8192,
                    on_section=lambda i, t, title: report("Developer docs", i, t, title)
                )
                dev_body = "\n\n".join([
                    tier1,
                    "## Feature → File Map\n\n" + feature_map,
                    "## Per-File Code Walkthrough\n\n" + walkthroughs,
                    tail,
                ])
                dev_docs = f"# Developer Documentation: {doc_context['repo_name']}\n\n{dev_body}"

            user_docs = None
            if want_user:
                head = build_sectioned_doc(
                    ollama, USER_MODEL, USER_DOCS_HEAD_SECTIONS, doc_context, context_length=4096,
                    on_section=lambda i, t, title: report("User guide", i, t, title)
                )
                feature_sections = build_user_feature_sections(
                    ollama, USER_MODEL, doc_context, features, context_length=4096,
                    on_feature=lambda i, t, name: report("User guide — feature", i, t, name)
                )
                user_tail = build_sectioned_doc(
                    ollama, USER_MODEL, USER_DOCS_TAIL_SECTIONS, doc_context, context_length=4096,
                    on_section=lambda i, t, title: report("User guide", i, t, title)
                )
                user_body = "\n\n".join([
                    head,
                    "## Features & How to Use Them\n\n" + feature_sections,
                    user_tail,
                ])
                user_docs = f"# User Guide: {doc_context['repo_name']}\n\n{user_body}"

            status_line.caption("💾 Saving documentation...")
            saved_dir = doc_gen.save_documentation(repo_name, dev_docs, user_docs, analysis)
            progress.progress(100)
            status_line.caption("✅ Done")

            st.success(f"✅ Documentation generated successfully! Saved to `{saved_dir}`")

            if dev_docs:
                st.markdown("### Preview: Developer Docs")
                st.markdown(dev_docs[:1000] + "...\n\n*[Full documentation saved]*")

            if user_docs:
                st.markdown("### Preview: User Guide")
                st.markdown(user_docs[:1000] + "...\n\n*[Full documentation saved]*")

            # Download buttons
            st.markdown("### 📥 Download Documentation")
            for output_file in doc_gen.list_output_files(repo_name):
                with open(output_file, "rb") as f:
                    st.download_button(
                        f"⬇️ {output_file.name}",
                        f.read(),
                        output_file.name,
                        key=f"local_dl_{output_file.name}"
                    )

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
                repo_name, "github", repo_url, doc_type=DOC_TYPE_OPTIONS[doc_type_label]
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
