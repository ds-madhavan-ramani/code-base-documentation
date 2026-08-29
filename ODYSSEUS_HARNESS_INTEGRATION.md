# Odysseus Harness Background Processing Integration

## Overview

This document describes the new **Odysseus Harness Background Processing** system that enables deep code analysis when users upload codebases or submit GitHub repositories.

---

## Architecture

```
┌─────────────────────────────────────┐
│    Streamlit Web UI (main.py)       │
│  ┌─────────────┬─────────────────┐  │
│  │Local Upload │ GitHub Analysis │  │
│  │Job Tracking │                 │  │
│  └─────────────┴─────────────────┘  │
└────────────────┬────────────────────┘
                 │
        ┌────────▼────────┐
        │   Job Queue     │  (persistent)
        │ (job_queue.py)  │
        └────────┬────────┘
                 │
        ┌────────▼─────────────┐
        │ Background Worker    │  (threaded)
        │background_worker.py  │
        └────────┬─────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───▼────────┐        ┌──────▼──────┐
│ Odysseus   │        │GitHub Client│
│ Harness    │        │github_client│
│odysseus    │        │   .py       │
│_harness.py │        └─────────────┘
└────────────┘
```

---

## New Components

### 1. **job_queue.py** - Persistent Job Management
```python
JobQueue
├── create_job(repo_name, source_type, source)
├── get_job(job_id)
├── update_job(job_id, status, progress, analysis)
├── list_jobs(repo_name)
└── Storage: ./data/jobs/*.json
```

**Features:**
- Persistent job storage (survives app restarts)
- Status tracking (PENDING → RUNNING → COMPLETED/FAILED)
- Progress monitoring (0-100%)
- Error logging
- Job history

### 2. **odysseus_harness.py** - Deep Code Analysis
```python
OdysseusHarness
├── health_check()
├── analyze_deep(code_files, repo_name)
├── generate_system_diagram(analysis)
└── batch_analyze(codebases)
```

**Capabilities:**
- Deep architecture pattern analysis
- Dependency graph generation
- Code metrics & health
- Security insights
- Performance patterns
- System diagram generation (Mermaid)
- Fallback to lightweight analysis if unavailable

### 3. **github_client.py** - GitHub Integration
```python
GitHubClient
├── clone_repository(repo_url)
├── get_repo_info(repo_path)
├── cleanup_cache(max_age_days)
└── is_github_url(url)
```

**Features:**
- Clone repositories with `--depth=1` (faster)
- Cache cloned repos for reuse
- Extract repository metadata
- Auto-cleanup of old caches
- Support for HTTPS URLs and shorthand (user/repo)

### 4. **background_worker.py** - Async Processing
```python
BackgroundWorker
├── start()
├── stop()
├── _worker_loop()
├── _process_job(job)
├── _get_github_code()
├── _generate_dev_docs()
└── _generate_user_docs()
```

**Workflow:**
1. Polls job queue every 5 seconds
2. Processes PENDING jobs
3. Runs Odysseus deep analysis
4. Generates documentation
5. Saves results to disk
6. Updates job status

---

## Workflow: Complete Pipeline

### Local File Upload (Synchronous - Current)
```
User Upload Files
    ↓
Code Parser extracts structure
    ↓
Odysseus analyzes
    ↓
LLM generates docs
    ↓
Results shown & downloadable
```

### GitHub Repository (Asynchronous - NEW)
```
User submits GitHub URL
    ↓
Job created in queue (ID returned)
    ↓
Background worker processes:
    ├─ Clone repository
    ├─ Extract code files
    ├─ Run Odysseus deep analysis
    ├─ Generate system diagram
    ├─ Generate documentation
    └─ Save results
    ↓
User views progress in "View Jobs"
    ↓
When done: Download documentation
```

---

## UI Changes

### New Input Modes
```
Input Source:
  ○ 📁 Local Upload       (existing)
  ○ 🐙 GitHub Repository  (NEW)
  ○ 📋 View Jobs          (NEW)
```

### GitHub Repository Mode
```
GitHub URL input:  https://github.com/user/repo
Project Name:      my_project

[📤 Submit for Analysis]

✅ Job submitted! ID: abc12345
🔄 Analysis running in background...
```

### View Jobs Mode
```
Analysis Jobs

▼ my_project - RUNNING (45%)
  Status:    running
  Progress:  45%
  Source:    github

▼ another_project - COMPLETED (100%)
  Status:    completed
  Progress:  100%
  Source:    github
  ✅ Analysis Complete
  📊 Analysis Results
  📄 [Download Developer Docs]
  📘 [Download User Guide]
```

---

## Configuration

### Environment Variables
```bash
# Add to .env
JOBS_DIR=./data/jobs              # Job storage location
CACHE_DIR=./data/cache            # GitHub clone cache
OUTPUT_DIR=./data/outputs         # Documentation output
ODYSSEUS_API_URL=http://localhost:8000
OLLAMA_API_URL=http://localhost:11434
```

### Job Storage Structure
```
data/jobs/
├── abc12345.json    # Job metadata & results
├── def67890.json
└── ghi13579.json
```

### Job File Format
```json
{
  "job_id": "abc12345",
  "repo_name": "my_project",
  "source_type": "github",
  "source": "https://github.com/user/repo",
  "status": "completed",
  "progress": 100,
  "created_at": "2025-08-29T10:30:00",
  "started_at": "2025-08-29T10:30:05",
  "completed_at": "2025-08-29T10:35:30",
  "analysis": { ... },
  "error": null,
  "results": { ... }
}
```

---

## Performance & Monitoring

### Background Worker
- **Polling interval:** 5 seconds
- **Max jobs in queue:** Unlimited
- **Job processing:** Sequential (one at a time)
- **Timeout:** 5 minutes per job

### Progress Tracking
```
Job Progress Stages:
  0%   → Job created
  20%  → Code files extracted
  50%  → Deep analysis complete
  80%  → Documentation generated
  100% → Results saved
```

### Error Handling
```
If GitHub clone fails:
  → Status: FAILED
  → Error: "Git clone failed: ..."
  → Job remains in queue for retry

If Odysseus unavailable:
  → Fallback to lightweight analysis
  → Continue with LLM generation
  → Status: COMPLETED (with note)

If LLM generation fails:
  → Status: FAILED
  → Error logged
  → Job remains in queue
```

---

## Usage Examples

### Example 1: Submit GitHub Repo
```python
# Via UI
1. Go to "🐙 GitHub Repository" tab
2. Enter: https://github.com/pytorch/pytorch
3. Enter: PyTorch
4. Click "📤 Submit for Analysis"
5. Get: Job ID "abc12345"
6. Go to "📋 View Jobs" to monitor
```

### Example 2: Manual Job Creation
```python
from core.job_queue import JobQueue
from core.github_client import GitHubClient

job_queue = JobQueue()
job = job_queue.create_job(
    repo_name="pytorch",
    source_type="github",
    source="https://github.com/pytorch/pytorch"
)
print(f"Job created: {job.job_id}")
```

### Example 3: Check Job Status
```python
job = job_queue.get_job("abc12345")
print(f"Status: {job.status}")
print(f"Progress: {job.progress}%")
print(f"Analysis: {job.analysis}")
```

---

## Integration with Existing Code

### Backward Compatibility
- ✅ Local file upload still works (unchanged)
- ✅ Existing prompts used
- ✅ Documentation format unchanged
- ✅ Download buttons work same way

### New Dependencies
None additional! Uses only:
- `requests` (already installed)
- `subprocess` (stdlib)
- `threading` (stdlib)
- `pathlib` (stdlib)

---

## Future Enhancements

### Planned Features
- [ ] Database backend (replace JSON files)
- [ ] API endpoints for external job submission
- [ ] Email notifications on completion
- [ ] Webhook support for CI/CD integration
- [ ] Job cancellation
- [ ] Batch analysis (multiple repos)
- [ ] Caching layer (avoid re-analysis)
- [ ] Advanced filtering in job view
- [ ] Real-time job progress via WebSocket
- [ ] Job scheduling (run analysis on schedule)

### Performance Improvements
- [ ] Parallel job processing (multiple workers)
- [ ] Analysis caching
- [ ] Incremental re-analysis (only changed files)
- [ ] Model warming (preload models)
- [ ] Connection pooling

---

## Testing the Integration

### 1. Test Local Upload (Existing)
```bash
streamlit run app/main.py
# Upload code files
# Should work exactly as before ✅
```

### 2. Test GitHub Integration
```bash
streamlit run app/main.py
# Go to "🐙 GitHub Repository"
# Submit: https://github.com/vinta/awesome-python
# Go to "📋 View Jobs"
# Watch progress update
```

### 3. Test Job Queue
```python
from core.job_queue import JobQueue
job_queue = JobQueue()
jobs = job_queue.list_jobs()
for job in jobs:
    print(f"{job.repo_name}: {job.status} ({job.progress}%)")
```

### 4. Test Background Worker
```python
from core.background_worker import BackgroundWorker
# Worker auto-starts when app loads
# Check logs for processing messages
```

---

## Troubleshooting

### Jobs Not Processing
```
Check:
1. Background worker thread is running
   → Look for "Background worker started" in logs
2. Job queue has pending jobs
   → python: from core.job_queue import JobQueue
   → job_queue.list_jobs()  # filter by status
3. Odysseus Harness is available (or fallback works)
   → curl http://localhost:8000/health
```

### GitHub Clone Fails
```
Common issues:
1. Network connectivity
   → Check: curl https://github.com
2. Large repository (>1GB)
   → Use --depth=1 cloning (already done)
3. SSH key required
   → Use HTTPS URLs instead of SSH
4. Rate limiting
   → Wait & retry or use GitHub token
```

### Analysis Takes Too Long
```
Optimization:
1. Use smaller repositories for testing
2. Check Odysseus/Ollama GPU usage
3. Monitor: nvidia-smi on Ubuntu server
4. Increase job timeout in background_worker.py
```

---

## Monitoring Checklist

- [ ] Background worker is running
- [ ] Job queue directory exists and has write permissions
- [ ] Odysseus Harness accessible (or fallback working)
- [ ] Ollama models cached and ready
- [ ] Output directory has space for results
- [ ] GitHub clone cache doesn't grow unbounded
- [ ] Job processing errors logged properly

---

## Migration Guide (From Old System)

No migration needed! The new system:
- ✅ Coexists with local upload
- ✅ Uses same output format
- ✅ Compatible with existing documentation
- ✅ Doesn't require database migration
- ✅ Can be disabled by removing GitHub tab

To disable GitHub integration temporarily:
```python
# In app/main.py
input_mode = st.sidebar.radio("Input Source", ["📁 Local Upload"])
# Remove "🐙 GitHub Repository" and "📋 View Jobs"
```

---

## Support & Debugging

### View Background Worker Logs
```bash
# Terminal 1: Run app with debug logging
DEBUG=true streamlit run app/main.py

# Terminal 2: Monitor job queue
watch -n 5 'ls -la data/jobs/ | tail -10'

# Terminal 3: Monitor outputs
watch -n 5 'ls -la data/outputs/ | tail -10'
```

### Manual Job Analysis
```python
from core.job_queue import JobQueue
from core.odysseus_harness import OdysseusHarness

job_queue = JobQueue()
job = job_queue.get_job("abc12345")
print(job.to_dict())

# Or run Odysseus analysis directly
odysseus = OdysseusHarness()
analysis = odysseus.analyze_deep(code_files, "test_repo")
```

---

## Version History

- **v1.0** (Current)
  - Background job processing
  - GitHub repository integration
  - Odysseus Harness deep analysis
  - Job tracking UI

---

## Questions?

Refer to:
- `AGENTS.md` - System architecture
- `PROJECT_SUMMARY_FOR_CLAUDE_CODE.md` - Project overview
- `CLAUDE_CODE.md` - Setup instructions
