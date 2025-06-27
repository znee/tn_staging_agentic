# Vector Store Building Guide

**Purpose**: Documentation for building high-quality cancer-specific vector stores when new guideline PDFs are added.

## Overview

This guide documents the standardized process for creating cancer-specific vector stores that match the main store's high-quality configuration. Use this when adding new body part PDFs (lung, breast, liver, etc.).

## High-Quality Configuration Standard

All cancer-specific vector stores should use these exact settings to maintain consistency:

```python
# Standard Configuration (matches main store)
chunk_size = 1000
chunk_overlap = 200
embedding_model = "nomic-embed-text:latest"
tokenizer = "Advanced PyMuPDF with table extraction"
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""]
)
```

## Quick Start for New Body Parts

### 1. Add New PDF
Place the PDF in `guidelines/pdfs/[BodyPart]_staging.pdf`

### 2. Update Body Part Mapping
Edit `agents/retrieve_guideline.py` - `_initialize_body_part_mapping()`:

```python
mapping = {
    # Existing oral cavity mappings...
    
    # Add new body part mappings
    "lung": "lung",
    "pulmonary": "lung", 
    "bronchial": "lung",
    
    "breast": "breast",
    "mammary": "breast",
    
    "liver": "liver",
    "hepatic": "liver",
    
    # etc.
}
```

### 3. Run Vector Store Builder
Use the standardized builder script:

```bash
cd /path/to/project
/opt/homebrew/Caskroom/miniconda/base/envs/tnm-staging/bin/python build_cancer_store.py --body-part lung --pdf guidelines/pdfs/Lung_staging.pdf
```

## Detailed Implementation

### Vector Store Builder Template

The standardized builder is located at: `not_using/experimental_code/rebuild_oropharyngeal_store.py`

**Key features to maintain:**
- Advanced PyMuPDF table detection
- Medical table markers (`[MEDICAL TABLE]`, `[END TABLE]`)
- Cancer-specific metadata enhancement
- HPV/special feature detection (adapt per cancer type)
- Comprehensive testing and validation

### Expected Output Structure

Each new cancer-specific store should produce:

```
faiss_stores/
├── [body_part]_local/           # Local embedding version
│   ├── index.faiss
│   └── index.pkl
├── [body_part]_openai/          # OpenAI embedding version (if configured)
│   ├── index.faiss
│   └── index.pkl
└── [body_part]_local_summary.json  # Processing summary
```

### Metadata Structure

Each chunk should include this metadata structure:

```python
chunk_metadata = {
    'chunk_id': i,
    'source': pdf_path,
    'cancer_type': body_part,
    'body_parts': [body_part, related_terms],
    'special_features': [cancer_specific_features],  # e.g., 'her2_aware' for breast
    'chunk_size': len(chunk),
    'has_table': '[MEDICAL TABLE]' in chunk,
    'has_t_staging': has_t_staging_content,
    'has_n_staging': has_n_staging_content,
    'has_special_content': has_cancer_specific_markers  # Adapt per cancer type
}
```

## Quality Validation

### Expected Metrics

For a 6-page AJCC guideline PDF, expect:
- **Chunks**: 15-25 (depending on content density)
- **Medical tables**: 3-6 detected tables
- **T staging chunks**: 40-60% of total chunks
- **N staging chunks**: 50-80% of total chunks
- **Special content**: Variable by cancer type

### Validation Tests

Each new store should pass these tests:

```python
test_queries = [
    f"T staging criteria {body_part}",
    f"N staging lymph node {body_part}",
    f"T4 staging {cancer_type}",
    f"N2 staging {cancer_type}",
    # Add cancer-specific queries
]
```

### Quality Benchmarks

- **Chunk count**: Should be 15-30 for typical AJCC guidelines
- **Table detection**: Should find major staging tables
- **Content coverage**: T and N staging content should be well-represented
- **Search quality**: All test queries should return relevant results

## Cancer-Specific Adaptations

### Breast Cancer
```python
special_features = ['her2_aware', 'er_pr_aware', 'dcis_aware']
special_content_markers = ['her2', 'estrogen receptor', 'progesterone receptor', 'dcis']
```

### Lung Cancer  
```python
special_features = ['nsclc_sclc_aware', 'mutation_aware']
special_content_markers = ['nsclc', 'sclc', 'egfr', 'alk', 'kras']
```

### Liver Cancer
```python
special_features = ['hepatocellular_aware', 'cirrhosis_aware']
special_content_markers = ['hepatocellular', 'cirrhosis', 'alpha-fetoprotein']
```

## Integration with Routing System

After building a new store, the routing system automatically detects it:

1. **Detection**: System checks if `faiss_stores/[body_part]_local` exists
2. **Routing**: If found, routes to specialized store
3. **Fallback**: If missing, falls back to main general store
4. **Logging**: All routing decisions logged for debugging

## Troubleshooting

### Common Issues

**Low chunk count (< 10)**: 
- Check PDF quality and text extraction
- Verify chunk size settings
- Review text splitter configuration

**No medical tables detected**:
- Verify PyMuPDF table detection is working
- Check PDF format (ensure tables are properly formatted)
- Review table detection criteria

**Poor search quality**:
- Verify embedding model is consistent
- Check chunk overlap settings
- Review content preprocessing

### Validation Commands

```bash
# Test store creation
python build_cancer_store.py --test --body-part [body_part]

# Validate routing
python -c "from agents.retrieve_guideline import GuidelineRetrievalAgent; # test routing"

# Check store quality  
python analyze_vector_store.py --store faiss_stores/[body_part]_local
```

## Maintenance

### Regular Tasks

1. **Quality monitoring**: Periodically test search quality with standard queries
2. **Consistency checks**: Ensure all stores use same configuration
3. **Performance monitoring**: Track retrieval speed and accuracy
4. **Updates**: Rebuild stores when PDFs are updated

### Backup Strategy

- Keep original PDFs in `guidelines/pdfs/`
- Backup processing summaries
- Maintain builder scripts in `not_using/experimental_code/`
- Document any custom adaptations per cancer type

## Future Enhancements

### Planned Improvements

- **Automated builder**: CLI tool for one-command store creation
- **Quality metrics**: Automated quality assessment
- **Multi-version support**: Support for different AJCC versions
- **Batch processing**: Build multiple stores simultaneously

### Architecture Evolution

The current architecture supports:
- ✅ Individual cancer-specific stores
- ✅ Intelligent routing with fallback
- ✅ Consistent quality standards
- 🔄 Future: Multi-guideline versions
- 🔄 Future: Automated quality monitoring
- 🔄 Future: Cross-cancer validation

---

**Last Updated**: June 27, 2025  
**Version**: 1.0  
**Maintainer**: TN Staging System  
**Template Based On**: Oral/Oropharyngeal store (17 chunks, high-quality)