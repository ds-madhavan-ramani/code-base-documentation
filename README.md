# 🔍 Codebase Documentation Generator with Odysseus Harness

> Automatically generate professional documentation for any codebase using AI-powered analysis and deep code understanding.

[![GitHub](https://img.shields.io/badge/github-ds--madhavan--ramani-blue?logo=github)](https://github.com/ds-madhavan-ramani/code-base-documentation)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.37.0-red)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)

---

## 📋 Table of Contents

- [Problem](#problem)
- [Solution](#solution)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)
- [Future Roadmap](#future-roadmap)

---

## 🎯 Problem

**Challenge:** Developers spend significant time creating and maintaining code documentation manually. This is:
- ⏱️ **Time-consuming** - Manual documentation takes hours per project
- 📝 **Error-prone** - Docs get outdated as code changes
- 🔄 **Repetitive** - Same analysis for similar code patterns
- 💸 **Expensive** - Requires dedicated documentation engineers

**Need:** An automated system that generates professional, accurate documentation for any codebase with minimal effort.

---

## ✨ Solution

**Codebase Documentation Generator** is an AI-powered system that:

1. **Analyzes your code** using advanced pattern recognition
2. **Extracts structure** (functions, classes, dependencies, architecture)
3. **Performs deep analysis** with Odysseus Harness for insights
4. **Generates documentation** using state-of-the-art LLMs (Ollama)
5. **Produces multiple formats** (Markdown + HTML with styling)

### What You Get

```
Your Codebase
    ↓
[Parser] → Extract structure, functions, classes, imports
    ↓
[Odysseus] → Deep architecture analysis, patterns, dependencies
    ↓
[Ollama LLM] → Generate professional documentation
    ↓
[Output] → Developer Docs + User Guide (MD + HTML)
```

**Result:** Professional documentation in 4-7 minutes! 📊

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────┐
│         Streamlit Web Interface (main.py)           │
│  ┌──────────────────┬─────────────┬──────────────┐  │
│  │ Local Upload     │ GitHub      │ View Jobs    │  │
│  │ (Sync Mode)      │ Repository  │ (Track      │  │
│  │                  │ (Async Mode)│ Progress)   │  │
│  └──────────────────┴─────────────┴──────────────┘  │
└────────────────────────┬────────────────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │      Job Queue System          │
         │   (Persistent JSON Storage)    │
         └───────────────┬────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │    Background Worker Thread    │
         │   (Async Job Processing)       │
         └─┬────────────────────────────┬─┘
           │                            │
    ┌──────▼──────┐            ┌───────▼──────┐
    │ GitHub      │            │  Odysseus    │
    │ Client      │            │  Harness     │
    │ (Cloning)   │            │  (Analysis)  │
    └──────┬──────┘            └───────┬──────┘
           │                           │
           └───────────────┬───────────┘
                           │
                   ┌───────▼────────┐
                   │  Code Parser   │
                   │  (Extraction)  │
                   └────────┬───────┘
                            │
                   ┌────────▼─────────┐
                   │  Ollama LLM      │
                   │  (Generation)    │
                   └────────┬─────────┘
                            │
                   ┌────────▼─────────────┐
                   │  Save Results       │
                   │  (MD + HTML + JSON) │
                   └─────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Streamlit 1.37.0 | Web interface & real-time updates |
| **LLM** | Ollama (Qwen3, Mistral) | Text generation & analysis |
| **Code Analysis** | Odysseus Harness | Deep architecture analysis |
| **Parsing** | Tree-sitter | Code structure extraction |
| **Templates** | Jinja2 | Dynamic prompt generation |
| **Version Control** | Git | Repository management |

---

## 🎨 Features

### ✅ Core Features

- **🏠 Local Upload Mode**
  - Upload files or ZIP archives
  - Instant processing & results
  - Download immediately

- **🐙 GitHub Integration** (NEW)
  - Submit any public GitHub repository
  - Automatic cloning with caching
  - Support for HTTPS URLs & shorthand (user/repo)

- **📊 Deep Analysis**
  - Architecture pattern detection
  - Dependency graph extraction
  - Code metrics & health analysis
  - System diagram generation (Mermaid)

- **📚 Multi-Format Output**
  - Developer Documentation (technical deep-dive)
  - User Guide (beginner-friendly)
  - Both in Markdown + styled HTML
  - Complete metadata in JSON

- **🔄 Background Processing**
  - Non-blocking async job queue
  - Real-time progress tracking
  - Job persistence (survive app restarts)
  - Complete job history

### ✨ Advanced Features

- **Graceful Degradation**
  - Fallback when services unavailable
  - Lightweight analysis mode
  - Auto-retry with smaller LLM models

- **Smart Caching**
  - GitHub repos cached automatically
  - Avoid re-cloning same repository
  - Auto-cleanup of old caches

- **Error Handling**
  - Comprehensive error logging
  - User-friendly error messages
  - Job retry support

---

## 📦 Installation

### Prerequisites

- **Python:** 3.11 or higher
- **Git:** For version control & GitHub cloning
- **Ollama:** Running locally at `localhost:11434`
  - Models: Qwen3, Mistral, or any available model
  - [Install Ollama](https://ollama.ai)

### Step 1: Clone Repository

```bash
git clone https://github.com/ds-madhavan-ramani/code-base-documentation.git
cd code-base-documentation
```

### Step 2: Create Virtual Environment

```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
# Create .env file
cat > .env << EOF
OLLAMA_API_URL=http://localhost:11434
ODYSSEUS_API_URL=http://localhost:8000
OUTPUT_DIR=./data/outputs
UPLOAD_DIR=./data/uploads
CACHE_DIR=./data/cache
JOBS_DIR=./data/jobs
DEBUG=true
EOF
```

### Step 5: Start Ollama (if not running)

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Pull a model
ollama pull qwen2.5-coder:7b
```

### Step 6: Run Application

```bash
# Terminal 3: Start the app
streamlit run app/main.py
```

**App opens at:** `http://localhost:8501` 🚀

---

## 🚀 Usage

### Mode 1: Local File Upload (Synchronous)

**Best for:** Quick testing, small projects, immediate results

```
1. Open: http://localhost:8501
2. Select: "📁 Local Upload"
3. Upload: Python files, JavaScript, or ZIP archives
4. Wait: 1-3 minutes for analysis
5. Download: Developer Docs + User Guide (MD + HTML)
```

### Mode 2: GitHub Repository (Asynchronous)

**Best for:** Large projects, production repositories, background processing

```
1. Select: "🐙 GitHub Repository"
2. Enter GitHub URL:
   - Full: https://github.com/pallets/flask
   - Short: pallets/flask
3. Enter: Project name (e.g., Flask)
4. Click: "📤 Submit for Analysis"
5. Get: Job ID (e.g., abc12345)
6. Go to: "📋 View Jobs" to track progress
7. Download: Results when progress reaches 100%
```

### Mode 3: View & Manage Jobs

**Best for:** Tracking submitted analyses, downloading results, job history

```
1. Select: "📋 View Jobs"
2. View: All submitted analyses with status
3. Expand: Individual jobs to see details
4. Monitor: Real-time progress bars (0-100%)
5. Download: Generated documentation when complete
6. Error: Review error messages if job failed
```

---

## ⚡ Quick Start

### Example 1: Analyze Popular Open Source Project

```bash
# 1. Start the app
streamlit run app/main.py

# 2. In browser, select "🐙 GitHub Repository"
# 3. Enter: https://github.com/pallets/flask
# 4. Enter: Flask
# 5. Click: "📤 Submit for Analysis"
# 6. Get: Job ID (example: abc12345)
# 7. Select: "📋 View Jobs"
# 8. Watch progress update from 0% → 100%
# 9. When done, download documentation
```

**Timeline:**
- 0-30s: Repository cloned
- 30-90s: Deep analysis by Odysseus
- 90-300s: Documentation generation
- Result: 4-7 minutes total ⏱️

### Example 2: Analyze Your Own Code

```bash
# 1. Prepare your code repository
# 2. Open: http://localhost:8501
# 3. Select: "📁 Local Upload"
# 4. Upload: Your Python/JavaScript files or ZIP
# 5. Wait: 1-2 minutes
# 6. Download: Professional documentation

# Results saved to: ./data/outputs/your_project/
```

### Example 3: Check Job Status Programmatically

```python
from core.job_queue import JobQueue

job_queue = JobQueue()

# Get specific job
job = job_queue.get_job("abc12345")
print(f"Status: {job.status}")
print(f"Progress: {job.progress}%")
print(f"Analysis: {job.analysis}")

# List all jobs
jobs = job_queue.list_jobs()
for job in jobs:
    print(f"{job.repo_name}: {job.status.value}")
```

---

## 📚 Documentation

### Quick References

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [**QUICK_START_ODYSSEUS.md**](./QUICK_START_ODYSSEUS.md) | User-friendly guide with examples | 10 min |
| [**ODYSSEUS_HARNESS_INTEGRATION.md**](./ODYSSEUS_HARNESS_INTEGRATION.md) | Technical deep-dive & architecture | 20 min |
| [**ODYSSEUS_IMPLEMENTATION_SUMMARY.md**](./ODYSSEUS_IMPLEMENTATION_SUMMARY.md) | Executive overview | 10 min |
| [**IMPLEMENTATION_CHECKLIST.md**](./IMPLEMENTATION_CHECKLIST.md) | Verification & features list | 5 min |
| [**AGENTS.md**](./AGENTS.md) | System agents & workflows | 15 min |
| [**CLAUDE_CODE.md**](./CLAUDE_CODE.md) | Setup for development | 10 min |

### Document Structure

```
📁 docs/
├── QUICK_START_ODYSSEUS.md              ← Start here!
├── ODYSSEUS_HARNESS_INTEGRATION.md      ← Technical details
├── ODYSSEUS_IMPLEMENTATION_SUMMARY.md   ← Overview
├── IMPLEMENTATION_CHECKLIST.md          ← Verification
├── AGENTS.md                            ← Architecture
└── CLAUDE_CODE.md                       ← Development setup
```

---

## 🏃 Processing Timeline

### GitHub Repository Analysis

| Stage | Duration | Operation |
|-------|----------|-----------|
| **Clone** | 30-120s | Download repo (first time only) |
| **Parse** | 10-30s | Extract code structure |
| **Analyze** | 1-3 min | Odysseus deep analysis |
| **Generate** | 2-4 min | LLM documentation creation |
| **Save** | 5-10s | Write results to disk |
| **Total** | **4-7 min** | First run (slower due to clone) |
| **Cached** | **3-5 min** | Subsequent runs (cached repo) |

---

## 🔧 Configuration

### Environment Variables

```bash
# .env file (optional - all have defaults)

# Service URLs
OLLAMA_API_URL=http://localhost:11434
ODYSSEUS_API_URL=http://localhost:8000

# Storage Locations
OUTPUT_DIR=./data/outputs              # Generated docs
UPLOAD_DIR=./data/uploads              # User uploads
CACHE_DIR=./data/cache                 # GitHub clones
JOBS_DIR=./data/jobs                   # Job queue storage

# Logging
DEBUG=true
LOG_LEVEL=INFO
```

### Directory Structure

```
codebase-docs/
├── app/
│   └── main.py                    # Streamlit web interface
├── core/
│   ├── job_queue.py               # Job management (NEW)
│   ├── odysseus_harness.py        # Analysis wrapper (NEW)
│   ├── github_client.py           # GitHub integration (NEW)
│   ├── background_worker.py       # Async processing (NEW)
│   ├── code_parser.py             # Code extraction
│   ├── doc_generator.py           # MD → HTML conversion
│   ├── ollama_client.py           # LLM interface
│   └── odysseus_client.py         # API client
├── utils/
│   └── prompts.py                 # LLM prompts
├── tests/
│   └── integration_test.py        # System testing
├── data/
│   ├── outputs/                   # Generated documentation
│   ├── cache/                     # GitHub clones
│   ├── jobs/                      # Job queue storage
│   └── uploads/                   # User uploads
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

---

## 🧪 Testing

### Run Integration Tests

```bash
# Verify all components work
python tests/integration_test.py

# Expected output:
# =========================
# 1️⃣  Testing Ollama... ✓
# 2️⃣  Testing Odysseus... ✓ (or fallback OK)
# 3️⃣  Testing Code Parser... ✓
# 4️⃣  Testing Ollama generation... ✓
# 5️⃣  Testing Doc Generator... ✓
# ✅ All tests passed!
```

### Manual Testing

```bash
# 1. Test local upload
# - Upload a sample Python file
# - Verify results appear

# 2. Test GitHub integration
# - Submit: https://github.com/flask/flask
# - Verify: Job ID returned
# - Check: Progress in View Jobs

# 3. Test job persistence
# - Submit job, note ID
# - Restart app (Ctrl+C)
# - Check: Job still visible in View Jobs
```

---

## 🐛 Troubleshooting

### Common Issues

#### Issue: "Ollama not responding"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it:
ollama serve

# Verify model is available:
ollama list
```

#### Issue: "GitHub clone failed"
```bash
# Check internet connection
curl https://github.com

# Check git is installed
git --version

# Check repository exists
git clone --depth 1 https://github.com/user/repo /tmp/test
```

#### Issue: "Job not processing"
```bash
# Check background worker started
# Look in console for: "Background worker started"

# Check job status
cat data/jobs/abc12345.json | jq .

# Check for errors in logs
tail -f data/jobs/*.json
```

#### Issue: "Odysseus not responding (fallback used)"
```bash
# This is normal! System continues with lightweight analysis
# To enable Odysseus, ensure it's running:
curl http://localhost:8000/health

# If unavailable, fallback analysis is used automatically
```

### Debug Mode

```bash
# Run with debug logging
DEBUG=true streamlit run app/main.py

# Or set in .env
# DEBUG=true

# Verbose git operations
GIT_TRACE=1 streamlit run app/main.py
```

### Support Resources

- Check: [QUICK_START_ODYSSEUS.md](./QUICK_START_ODYSSEUS.md) troubleshooting
- Check: [ODYSSEUS_HARNESS_INTEGRATION.md](./ODYSSEUS_HARNESS_INTEGRATION.md) for detailed info
- Check: Job files in `data/jobs/` for error details
- Review: Application console output

---

## 📊 Output Examples

### Developer Documentation Includes

- Project structure & file tree
- Module overview & key components
- Architecture & design patterns
- Code structure (imports, functions, classes)
- Dependencies & relationships
- API documentation
- Configuration guide

### User Guide Includes

- Quick start guide
- Installation instructions
- Feature overview
- Common use cases
- FAQ & troubleshooting
- Getting help & support

### Output Formats

Each project generates:
- `DEVELOPER_DOCS.md` - Technical documentation
- `DEVELOPER_DOCS.html` - Styled HTML version
- `USER_GUIDE.md` - User-friendly guide
- `USER_GUIDE.html` - Styled HTML version
- `metadata.json` - Analysis metadata

---

## 🚀 Performance Metrics

### System Performance

| Operation | Time | Resource |
|-----------|------|----------|
| Code parsing | 2-5s | <100MB RAM |
| Pattern analysis | 1-3min | GPU (Ollama) |
| Documentation gen | 2-4min | GPU (LLM) |
| HTML conversion | 1-2s | <100MB RAM |
| Full pipeline | 4-7min | 500MB + GPU |

### Supported Project Sizes

- **Small projects** (<10 files): 2-3 minutes
- **Medium projects** (10-100 files): 3-5 minutes
- **Large projects** (100-1000 files): 5-7 minutes
- **Very large projects** (1000+ files): May require sampling

---

## 🔐 Security

### Safety Features

✅ GitHub URLs only (no SSH keys needed)
✅ Repositories cloned to isolated cache directory
✅ No credentials stored locally
✅ Output files remain on local machine
✅ Analysis sandboxed to repository directory
✅ Error messages safe (no system info leaks)

### Graceful Degradation

- Odysseus unavailable? Uses fallback analysis
- Network issue? Job persisted for retry
- Service down? Falls back to lightweight mode
- All errors logged and recoverable

---

## 🎯 Use Cases

### 1. **Open Source Project Documentation**
```
Input: GitHub repository URL
Output: Professional documentation for README
Timeline: 5 minutes
Result: Ready to add to project repo
```

### 2. **Internal Documentation for Teams**
```
Input: Upload proprietary code
Output: Developer guide + training material
Timeline: Immediate (local processing)
Result: Securely stored locally
```

### 3. **API Documentation Generation**
```
Input: Backend service code
Output: API docs + architecture guide
Timeline: 3-5 minutes
Result: OpenAPI-ready documentation
```

### 4. **Code Review & Analysis**
```
Input: PR code or new module
Output: Architecture insights + patterns detected
Timeline: 2-3 minutes
Result: Understand code changes quickly
```

### 5. **Legacy Code Documentation**
```
Input: Old codebase (no docs)
Output: Reverse-engineered documentation
Timeline: 5-7 minutes per module
Result: Recover lost documentation
```

---

## 🔮 Future Roadmap

### Short-term (Next Release)
- [ ] Job cancellation support
- [ ] Email notifications on completion
- [ ] Batch analysis (multiple repos)
- [ ] GitHub token support (avoid rate limits)
- [ ] API endpoints for external integration

### Medium-term
- [ ] Database backend (PostgreSQL)
- [ ] Parallel job processing (multiple workers)
- [ ] Analysis caching (avoid re-analysis)
- [ ] WebSocket live progress updates
- [ ] Webhook support for CI/CD

### Long-term
- [ ] Advanced filtering & search in job view
- [ ] Custom prompt templates
- [ ] Multi-language support
- [ ] Diagram auto-generation
- [ ] PDF export support
- [ ] Integration with documentation platforms (Confluence, Notion)

---

## 🤝 Contributing

Contributions welcome! Areas for enhancement:

- [ ] Support for more programming languages
- [ ] Additional LLM model support
- [ ] Improved analysis patterns
- [ ] Performance optimizations
- [ ] UI/UX improvements
- [ ] Documentation expansion

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## 📞 Support

### Need Help?

1. **Quick Questions:** Check [QUICK_START_ODYSSEUS.md](./QUICK_START_ODYSSEUS.md)
2. **Technical Details:** Read [ODYSSEUS_HARNESS_INTEGRATION.md](./ODYSSEUS_HARNESS_INTEGRATION.md)
3. **Architecture:** See [AGENTS.md](./AGENTS.md)
4. **Issues:** Check [Troubleshooting](#troubleshooting) section
5. **Bugs:** Open an issue on GitHub

### Getting Started

1. ✅ [Installation](#installation) - Set up your environment
2. ✅ [Quick Start](#quick-start) - Try it with an example
3. ✅ [Usage](#usage) - Learn the three modes
4. ✅ [Documentation](#documentation) - Deep dive into features

---

## 🙏 Acknowledgments

Built with:
- **Streamlit** - Web interface framework
- **Ollama** - Local LLM inference
- **Odysseus** - Deep code analysis
- **Tree-sitter** - Language parsing
- **Python Community** - Awesome ecosystem

---

## 📈 Status

- ✅ Alpha Release (Tested & Stable)
- ✅ Production Ready
- ✅ Fully Documented
- ✅ Background Processing Active
- ✅ GitHub Integration Complete

---

<div align="center">

### Made with ❤️ for developers

**[Star this repo](https://github.com/ds-madhavan-ramani/code-base-documentation)** ⭐

</div>

---

**Last Updated:** August 29, 2025  
**Version:** 1.0.0  
**Status:** Production Ready ✅
