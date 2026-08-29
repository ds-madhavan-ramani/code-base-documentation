# Quick Start: Odysseus Harness Background Processing

## What's New?

Your codebase documentation system now supports **background analysis** with **Odysseus Harness** for GitHub repositories!

---

## 🚀 Quick Setup

### 1. No New Dependencies Required
All new features use existing libraries:
```bash
# Your current requirements.txt covers everything:
✅ requests
✅ streamlit
✅ markdown
✅ pathlib (stdlib)
✅ threading (stdlib)
✅ subprocess (stdlib)
```

### 2. Start the App (Same as Before)
```bash
cd codebase-docs
source venv/bin/activate
streamlit run app/main.py
```

The background worker **automatically starts** when the app loads.

---

## 💡 Three Ways to Use

### Option 1: Local File Upload (Existing)
**Best for:** Quick testing, small projects
```
1. Select "📁 Local Upload"
2. Upload files or ZIP
3. See results immediately
4. Download MD + HTML
```

### Option 2: GitHub Repository (NEW)
**Best for:** Large projects, shared repos
```
1. Select "🐙 GitHub Repository"
2. Paste: https://github.com/user/repo
3. Enter project name
4. Click "📤 Submit for Analysis"
5. Get job ID (e.g., "abc12345")
6. Analysis runs in background
```

### Option 3: View Job Progress (NEW)
**Best for:** Monitoring & downloading results
```
1. Select "📋 View Jobs"
2. See all analysis jobs
3. Watch progress 0-100%
4. Download when complete
```

---

## 📋 Example: Analyze a Real GitHub Repo

### Step 1: Submit Repository
```
Input Source: 🐙 GitHub Repository

GitHub URL:  https://github.com/vinta/awesome-python
Project Name: awesome_python

[📤 Submit for Analysis]

✅ Job submitted! ID: abc12345
🔄 Analysis running in background...
```

### Step 2: Monitor Progress
```
Input Source: 📋 View Jobs

▼ awesome_python - RUNNING (65%)
  Status:    running
  Progress:  65%
  Source:    github
```

### Step 3: Download Results
```
▼ awesome_python - COMPLETED (100%)
  Status:    completed
  Progress:  100%
  Source:    github
  ✅ Analysis Complete
  
  📄 [Download Developer Docs]
  📘 [Download User Guide]
```

---

## ⏱️ Processing Timeline

| Stage | Time | What's Happening |
|-------|------|------------------|
| 0% | Just created | Job queued |
| 20% | <1 min | Repository cloned |
| 50% | 1-3 min | Deep analysis with Odysseus |
| 80% | 2-4 min | Documentation generation |
| 100% | 4-6 min | Complete, ready to download |

**Total time:** 4-6 minutes per repository

---

## 🔧 Architecture Overview

```
You                              Your Mac
  ↓                               ↓
[Upload or GitHub URL] ────→ [Streamlit App]
                                  ↓
                          [Job Queue] (persistent)
                                  ↓
                      [Background Worker] (thread)
                                  ↓
                  ┌───────────────┼───────────────┐
                  ↓               ↓               ↓
             [GitHub Clone]  [Odysseus      [Ollama]
             [Code Parse]     Analysis]   [Generate Docs]
                  ↓               ↓               ↓
                  └───────────────┴───────────────┘
                                  ↓
                          [Save Results]
                                  ↓
              [You Download MD + HTML files]
```

---

## 📁 New Files Created

### Core Components
- `core/job_queue.py` - Job management & persistence
- `core/odysseus_harness.py` - Deep code analysis
- `core/github_client.py` - GitHub integration
- `core/background_worker.py` - Async processing

### Documentation
- `ODYSSEUS_HARNESS_INTEGRATION.md` - Full technical guide
- `QUICK_START_ODYSSEUS.md` - This file

### Modified
- `app/main.py` - Added GitHub & job tracking UI
- `tests/integration_test.py` - Updated to use .env config

---

## 🎯 Key Features

✅ **Persistent Jobs**
- Jobs survive app restarts
- Stored in `./data/jobs/`
- Complete history available

✅ **Deep Analysis**
- Odysseus Harness patterns
- Architecture insights
- Dependency graphs
- System diagrams

✅ **Non-Blocking UI**
- Submit job, get ID immediately
- Results ready when done
- No waiting in browser

✅ **GitHub Support**
- HTTPS URLs: `https://github.com/user/repo`
- Shorthand: `user/repo`
- Auto-caches cloned repos

✅ **Fallback Support**
- Odysseus unavailable? Uses lightweight analysis
- Ollama slow? Auto-retries with smaller models
- Graceful degradation throughout

---

## ⚙️ Configuration

### Environment Variables (Optional)
```bash
# Add to .env (all have defaults)
JOBS_DIR=./data/jobs              # Where jobs stored
CACHE_DIR=./data/cache            # GitHub clone cache
OUTPUT_DIR=./data/outputs         # Documentation output
ODYSSEUS_API_URL=http://localhost:8000
OLLAMA_API_URL=http://localhost:11434
```

### Default Locations
```
codebase-docs/
├── data/
│   ├── jobs/           ← Job queue storage
│   ├── cache/          ← GitHub cloned repos
│   └── outputs/        ← Generated docs
├── app/
│   └── main.py         ← Updated UI
└── core/
    ├── job_queue.py    ← NEW
    ├── odysseus_harness.py ← NEW
    ├── github_client.py    ← NEW
    └── background_worker.py ← NEW
```

---

## 🐛 Troubleshooting

### Jobs Not Processing
```bash
# Check if worker thread is running
# Look in app output for: "Background worker started"

# Check job queue
ls -la data/jobs/

# Check job status
cat data/jobs/abc12345.json
```

### GitHub Clone Fails
```
Common causes:
1. Network issue - test: curl https://github.com
2. Large repo - use smaller repo for testing
3. Rate limit - wait 1 hour and retry
```

### Slow Processing
```
Check:
1. Odysseus available: curl http://localhost:8000/health
2. Ollama responsive: curl http://localhost:11434/api/tags
3. GPU usage: ssh ubuntu "nvidia-smi"
4. Network latency: ssh ubuntu "ping -c 1 192.168.1.100"
```

---

## 💾 Job Storage Format

Each job stored as JSON:
```json
{
  "job_id": "abc12345",
  "repo_name": "my_project",
  "source_type": "github",
  "source": "https://github.com/user/repo",
  "status": "completed|running|pending|failed",
  "progress": 45,
  "created_at": "2025-08-29T10:30:00",
  "started_at": "2025-08-29T10:30:05",
  "completed_at": "2025-08-29T10:35:30",
  "analysis": { ... },
  "error": null
}
```

---

## 🔍 Testing

### 1. Local Upload (Existing - Still Works)
```bash
streamlit run app/main.py
# Select "📁 Local Upload"
# Upload test files
# Should complete immediately ✅
```

### 2. GitHub Integration (New)
```bash
streamlit run app/main.py
# Select "🐙 GitHub Repository"
# Submit: https://github.com/torvalds/linux
# Should show progress ✅
```

### 3. Job Tracking (New)
```bash
streamlit run app/main.py
# Select "📋 View Jobs"
# Should show all submitted jobs ✅
```

---

## 🚦 Job Status Flow

```
User Submits Job
      ↓
[PENDING] ← Waiting in queue
      ↓
[RUNNING] ← Background worker processing
      ↓ (Success)
[COMPLETED] ← Results saved, downloadable
      
      ↓ (Error)
[FAILED] ← Error logged, user notified
```

---

## 📊 Monitoring

### View Active Jobs
```bash
ls -la data/jobs/
# Shows: abc12345.json, def67890.json, ...
```

### View Job Details
```bash
cat data/jobs/abc12345.json | jq '.status, .progress'
```

### Monitor Output
```bash
ls -la data/outputs/my_project/
# Shows: DEVELOPER_DOCS.md, USER_GUIDE.md, .html files
```

---

## 🔐 Security Notes

✅ Safe by default:
- GitHub URLs only (no SSH keys needed)
- Repos cloned to isolated cache
- No credentials stored
- Analysis sandboxed
- Output files local only

---

## ⚡ Performance Tips

1. **First time:** Allow 5-10 minutes
   - GitHub clone is slower on first run
   - Subsequent runs use cached repo

2. **Large repos:** Use main branch only
   - `--depth=1` cloning saves time
   - Full history not needed

3. **Multiple repos:** Submit one at a time
   - Worker processes sequentially
   - Queue shows order

4. **Production repos:** Add GitHub token
   - Avoid rate limiting
   - Use PAT in future version

---

## 📞 Support

For issues or questions:

1. **Check logs:** `streamlit run app/main.py --logger.level=debug`
2. **Check jobs:** `cat data/jobs/*.json | jq .`
3. **Check services:** 
   - Ollama: `curl http://localhost:11434/api/tags`
   - Odysseus: `curl http://localhost:8000/health`

See `ODYSSEUS_HARNESS_INTEGRATION.md` for detailed documentation.

---

## 🎉 You're Ready!

Your system now has:
- ✅ Local file upload (existing)
- ✅ GitHub repository analysis (NEW)
- ✅ Background job processing (NEW)
- ✅ Job progress tracking (NEW)
- ✅ Deep Odysseus analysis (NEW)

**Start by:** `streamlit run app/main.py`

Then:
1. Try "🐙 GitHub Repository"
2. Submit: `https://github.com/pallets/flask`
3. Watch progress in "📋 View Jobs"
4. Download results when done!
