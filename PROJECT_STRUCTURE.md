# TN Staging System - Project Structure

## 📁 Clean Production Structure

```
tn_staging_agentic/
├── 📚 Core Documentation
│   ├── README.md                    # Main project overview and quick start
│   ├── CLAUDE.md                    # Complete project specifications
│   ├── ARCHITECTURE.md              # Detailed architecture with mermaid diagrams
│   └── PROJECT_STRUCTURE.md         # This file
│
├── ⚙️ Configuration & Environment
│   ├── requirements.txt             # Python dependencies
│   ├── environment.yml              # Conda environment definition
│   └── .gitignore                   # Git ignore patterns
│
├── 🚀 User Interfaces
│   ├── tn_staging_api.py           # Command-line interface
│   ├── tn_staging_gui.py           # Streamlit web interface
│   └── main.py                     # Core system class
│
├── 🤖 Agent System
│   └── agents/
│       ├── __init__.py             # Agent package initialization
│       ├── base.py                 # Base agent class and shared components
│       ├── detect.py               # Body part/cancer type detection
│       ├── retrieve_guideline.py   # AJCC guideline retrieval from vector store
│       ├── staging_t.py            # T staging analysis with LLM
│       ├── staging_n.py            # N staging analysis with LLM
│       ├── query.py                # Interactive question generation
│       └── report.py               # Final report generation
│
├── 🏗️ Core Infrastructure
│   ├── config/                     # LLM provider configurations
│   │   ├── __init__.py
│   │   ├── llm_providers.py        # Provider factory and implementations
│   │   ├── ollama_config.py        # Ollama-specific configuration
│   │   └── openai_config.py        # OpenAI-specific configuration
│   │
│   ├── contexts/                   # Context and workflow management
│   │   ├── __init__.py
│   │   └── context_manager.py      # Context manager and workflow orchestrator
│   │
│   └── utils/                      # Utilities and logging
│       ├── __init__.py
│       └── logging_config.py       # Session-based logging system
│
├── 📖 Guidelines & Vector Stores
│   ├── guidelines/                 # AJCC guidelines processing
│   │   ├── __init__.py
│   │   ├── tokenizer.py           # PDF processing and tokenization
│   │   └── pdfs/                  # AJCC PDF guidelines (gitignored)
│   │       └── oral cavity and oropharyngeal.pdf
│   │
│   └── faiss_stores/              # Vector databases (gitignored)
│       ├── ajcc_guidelines_local/  # Ollama embeddings
│       └── ajcc_guidelines_openai/ # OpenAI embeddings
│
├── 📊 Logs & Testing
│   ├── logs/                      # Session logs (gitignored)
│   │   ├── session_*.log          # Human-readable logs
│   │   └── session_*.jsonl        # Structured event logs
│   │
│   └── tests/                     # Test suite
│       ├── unit/                  # Unit tests
│       ├── integration/           # Integration tests
│       └── test_*.py              # Test files
│
├── 🗂️ Archived Materials
│   ├── old/                       # Previous version (reference)
│   │   ├── CLAUDE.md              # Original specifications
│   │   ├── CRITICAL_ANALYSIS.md   # Colleague feedback analysis
│   │   ├── FEEDBACK_RESPONSE.md   # Improvement plan
│   │   └── *.py                   # Original implementation files
│   │
│   └── not_using/                 # Development utilities and archived code
│       ├── docs/                  # Additional documentation
│       ├── gui_attempts/          # GUI development iterations
│       ├── launchers/             # Various launcher scripts
│       ├── ajcc_tokenizer_*.py    # Vector store building tools
│       ├── validate_system.py     # System validation script
│       └── test_*.txt             # Test data files
```

## 🎯 Key Directories Explained

### **Production Code (Git Tracked)**
- **`agents/`** - Core LLM agents implementing the staging logic
- **`config/`** - LLM provider configurations and factory patterns  
- **`contexts/`** - Context management and workflow orchestration
- **`utils/`** - Logging and utility functions
- **`tests/`** - Comprehensive test suite
- **Root files** - User interfaces and system entry points

### **Built Locally (Git Ignored)**
- **`faiss_stores/`** - Vector databases built from AJCC PDFs
- **`logs/`** - Session logs with detailed analysis traces
- **`guidelines/pdfs/`** - AJCC PDF files (download separately)

### **Reference & Development (Git Tracked)**
- **`old/`** - Previous version for reference and comparison
- **`not_using/`** - Development utilities, archived code, and extra documentation

## 🔧 File Responsibilities

### **User Entry Points**
| File | Purpose | Usage |
|------|---------|-------|
| `tn_staging_api.py` | Command-line interface | `python tn_staging_api.py --help` |
| `tn_staging_gui.py` | Web interface | `streamlit run tn_staging_gui.py` |
| `main.py` | Core system class | Imported by interfaces |

### **Core Agent Files**
| File | Purpose | Key Function |
|------|---------|--------------|
| `agents/base.py` | Base classes | `BaseAgent`, `AgentContext`, `AgentMessage` |
| `agents/detect.py` | Detection | Identifies body part and cancer type |
| `agents/retrieve_guideline.py` | Guidelines | Retrieves AJCC criteria from vector store |
| `agents/staging_t.py` | T Staging | LLM-based tumor staging analysis |
| `agents/staging_n.py` | N Staging | LLM-based node staging analysis |
| `agents/query.py` | Querying | Generates clarifying questions |
| `agents/report.py` | Reporting | Final report generation |

### **Infrastructure Files**
| File | Purpose | Key Classes |
|------|---------|-------------|
| `config/llm_providers.py` | LLM abstraction | `LLMProviderFactory`, `OllamaProvider`, `OpenAIProvider` |
| `contexts/context_manager.py` | Workflow | `ContextManager`, `WorkflowOrchestrator` |
| `utils/logging_config.py` | Logging | `SessionLogger`, session-based file logging |

## 🚀 Getting Started Paths

### **For Users**
1. Read `README.md` for overview and quick start
2. Run `tn_staging_api.py --help` for CLI usage  
3. Run `streamlit run tn_staging_gui.py` for web interface

### **For Developers**
1. Read `CLAUDE.md` for complete specifications
2. Review `ARCHITECTURE.md` for system design
3. Explore `agents/` for core implementation
4. Check `tests/` for usage examples

### **For Contributors**
1. Use conda environment: `conda env create -f environment.yml`
2. Follow LLM-first principles (no hardcoded medical rules)
3. Add tests in `tests/` for new functionality
4. Update documentation for any changes

## 📊 Project Stats

- **Core Python files**: ~20 production files
- **Lines of code**: ~3,000 LOC (excluding archived)
- **Dependencies**: ~15 core packages (PyTorch-free)
- **Architecture**: Agent-based with LLM-first approach
- **Testing**: Unit and integration test coverage
- **Documentation**: Comprehensive guides and specifications

---

**Status**: ✅ **Clean, organized, production-ready structure** with clear separation between production code, development utilities, and reference materials.