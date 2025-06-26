# TN Staging System - Changelog

## [2.0.2] - 2025-06-25 - Guidelines Update & Tokenizer Enhancement

### 📄 Updated Guidelines
- **New PDF**: `Oralcavity_oropharyngeal.pdf` with enhanced tabular structures
- **Enhanced Table Detection**: 4 medical tables successfully tokenized (p16+ and p16- cancer staging)
- **Improved Chunking**: 34 semantic chunks generated (optimized from previous 83)

### 🔧 Tokenizer Improvements
- **Fixed Metadata Bug**: `has_table` metadata now correctly identifies chunks with medical tables
- **Enhanced Pattern Matching**: Updated pattern from exact `"[MEDICAL TABLE]"` to flexible `"[MEDICAL TABLE"`
- **Better Retrieval**: Improved semantic search for table-containing chunks

### 🧹 Project Organization
- **Cleanup**: Moved debugging and analysis scripts to `not_using/` directory
- **Documentation**: Updated all references to reflect new PDF and tokenization results

## [2.0.0] - 2024-06-24 - Production Release

### 🚀 Major Features Added

#### Interactive Workflow System
- **Query Generation**: Automatic question generation when staging confidence is low or TX/NX results
- **Enhanced Report Re-analysis**: Combines user responses with original reports for improved accuracy
- **Real-time Chat Interface**: Streamlit GUI with conversational workflow and history
- **Response Validation**: Smart handling of user responses with context preservation

#### Medical Accuracy Improvements
- **N0 vs NX Distinction**: Proper medical logic - N0 only with explicit negative findings, NX when unclear
- **Radiologic Context Awareness**: Questions focus on imaging findings, not pathology specimens
- **Confidence-based Validation**: Automatic query generation for uncertain staging (< 0.7 confidence)
- **AJCC Guideline Compliance**: Enhanced vector store retrieval with medical table extraction

### 🔧 Technical Improvements

#### LLM Response Handling
- **Enhanced JSON Parsing**: Robust handling of `<think>` tags across all agents
- **Fallback Text Parsing**: Multiple extraction patterns when JSON parsing fails
- **Response Cleaning**: Automatic removal of LLM artifacts and thinking tags
- **Error Recovery**: Graceful fallbacks with meaningful error messages

#### Architecture Enhancements
- **Agent-based System**: Clean separation of concerns with specialized agents
- **LLM-First Approach**: No hardcoded medical rules, all logic through LLM + guidelines
- **Session Management**: Comprehensive logging and context tracking
- **Provider Abstraction**: Support for Ollama, OpenAI, and hybrid configurations

#### User Interface
- **Streamlit GUI**: Production-ready web interface with chat history
- **Progress Indicators**: Real-time processing status and progress bars
- **Query Interface**: Dedicated input areas for responding to staging questions
- **Session Tracking**: Visual indicators for pending operations and query states

### 🩺 Medical System Features

#### Staging Logic
- **T Staging Agent**: Direct LLM analysis with AJCC guideline integration
- **N Staging Agent**: Enhanced lymph node assessment with validation logic
- **Detection Agent**: Robust body part and cancer type identification
- **Query Agent**: Targeted question generation for missing information

#### Guidelines Integration
- **Vector Store Retrieval**: FAISS-based AJCC guideline storage and retrieval
- **Table Extraction**: Enhanced PDF processing with medical table preservation
- **Contextual Retrieval**: Body part and cancer type specific guideline fetching
- **Fallback Mechanisms**: LLM-based guideline simulation when vector store unavailable

### 📊 Performance & Quality

#### System Performance
- **Analysis Time**: 1-3 minutes per report (optimized for accuracy)
- **Memory Efficiency**: ~2GB RAM including vector stores
- **PyTorch-Free**: Removed heavy dependencies for cleaner deployment
- **Concurrent Processing**: Parallel T and N staging analysis

#### Quality Assurance
- **Comprehensive Logging**: Session-based logs with JSON and text formats
- **Error Handling**: Graceful degradation with clear error messages
- **Testing Suite**: Unit and integration tests for reliability
- **Medical Validation**: Proper staging logic with confidence assessment

### 🛠️ Developer Experience

#### Documentation
- **Complete README**: Quick start guide with examples and configuration
- **Architecture Guide**: Detailed system design with mermaid diagrams
- **Project Structure**: Clear organization with production/development separation
- **API Documentation**: CLI and programmatic usage examples

#### Development Tools
- **Conda Environment**: Consistent development setup with all dependencies
- **Git Integration**: Clean repository structure with proper gitignore
- **Debugging Tools**: Comprehensive logging and error tracking
- **Configuration Management**: Flexible backend switching and environment variables

### 🔒 Production Features

#### Security & Compliance
- **Local Processing**: Ollama support for privacy-sensitive environments
- **Session Isolation**: Proper context management and cleanup
- **Error Sanitization**: Safe error messages without sensitive data exposure
- **Medical Disclaimer**: Clear warnings about clinical decision support limitations

#### Deployment Ready
- **Container Support**: Docker-compatible with conda environment
- **Configuration Flexibility**: Environment variable and file-based configuration
- **Monitoring**: Structured logging for production monitoring
- **Scalability**: Stateless design supporting horizontal scaling

## [1.0.0] - Previous Version

### Initial Features
- Basic TN staging analysis
- Pattern-based extraction
- Simple CLI interface
- OpenAI integration

---

## Migration Guide from v1.0 to v2.0

### Key Changes
1. **Architecture**: Moved from pattern-based to LLM-first approach
2. **Interface**: Added interactive Streamlit GUI
3. **Medical Logic**: Enhanced N0/NX distinction and radiologic focus
4. **Error Handling**: Comprehensive improvements with robust JSON parsing

### Breaking Changes
- Pattern extraction methods removed
- API response format enhanced with confidence and rationale
- Session management redesigned for better user experience

### Upgrade Steps
1. Update conda environment: `conda env update -f environment.yml`
2. Rebuild vector stores: `streamlit run not_using/ajcc_tokenizer_ollama.py`
3. Test new GUI: `streamlit run tn_staging_gui.py`
4. Review updated documentation in README.md and ARCHITECTURE.md

---

**Status**: ✅ **Production Ready** - Complete LLM-first architecture with interactive workflow and comprehensive testing.