# Quick Start: Odysseus Direct (5 Minutes)

## What You Need

1. **Anthropic API Key** - from https://console.anthropic.com
2. **Ollama running** - for documentation generation
3. **Python 3.10+** - on your machine

## Setup (5 minutes)

### Step 1: Install Dependencies (1 min)
```bash
cd codebase-docs
pip install -r requirements.txt
```

### Step 2: Create .env File (1 min)
```bash
cat > .env << 'EOF'
ANTHROPIC_API_KEY=sk-your-key-here
ODYSSEUS_MODEL=claude-opus-4-1
OLLAMA_API_URL=http://localhost:11434
OLLAMA_DEV_MODEL=qwen2.5-coder:7b
OLLAMA_USER_MODEL=qwen2.5-coder:7b
OUTPUT_DIR=./data/outputs
JOBS_DIR=./data/jobs
CACHE_DIR=./data/cache
UPLOAD_DIR=./data/uploads
DEBUG=true
EOF
```

### Step 3: Start Ollama (1 min)
```bash
# Terminal 1
ollama serve

# Terminal 2 (if model not installed)
ollama pull qwen2.5-coder:7b
```

### Step 4: Run App (1 min)
```bash
# Terminal 3
streamlit run app/main.py
```

### Step 5: Test (1 min)
- Open http://localhost:8501
- See "✓ Odysseus (Direct)" in sidebar
- Upload a Python file
- Watch it analyze!

**Total: ~5 minutes ✓**

---

## Usage

### Mode 1: Local File Upload (Sync)
```
1. Click "📁 Local Upload"
2. Upload .py files or ZIP
3. Wait 3-8 minutes
4. Download results
```

### Mode 2: GitHub Analysis (Async)
```
1. Click "🐙 GitHub Repository"
2. Enter: https://github.com/user/repo
3. Click "📤 Submit for Analysis"
4. Get job ID
5. Go to "📋 View Jobs" to track
6. Download when done (100%)
```

### Mode 3: Check Jobs
```
1. Click "📋 View Jobs"
2. See all analyses
3. Track progress
4. Download results
```

---

## What's Different Now?

### Before ❌
- Tried calling API at localhost:8000
- API didn't exist
- Always fell back to lightweight analysis
- No deep insights

### Now ✅
- Uses Odysseus Harness directly
- Claude provides deep analysis
- Architecture patterns detected
- Dependency graphs extracted
- Full insights generated

---

## Speed vs. Depth

### Express Mode (Fast, Lightweight)
- Time: < 1 min
- Depth: Shallow (imports, functions only)
- Uses: No Anthropic cost

### Standard Mode (Balanced) ← YOU ARE HERE
- Time: 4-8 min
- Depth: Deep (architecture, patterns, insights)
- Uses: Anthropic API (~100k tokens per analysis)

### Deep Mode (Thorough, Slow)
- Time: 10-15 min
- Depth: Very deep (all patterns, all insights)
- Uses: Anthropic API (~200k+ tokens)
- Edit: Increase `budget_tokens` in `odysseus_analysis_agent.py`

---

## Example Walkthrough

### Analyzing Flask (Flask Project)
```
1. Navigate to http://localhost:8501
2. Select "🐙 GitHub Repository"
3. Enter: https://github.com/pallets/flask
4. Enter name: "Flask"
5. Click "📤 Submit for Analysis"
6. Get ID: abc12345
7. Click "📋 View Jobs"
8. Watch progress: 0% → 100%
9. Download when complete
10. Open DEVELOPER_DOCS.html to see results
```

**Timeline:**
- 0-30s: Job queued
- 30-120s: Repository cloned & parsed
- 120-300s: Odysseus analyzes (Claude thinking)
- 300-600s: Ollama generates documentation
- 600-720s: Results ready
- **Total: ~12 minutes for large repo**

---

## Costs

### API Usage Per Analysis

| Model | Tokens | Cost |
|-------|--------|------|
| Claude Opus 4.1 | 80,000-150,000 | $1.20-2.25 |
| Claude 3.5 Sonnet | 60,000-120,000 | $0.36-0.72 |
| Claude 3 Haiku | 40,000-80,000 | $0.04-0.08 |

**Example:** Analyzing Flask repo with Sonnet = ~$0.50 per run

---

## Troubleshooting

### "Command not found: pip"
```bash
# Use python3 instead
python3 -m pip install -r requirements.txt
```

### "No module named 'odysseus'"
```bash
pip install -r requirements.txt  # Reinstall
# Or manually:
pip install odysseus-harness
```

### "ANTHROPIC_API_KEY not found"
```bash
# Check .env exists
cat .env | grep ANTHROPIC

# If missing, add it:
echo "ANTHROPIC_API_KEY=sk-your-key" >> .env

# Or export:
export ANTHROPIC_API_KEY=sk-your-key
```

### "Analysis is stuck / never completes"
```bash
# Check API quota (console.anthropic.com)
# Wait 1-2 minutes (analysis takes time)
# Check logs for "rate limit" errors
# Try with smaller codebase
```

### "Only lightweight analysis (fallback)"
```bash
# Means Odysseus failed, but app still works
# Check:
1. API key is valid
2. You have quota
3. Check console for specific error
4. Retry in a moment
```

---

## Advanced

### Change Model (Speed/Cost)
Edit `.env`:
```bash
# Fastest & cheapest
ODYSSEUS_MODEL=claude-3-haiku

# Balanced
ODYSSEUS_MODEL=claude-3.5-sonnet

# Most capable (default)
ODYSSEUS_MODEL=claude-opus-4-1
```

### Increase Analysis Depth
Edit `core/odysseus_analysis_agent.py`:
```python
harness = Harness(
    workdir=str(tmpdir_path),
    model=self.model,
    budget_tokens=400_000,  # ← Increase for deeper analysis
    max_turns=50,
)
```

### Use Only Lightweight (No API Cost)
Edit `core/odysseus_analysis_agent.py`:
```python
def analyze_deep(self, code_files, repo_name):
    # Skip Odysseus, use lightweight
    return self._lightweight_analysis(code_files, repo_name)
```

---

## Architecture at a Glance

```
Your Code
    ↓
Streamlit App
    ↓
Background Worker (async processing)
    ↓
Odysseus Harness (Python library)
    ↓
Claude (Anthropic API) ← Deep analysis here
    ↓
Results: Architecture, Patterns, Dependencies, Insights
    ↓
Ollama (Local LLM) ← Doc generation here
    ↓
Professional Documentation (MD + HTML)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `core/odysseus_analysis_agent.py` | Odysseus integration |
| `core/background_worker.py` | Async job processing |
| `core/job_queue.py` | Job management |
| `app/main.py` | Streamlit UI |
| `.env` | Configuration |

---

## Next Steps

1. ✅ Install & setup (above)
2. ✅ Test with small repo
3. ✅ Monitor first run's performance
4. ✅ Adjust model for speed/cost if needed
5. ✅ Use with larger projects

---

## Getting Help

| Need | Check |
|------|-------|
| Setup issues | This file + `.env` |
| Usage questions | `ODYSSEUS_SETUP_GUIDE.md` |
| Architecture details | `MIGRATION_TO_DIRECT_ODYSSEUS.md` |
| Troubleshooting | Scroll up ↑ |

---

## Summary

✅ **Install:** `pip install -r requirements.txt`  
✅ **Configure:** Create `.env` with your API key  
✅ **Run:** `streamlit run app/main.py`  
✅ **Test:** Upload code and watch it analyze  
✅ **Done!** Download professional docs in 4-8 minutes  

**That's it! You now have deep code analysis powered by Claude via Odysseus Harness.** 🚀
