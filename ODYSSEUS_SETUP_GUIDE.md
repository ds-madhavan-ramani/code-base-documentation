# Odysseus Harness Integration Guide

## Overview

This guide explains how the codebase-docs app now uses **Odysseus Harness** (from the Vizuara course) as a direct Python library for deep code analysis, instead of trying to call it as an API.

## Architecture

### Before (Broken)
```
Streamlit App
    ↓
BackgroundWorker
    ↓
HTTP Request → http://localhost:8000/api/analyze  ✗ (No API running)
```

### After (Working)
```
Streamlit App
    ↓
BackgroundWorker
    ↓
OdysseusAnalysisAgent
    ↓
Odysseus Harness (Direct Python Library)  ✓
```

## Installation

### Step 1: Update Dependencies

The `requirements.txt` now includes Odysseus Harness:

```bash
pip install -r requirements.txt
```

This installs `odysseus-harness` directly from the GitHub repository.

### Step 2: Set Up Environment Variables

Create a `.env` file with:

```bash
# LLM Configuration
ODYSSEUS_MODEL=claude-opus-4-1  # or claude-3.5-sonnet, etc.
ANTHROPIC_API_KEY=sk-xxx...     # Your Anthropic API key

# Ollama Configuration
OLLAMA_API_URL=http://localhost:11434
OLLAMA_DEV_MODEL=qwen2.5-coder:7b
OLLAMA_USER_MODEL=qwen2.5-coder:7b

# Storage
OUTPUT_DIR=./data/outputs
UPLOAD_DIR=./data/uploads
CACHE_DIR=./data/cache
JOBS_DIR=./data/jobs
```

**Important:** Odysseus Harness uses your Anthropic API key, not a local Ollama model for analysis. Set `ANTHROPIC_API_KEY` in your environment.

### Step 3: Start Ollama (for Documentation Generation)

Ollama is still used for generating documentation (User Guide & Developer Docs):

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Pull a model
ollama pull qwen2.5-coder:7b
```

### Step 4: Run the App

```bash
streamlit run app/main.py
```

App opens at: `http://localhost:8501`

## How It Works

### Analysis Flow

1. **User uploads code** or submits GitHub repo
2. **BackgroundWorker** processes the job
3. **OdysseusAnalysisAgent** uses Odysseus Harness to:
   - Initialize Odysseus in a temp directory with your code
   - Run Claude-based deep analysis via Odysseus
   - Extract structured insights (architecture, patterns, dependencies)
4. **Ollama** generates documentation from the analysis
5. **Results saved** to `data/outputs/`

### Speed vs. Deep Analysis

| Mode | Speed | Depth | Cost |
|------|-------|-------|------|
| **Odysseus (Default)** | 2-4 min | Deep (architecture, patterns, insights) | Uses Anthropic API |
| **Fallback (Lightweight)** | < 1 min | Shallow (imports, functions, classes) | Free (if Odysseus fails) |

**The system automatically falls back to lightweight analysis if:**
- Anthropic API is unavailable
- Rate limits hit
- Odysseus analysis fails for any reason

## Key Components

### OdysseusAnalysisAgent (`core/odysseus_analysis_agent.py`)

Uses Odysseus Harness directly to analyze code:

```python
from core.odysseus_analysis_agent import OdysseusAnalysisAgent

agent = OdysseusAnalysisAgent(model="claude-opus-4-1")
analysis = agent.analyze_deep(code_files, "my_repo")
```

**Features:**
- Direct Odysseus integration (no API needed)
- Deep architecture analysis
- Pattern detection
- Dependency extraction
- Automatic fallback to lightweight analysis

### BackgroundWorker (`core/background_worker.py`)

Processes jobs asynchronously:

1. Polls job queue every 5 seconds
2. Clones GitHub repos (if needed)
3. Runs Odysseus analysis
4. Generates documentation
5. Saves results

### JobQueue (`core/job_queue.py`)

Manages persistent job storage:

- Create, track, and update jobs
- Status: PENDING → RUNNING → COMPLETED/FAILED
- Progress monitoring (0-100%)
- Job history

## Configuration

### Model Selection

Choose your Claude model in `.env`:

```bash
# Best for deep analysis (more capable)
ODYSSEUS_MODEL=claude-opus-4-1

# Faster, cheaper
ODYSSEUS_MODEL=claude-3.5-sonnet

# Fastest, cheapest
ODYSSEUS_MODEL=claude-3-haiku
```

### Token Budget

Edit `core/odysseus_analysis_agent.py` to adjust token budget:

```python
harness = Harness(
    workdir=str(tmpdir_path),
    model=self.model,
    budget_tokens=200_000,  # ← Increase for larger codebases
    max_turns=50,
)
```

### Fallback Behavior

Lightweight analysis activates automatically when:
- Odysseus analysis fails
- Anthropic API unavailable
- Network issues

To disable Odysseus and use fallback only:

```python
# In core/odysseus_analysis_agent.py
def analyze_deep(self, code_files, repo_name):
    return self._lightweight_analysis(code_files, repo_name)
```

## Troubleshooting

### Issue: "ANTHROPIC_API_KEY not found"

**Solution:** Set your API key in `.env`:
```bash
ANTHROPIC_API_KEY=sk-your-key-here
```

Or export it:
```bash
export ANTHROPIC_API_KEY=sk-your-key-here
```

### Issue: "Analysis is slow"

**Solutions:**
- Use a faster model: `ODYSSEUS_MODEL=claude-3-haiku`
- Reduce token budget in `odysseus_analysis_agent.py`
- For large repos, implement file filtering in `code_parser.py`

### Issue: "Analysis fails for large codebases"

**Solutions:**
1. Increase token budget:
   ```python
   budget_tokens=400_000  # Up from 200_000
   ```

2. Sample files if repo is huge:
   ```python
   # In CodeParser, limit to top N files
   files = list(code_files.items())[:100]
   ```

3. Use lightweight mode only:
   ```python
   # Skip Odysseus, use fast fallback
   return self._lightweight_analysis(code_files, repo_name)
   ```

### Issue: "Rate limits hit"

**Solution:** Wait a moment before submitting more jobs. The system queues jobs and processes them sequentially to avoid rate limits.

## Performance

### Timeline for Analysis

| Stage | Duration |
|-------|----------|
| Code extraction | 5-10s |
| Odysseus analysis | 60-180s (depends on model & codebase size) |
| Documentation generation | 120-240s |
| **Total** | **3-8 minutes** |

### Token Usage

| Model | Typical Usage | Cost |
|-------|---------------|------|
| Claude Opus 4.1 | 50,000-150,000 | High accuracy |
| Claude 3.5 Sonnet | 40,000-120,000 | Balanced |
| Claude 3 Haiku | 30,000-80,000 | Cheapest |

## Advanced Usage

### Custom Analysis Prompts

Edit `_build_analysis_prompt()` in `odysseus_analysis_agent.py`:

```python
def _build_analysis_prompt(self, repo_name, code_files):
    return f"""Your custom prompt here...
    
    Repository: {repo_name}
    Files: {len(code_files)}
    """
```

### Using Odysseus Skills

The harness can load skills from the `ODYSSEUS_SKILLS_DIR`:

```python
def _build_analysis_prompt(self, repo_name, code_files):
    return """Load the /code_analysis skill and:
    
    1. Analyze architecture
    2. Check for anti-patterns
    3. Suggest improvements
    """
```

### Parallel Analysis (Advanced)

For multiple repos, modify `background_worker.py`:

```python
def _worker_loop(self):
    pending = self.job_queue.list_jobs()
    # Process multiple jobs in parallel (careful with token limits!)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(self._process_job, j) for j in pending]
```

## Combining Speed & Depth

You now have **both** in one system:

✅ **Deep Analysis** via Odysseus Harness (architecture, patterns, insights)  
✅ **Fast Fallback** via lightweight analysis (imports, functions, classes)  
✅ **Async Processing** (non-blocking UI)  
✅ **Job Persistence** (survives app restarts)  

The system automatically picks the best approach for each codebase!

## Next Steps

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Set up `.env`** with your Anthropic API key
3. **Start Ollama** for documentation generation
4. **Run the app**: `streamlit run app/main.py`
5. **Upload code** or submit a GitHub repo
6. **Watch it analyze** deeply with Odysseus!

## Support

- Check `.env` configuration
- Verify Anthropic API key is valid
- Check Ollama is running for doc generation
- Review logs for detailed errors
- See `ODYSSEUS_HARNESS_INTEGRATION.md` for older info (now outdated)

---

**Architecture:** Odysseus Harness (direct) + Ollama (docs) + Streamlit (UI)  
**Speed:** 3-8 minutes per codebase  
**Depth:** Full architecture analysis + patterns + insights  
**Reliability:** Auto-fallback to lightweight analysis if needed
