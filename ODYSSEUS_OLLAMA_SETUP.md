# Odysseus Harness with Local Ollama Models

## Overview

This guide explains how to use **Odysseus Harness with open-source models from Ollama** for entirely local code analysis — no API keys, no internet required!

## Architecture

```
Your Code
    ↓
Streamlit App
    ↓
BackgroundWorker (async processing)
    ↓
Odysseus Harness
    ↓
Custom Ollama Provider ← Uses local Ollama models
    ↓
Ollama API (localhost:11434)
    ↓
Local Models (Qwen, Mistral, Llama, etc.) ✓ FULLY LOCAL
    ↓
Deep Analysis Results
    ↓
More Ollama (docs generation)
    ↓
Professional Documentation (all local)
```

## Prerequisites

You need **Ollama running locally** with at least one capable model:

### Recommended Models

| Model | Size | Speed | Capability | Best For |
|-------|------|-------|-----------|----------|
| **qwen2.5-coder:32b** | 20GB | 1-2 tok/s | ⭐⭐⭐⭐⭐ | Best analysis (if you have GPU) |
| **qwen2.5-coder:7b** | 4.7GB | 3-5 tok/s | ⭐⭐⭐⭐ | Good balance |
| **mistral:latest** | 4.1GB | 5-10 tok/s | ⭐⭐⭐ | Fast, decent |
| **llama2:latest** | 3.8GB | 5-10 tok/s | ⭐⭐⭐ | Good fallback |

**Recommended**: `qwen2.5-coder` (optimized for code understanding)

## Installation

### Step 1: Install Ollama

Download from https://ollama.ai

```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Then start it
ollama serve
```

### Step 2: Pull Model(s)

```bash
# In another terminal
ollama pull qwen2.5-coder:7b

# Or for higher quality (if you have GPU with 8GB+ VRAM):
ollama pull qwen2.5-coder:32b

# Optional: Pull other models
ollama pull mistral
ollama pull llama2
```

### Step 3: Update Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

Create `.env`:

```bash
# Odysseus model (must be installed in Ollama)
ODYSSEUS_MODEL=qwen2.5-coder:7b

# Ollama API endpoint
OLLAMA_API_URL=http://localhost:11434

# Ollama models for documentation
OLLAMA_DEV_MODEL=qwen2.5-coder:7b
OLLAMA_USER_MODEL=qwen2.5-coder:7b

# Storage
OUTPUT_DIR=./data/outputs
JOBS_DIR=./data/jobs
CACHE_DIR=./data/cache
UPLOAD_DIR=./data/uploads

# Optional
DEBUG=true
```

### Step 5: Run the App

```bash
streamlit run app/main.py
```

**That's it!** Everything is local and offline.

---

## Usage

### Mode 1: Upload Local Files
```
1. Open http://localhost:8501
2. Click "📁 Local Upload"
3. Upload Python/JavaScript files or ZIP
4. Wait 4-10 minutes for deep analysis
5. Download results
```

### Mode 2: Analyze GitHub Repos
```
1. Click "🐙 GitHub Repository"
2. Enter: https://github.com/user/repo
3. Click "📤 Submit for Analysis"
4. Get job ID
5. Click "📋 View Jobs" to track (offline analysis)
6. Download when complete
```

### Mode 3: Track Jobs
```
1. Click "📋 View Jobs"
2. See all analyses
3. Monitor progress
4. Download results
```

---

## Model Selection

### For Best Quality (Needs GPU)
```bash
ODYSSEUS_MODEL=qwen2.5-coder:32b
```
- Time: 8-15 minutes per repo
- Quality: Excellent (state-of-art reasoning)
- GPU: Need 24GB+ VRAM
- Cost: None (fully local)

### For Balanced Performance (Recommended)
```bash
ODYSSEUS_MODEL=qwen2.5-coder:7b
```
- Time: 5-10 minutes per repo
- Quality: Very good
- GPU: Need 8GB+ VRAM (or use CPU)
- Cost: None (fully local)

### For Fast Analysis
```bash
ODYSSEUS_MODEL=mistral:latest
```
- Time: 3-7 minutes per repo
- Quality: Good
- GPU: Works on 4GB+ VRAM
- Cost: None (fully local)

### Switch Models Dynamically
```bash
# Just change .env and restart app
ODYSSEUS_MODEL=llama2:latest
```

---

## How It Works

### Analysis Pipeline

1. **Code Extraction** (5-10s)
   - Upload files or clone from GitHub
   - Extract code structure

2. **Odysseus Analysis** (60-300s)
   - Initialize Odysseus harness
   - Uses custom Ollama provider
   - Claude-equivalent reasoning with open-source model
   - Extracts architecture, patterns, dependencies

3. **Doc Generation** (60-240s)
   - Takes analysis results
   - Generates documentation with Ollama
   - Creates both Markdown and HTML

4. **Save Results** (5-10s)
   - Store to `data/outputs/`
   - Ready to download

### Deep Analysis Features

With Odysseus + Ollama, you get:

✅ **Architecture Analysis** - System design and structure  
✅ **Pattern Detection** - Design patterns and best practices  
✅ **Dependency Graphs** - Component relationships  
✅ **Data Flow** - How information moves through system  
✅ **Code Metrics** - File counts, lines, complexity  
✅ **Key Insights** - Strengths, issues, technical highlights  

All computed **locally on your machine** with open-source models!

---

## Custom Providers (Advanced)

The `odysseus_ollama_provider.py` is a custom provider that makes Odysseus work with Ollama instead of Gemini/Anthropic.

### What It Does
- Translates between Odysseus's message format and Ollama's API
- Handles tool calls (even though Ollama doesn't support them well)
- Manages timeouts and retries
- Provides health checks and model listing

### If You Want to Use Another Provider

Create a new provider file (e.g., `odysseus_custom_provider.py`):

```python
import odysseus.provider as provider_module

# Your custom complete() function
def complete(model: str, system: str, messages: list[dict], tools: list[dict]) -> dict:
    # Your implementation
    return {"text": ..., "tool_calls": [], "usage": {...}}

# Inject into Odysseus
provider_module.complete = complete
provider_module.DEFAULT_MODEL = "your-model"
```

Then in `odysseus_analysis_agent.py`:
```python
from core.odysseus_custom_provider import complete
import odysseus.provider as provider_module
provider_module.complete = complete
```

---

## Performance & Timing

### Typical Timeline (qwen2.5-coder:7b)

| Stage | Duration | CPU | GPU |
|-------|----------|-----|-----|
| Code extraction | 5-10s | Yes | Yes |
| Odysseus analysis | 60-180s | ✓ Yes | ✓ Faster |
| Doc generation | 60-120s | ✓ Yes | ✓ Faster |
| File I/O | 5-10s | Yes | - |
| **Total** | **2-5 min** | ~ | ~ |

### With Larger Models (qwen2.5-coder:32b)

| Stage | Duration | Needs GPU |
|-------|----------|-----------|
| Code extraction | 5-10s | No |
| Odysseus analysis | 180-360s | Yes (24GB+) |
| Doc generation | 120-240s | Yes |
| File I/O | 5-10s | No |
| **Total** | **5-10 min** | Yes |

### GPU vs. CPU

**With GPU (NVIDIA/AMD):**
- Setup: `ollama serve` automatically uses GPU
- Speed: 2-5x faster
- Memory: GPU VRAM must fit model

**Without GPU (CPU only):**
- Setup: Just works (slower)
- Speed: 10-30 tok/s (slower)
- Memory: RAM must fit model (~2-3x model size)

---

## Troubleshooting

### "Cannot connect to Ollama at http://localhost:11434"

**Solution:**
```bash
# Make sure Ollama is running
ollama serve

# Check it's working
curl http://localhost:11434/api/tags

# If not installed:
# Download from https://ollama.ai
```

### "Model 'qwen2.5-coder:7b' not found in Ollama"

**Solution:**
```bash
# Pull the model
ollama pull qwen2.5-coder:7b

# Or list available models
ollama list
```

### "Analysis is very slow (< 1 token/second)"

**Causes & Solutions:**
1. Using CPU instead of GPU
   - Verify: `nvidia-smi` shows VRAM usage
   - Fix: Install NVIDIA driver or use smaller model

2. Model too large for your hardware
   - Current: `qwen2.5-coder:32b`
   - Fix: `ollama pull qwen2.5-coder:7b`

3. Not enough RAM
   - Models need 2-3x their size in RAM
   - Fix: Use smaller model

### "Out of Memory Error"

**Solution:**
1. Stop Ollama: `kill ollama`
2. Use smaller model:
   ```bash
   ODYSSEUS_MODEL=mistral:latest
   ```
3. Reduce context: Edit `odysseus_analysis_agent.py`:
   ```python
   budget_tokens=50_000  # was 100_000
   ```

### "Analysis gives nonsensical results"

**Solution:**
1. Try better model:
   ```bash
   ollama pull qwen2.5-coder:32b
   # Update .env: ODYSSEUS_MODEL=qwen2.5-coder:32b
   ```

2. Improve prompts: Edit `_build_analysis_prompt()` in `odysseus_analysis_agent.py`

3. Check Ollama logs:
   ```bash
   # Ollama window shows detailed logs
   ```

---

## Comparison: Ollama vs. Cloud APIs

| Aspect | Ollama (Local) | Anthropic | Gemini | Ollama |
|--------|---|---|---|---|
| **Privacy** | ✓ 100% local | ✗ Cloud | ✗ Cloud | ✓ |
| **Cost** | ✓ Free | ✗ ~$1-2 per | ✗ ~$1 per | ✓ |
| **Speed** | Varies | ⚡ Very fast | ⚡ Very fast | Variable |
| **Quality** | ⭐⭐⭐-⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐-⭐⭐⭐⭐ |
| **Setup** | Simple | Easy | Easy | Simple |
| **Offline** | ✓ Yes | ✗ No | ✗ No | ✓ Yes |
| **Latency** | 100-1000ms | 500-2000ms | 500-2000ms | 100-1000ms |

---

## Best Practices

### 1. Pick Right Model for Your Hardware

```bash
# Check available RAM
free -h  # Linux
vm_stat  # macOS

# Pick model accordingly:
# 8GB RAM → qwen2.5-coder:7b or mistral
# 16GB RAM → qwen2.5-coder:7b (faster) or 32b (better)
# 32GB+ RAM → qwen2.5-coder:32b
```

### 2. Keep Models Fresh

```bash
# Update Ollama
ollama list  # See what you have
ollama pull qwen2.5-coder:7b --latest
```

### 3. Monitor Performance

```bash
# In separate terminal during analysis
watch -n 1 'ollama list'

# Check GPU usage (if available)
nvidia-smi -l 1  # NVIDIA GPU
```

### 4. Parallel Codebase Analysis (Advanced)

Edit `background_worker.py` to process multiple jobs:

```python
# Currently processes 1 job at a time
# To process 2 in parallel:
from concurrent.futures import ThreadPoolExecutor

max_workers = 2  # Adjust based on model memory
```

---

## Next Steps

1. ✅ Install Ollama from https://ollama.ai
2. ✅ Pull a model: `ollama pull qwen2.5-coder:7b`
3. ✅ Create `.env` (see above)
4. ✅ Install Python deps: `pip install -r requirements.txt`
5. ✅ Start app: `streamlit run app/main.py`
6. ✅ Upload code and watch it analyze locally!

---

## Key Files

| File | Purpose |
|------|---------|
| `core/odysseus_ollama_provider.py` | Custom Ollama provider for Odysseus |
| `core/odysseus_analysis_agent.py` | Analysis agent using Odysseus + Ollama |
| `core/background_worker.py` | Async job processing |
| `core/job_queue.py` | Job management |
| `app/main.py` | Streamlit UI |

---

## Summary

✅ **Fully local** - No cloud APIs, no internet needed  
✅ **Private** - Your code never leaves your machine  
✅ **Free** - No API costs  
✅ **Fast** - With GPU, can be as fast as cloud APIs  
✅ **Flexible** - Easy to swap models  
✅ **Deep analysis** - Full Odysseus + Claude-level reasoning with open-source models  

**Everything runs on your machine. Complete control. Zero dependencies on external services.** 🚀
