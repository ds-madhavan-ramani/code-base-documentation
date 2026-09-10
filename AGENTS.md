# Agents & Workflows for Codebase Documentation System

## Overview
This document describes the autonomous agents and workflows available in the system.

---

## 1. Code Parser Agent
**Role:** Extract structure from codebases  
**Trigger:** User uploads code folder or ZIP  
**Actions:**
- Recursively scan directory for source files
- Extract imports, functions, classes
- Create file tree visualization
- Detect language from file extension
- Ignore .git, node_modules, __pycache__, etc.

**Output:**
```python
{
  "file_tree": "project_name/\n├── src/\n│   ├── main.py\n│   └── utils.py\n...",
  "code_structure": {
    "imports": ["os", "sys", "requests"],
    "functions": ["main", "helper", "process"],
    "classes": ["DataProcessor", "Config"]
  }
}
```

---

## 2. Ollama Generation Agent
**Role:** Generate text documentation using LLM  
**Trigger:** After code structure extracted  
**Models Available:**
- `qwen3:32b` - Best quality, slower (19GB VRAM)
- `qwen3:8b` - Good quality, fast (5GB VRAM)
- `mistral` - General purpose (7GB VRAM)
- `qwen2.5-coder:7b` - Code specialist (5GB VRAM)

**Fallback Chain:**
1. Try primary model
2. If timeout → try next model
3. If all fail → use any available model
4. If none available → error

**Generation Style:** Section-by-section and grounded, not one shot
(`utils/prompts.py`). Fixed whole-document sections still run once each;
the sections most prone to hallucination (feature explanations, per-file
code detail) are generated dynamically instead — one real feature or one
real source file per call, with that file's actual content in the prompt —
so the model explains code it's genuinely shown rather than inventing
plausible-sounding function names or repo URLs. See README.md's
"Documentation Generation (Grounded, Section-by-Section)" section for the
full flow diagram.
- **Dev Docs:** `DEV_DOCS_TIER1_SECTIONS` (Big Picture, Systems View,
  Architecture & Patterns) → `build_feature_map_section()` (1 call) →
  `build_file_walkthrough_sections()` (1 call per significant file, capped
  at `DEV_DOCS_MAX_FILES`) → `DEV_DOCS_TAIL_SECTIONS` (Configuration &
  Workflow, Common Tasks & Troubleshooting)
- **User Guide:** `USER_DOCS_HEAD_SECTIONS` (Big Picture, Quick Start &
  Install) → `build_user_feature_sections()` (1 call per feature, sharing
  the same `identify_features()` result as the dev docs) →
  `USER_DOCS_TAIL_SECTIONS` (FAQ & Support)

---

## 3. Odysseus Analysis Agent
**Role:** Deep code analysis (optional)  
**Trigger:** If Odysseus server available  
**Actions:**
- Analyze architecture patterns
- Identify key modules
- Extract dependencies
- Detect design patterns
- Generate system diagrams

**Fallback:** If Odysseus unavailable, uses file-based analysis

---

## 4. Documentation Generator Agent
**Role:** Convert analysis to markdown/HTML  
**Trigger:** After analysis complete  
**Actions:**
- Generate developer docs (markdown)
- Generate user guides (markdown)
- Convert markdown → HTML with CSS
- Create metadata.json
- Save to data/outputs/{repo_name}/

**Output Files:**
- DEVELOPER_DOCS.md
- DEVELOPER_DOCS.html
- USER_GUIDE.md
- USER_GUIDE.html
- metadata.json

---

## 5. Model Selection Agent
**Role:** Choose best model automatically  
**Logic:**

```python
# For Developer Documentation (needs quality)
For task = "dev_docs":
  1. Try qwen3:32b (best)
  2. Try qwen2.5-coder:32b (alternative)
  3. Try mistral (fast fallback)
  4. Use any available model

# For User Guides (needs speed)
For task = "user_docs":
  1. Try qwen3:8b (balanced)
  2. Try qwen2.5-coder:7b (coder)
  3. Try neural-chat (conversational)
  4. Try phi (ultra-light)
  5. Use any available model
```

---

## 6. Streamlit UI Agent
**Role:** Web interface for all operations  
**Trigger:** `streamlit run app/main.py`  
**Features:**
- File upload (folder, ZIP, individual files)
- Real-time status updates
- Service health check sidebar
- Progress bars for long operations
- Download generated documentation
- Preview dev docs & user guide

---

## 7. Integration Test Agent
**Role:** Validate all components  
**Trigger:** `python tests/integration_test.py`  
**Tests:**
1. ✓ Ollama health check
2. ✓ Odysseus availability
3. ✓ Code parser functionality
4. ✓ LLM generation
5. ✓ HTML generation
6. ✓ Full pipeline

**Expected Result:** All 5 tests pass ✅

---

## Workflow: Full Pipeline

```
USER UPLOADS CODE
        ↓
┌─────────────────────────────────────┐
│ 1. Code Parser Agent               │
│    - Scan files                     │
│    - Extract structure              │
│    - Create file tree               │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 2. Odysseus Agent (Optional)        │
│    - Deep analysis                  │
│    - Architecture patterns          │
│    - Dependencies                   │
│    - Fallback if unavailable        │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 3. Model Selection Agent            │
│    - Choose best model              │
│    - Set up fallback chain          │
│    - Configure parameters           │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 4. Ollama Generation Agent          │
│    - Generate dev docs              │
│    - Generate user guide            │
│    - Auto-retry on failure          │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 5. Documentation Generator          │
│    - Convert markdown → HTML        │
│    - Apply CSS styling              │
│    - Save all formats               │
│    - Create metadata                │
└─────────────────────────────────────┘
        ↓
DOWNLOAD DOCUMENTATION (MD + HTML)
```

---

## Error Handling Strategy

### Ollama Timeout
```
Attempt 1: qwen3:32b (20 sec timeout)
  ↓ TIMEOUT
Attempt 2: qwen3:8b (15 sec timeout)
  ↓ TIMEOUT
Attempt 3: mistral (10 sec timeout)
  ↓ SUCCESS → Use response
```

### Model Not Available
```
Requested: qwen3:32b
Available: [qwen3:8b, mistral, phi]
Action: Use largest available = mistral
```

### Markdown Conversion Fails
```
Try 1: md_convert(..., extensions=['extra', 'codehilite'])
  ↓ ERROR (codehilite not available)
Try 2: md_convert(..., extensions=['fenced_code'])
  ↓ SUCCESS
```

### All Services Down
```
Ollama: UNAVAILABLE
Odysseus: UNAVAILABLE
Action: Error - Cannot proceed without Ollama
Message: "Ollama not running. Start with: ollama serve"
```

---

## Manual Agent Invocation

### Parse Code
```python
from core.code_parser import CodeParser

parser = CodeParser("./my_project")
code_files = parser.parse_directory()
file_tree = parser.create_file_tree()
```

### Generate Text
```python
from core.ollama_client import OllamaClient

ollama = OllamaClient("http://localhost:11434")
response = ollama.generate(
    model="qwen3:8b",
    prompt="Explain this code...",
    context_length=8192
)
```

### Analyze Code
```python
from core.odysseus_analysis_agent import OdysseusAnalysisAgent

odysseus = OdysseusAnalysisAgent(model="qwen3:32b")
analysis = odysseus.analyze_deep(code_files, repo_name="my_project")
```

### Generate Documentation
```python
from core.doc_generator import DocumentationGenerator

doc_gen = DocumentationGenerator("./outputs")
doc_gen.save_documentation(
    repo_name="my_project",
    dev_docs=dev_markdown,
    user_docs=user_markdown,
    metadata={"project": "my_project"}
)
```

---

## Performance Metrics

| Agent | Input | Output | Time | VRAM |
|-------|-------|--------|------|------|
| Code Parser | 100 files | Structure | 2-5s | <100MB |
| Model Selection | Model list | Best model | <1s | <100MB |
| LLM Generation | Prompt | Doc text | 10-30s | 19GB |
| Doc Generator | Markdown | HTML | 1-2s | <100MB |
| Full Pipeline | Codebase | Docs | 30-60s | 19GB |

---

## Configuration

### Environment Variables
```bash
OLLAMA_API_URL=http://localhost:11434
ODYSSEUS_API_URL=http://localhost:8000
OUTPUT_DIR=./data/outputs
DEBUG=true
```

### Model Configuration
```python
PRIMARY_MODEL = "qwen3:32b"
FALLBACK_MODEL = "qwen3:8b"
CONTEXT_LENGTH = 8192
TEMPERATURE = 0.7
```

### Timeout Configuration
```python
OLLAMA_TIMEOUT = 300  # 5 minutes
ODYSSEUS_TIMEOUT = 120  # 2 minutes
```

---

## Monitoring & Logging

### Health Check
```bash
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:8000/health     # Odysseus
```

### Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Model Activity
```bash
ollama list  # See what's loaded
watch -n 5 'nvidia-smi'  # Monitor GPU
```

---

## Next Generation Improvements

- [ ] Caching layer (avoid re-analyzing same code)
- [ ] Job queue (background processing)
- [ ] Database for job history
- [ ] Advanced prompt tuning
- [ ] Multi-language support
- [ ] Mermaid diagram generation
- [ ] GitHub integration
- [ ] PDF export

