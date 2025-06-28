# Context Optimization Strategy

**Date**: June 27, 2025  
**Purpose**: Practical implementation guide for reducing LLM context sizes  
**Target**: Reduce T/N staging agent response time from 37-40s to 15-25s

## Strategy Overview

Based on the comprehensive LLM context analysis, the optimization strategy focuses on **intelligent context reduction** for the T and N staging agents, which are consuming 900-2,900 tokens each.

## Priority 1: Guideline Context Reduction (Highest Impact)

### Current Problem:
- **Retrieved guidelines**: 2,000-8,000 characters of full AJCC sections
- **Irrelevant content**: General cancer information not needed for specific staging
- **Verbose descriptions**: Detailed explanations beyond core staging criteria

### Implementation Approach:

#### 1a. Intelligent Guideline Filtering
```python
def filter_guidelines_for_staging(guidelines: str, stage_type: str, case_features: Dict) -> str:
    """Filter guidelines to staging-relevant content only."""
    
    # Priority 1: Medical tables (preserve completely)
    tables = extract_medical_tables(guidelines)
    
    # Priority 2: Stage-specific criteria
    if stage_type == "T":
        relevant_markers = ["t0", "t1", "t2", "t3", "t4", "invasion", "size", "criteria"]
    else:  # N staging
        relevant_markers = ["n0", "n1", "n2", "n3", "lymph", "node", "metastasis", "criteria"]
    
    # Extract only relevant sections
    filtered_sections = []
    for section in guidelines.split('\n\n'):
        if any(marker in section.lower() for marker in relevant_markers):
            filtered_sections.append(section)
    
    # Combine tables + relevant sections
    return combine_priority_content(tables, filtered_sections)
```

#### 1b. Case-Driven Filtering
```python
def filter_by_case_context(guidelines: str, case_features: Dict) -> str:
    """Further filter guidelines based on specific case characteristics."""
    
    # If case has size information, prioritize size-based criteria
    if case_features.get('has_size'):
        prioritize_content_with_keywords(guidelines, ['cm', 'size', 'diameter'])
    
    # If case has invasion, prioritize invasion criteria  
    if case_features.get('has_invasion'):
        prioritize_content_with_keywords(guidelines, ['invasion', 'extends', 'involves'])
    
    # If case has nodes, prioritize node-specific content
    if case_features.get('has_nodes'):
        prioritize_content_with_keywords(guidelines, ['lymph', 'node', 'metastatic'])
```

**Expected Reduction**: 2,000-8,000 → 800-2,500 characters (50-70% reduction)

## Priority 2: Report Context Optimization (High Impact)

### Current Problem:
- **Full radiologic report**: 1,000-5,000 characters passed to each staging agent
- **Irrelevant sections**: Procedural details, equipment information, demographics
- **Verbose descriptions**: Clinical background not needed for staging

### Implementation Approach:

#### 2a. Staging-Relevant Extraction
```python
def extract_staging_relevant_content(report: str) -> Dict[str, str]:
    """Extract only staging-relevant sections from radiologic report."""
    
    relevant_sections = {
        'findings': extract_findings_section(report),
        'measurements': extract_measurements(report), 
        'invasion_patterns': extract_invasion_details(report),
        'lymph_nodes': extract_node_information(report),
        'clinical_impression': extract_impression(report)
    }
    
    # Filter out procedural and administrative content
    filtered_sections = {k: v for k, v in relevant_sections.items() if v}
    
    return filtered_sections

def create_staging_focused_report(relevant_sections: Dict[str, str], stage_type: str) -> str:
    """Create focused report for specific staging agent."""
    
    if stage_type == "T":
        # Focus on tumor characteristics
        focus_sections = ['findings', 'measurements', 'invasion_patterns', 'clinical_impression']
    else:  # N staging
        # Focus on lymph node characteristics  
        focus_sections = ['findings', 'lymph_nodes', 'measurements', 'clinical_impression']
    
    return combine_relevant_sections(relevant_sections, focus_sections)
```

**Expected Reduction**: 1,000-5,000 → 400-2,000 characters (50-60% reduction)

## Priority 3: Prompt Optimization (Medium Impact)

### Current Problem:
- **T staging prompt**: ~1,330 characters with verbose instructions
- **N staging prompt**: ~1,440 characters with complex N0/NX logic
- **Redundant instructions**: Similar content across prompts

### Implementation Approach:

#### 3a. Streamlined Prompt Templates
```python
# Before: Verbose instruction (1,330 chars)
VERBOSE_T_PROMPT = """
You are a radiologist expert in cancer staging. Analyze this radiologic report and determine the T stage according to AJCC guidelines.

Please analyze the following carefully:
1. Review the radiologic findings in detail
2. Consider the tumor size, invasion patterns, and anatomical involvement
3. Cross-reference with the provided AJCC staging guidelines
4. Determine the most appropriate T stage classification
5. Provide detailed rationale for your decision
...
"""

# After: Concise instruction (800 chars)
CONCISE_T_PROMPT = """
Analyze this radiologic report for T staging using AJCC guidelines.

REPORT: {report}
GUIDELINES: {guidelines}
BODY PART: {body_part}

Determine T stage considering:
- Tumor size/dimensions
- Invasion patterns  
- Anatomical involvement

Output JSON: {json_schema}
"""
```

**Expected Reduction**: 1,330-1,440 → 800-1,000 characters (25-40% reduction)

## Priority 4: Structured Output Optimization (Medium Impact)

### Current Problem:
- **Complex JSON schemas**: Detailed output requirements add instruction overhead
- **Validation logic**: Extensive rules for N0/NX distinction
- **Language validation**: Additional English-only requirements

### Implementation Approach:

#### 4a. Simplified JSON Schema
```python
# Before: Complex schema with extensive validation
COMPLEX_SCHEMA = {
    "t_stage": "string (T0, T1, T2, T3, T4, T4a, T4b, or TX)",
    "confidence": "float (0.0-1.0)",
    "rationale": "string (detailed explanation citing guidelines)",
    "extracted_info": {
        "tumor_size": "string or null",
        "invasion_pattern": "string or null", 
        "anatomical_involvement": "array of strings",
        "staging_factors": "array of strings"
    },
    "validation": {
        "guidelines_referenced": "boolean",
        "measurement_based": "boolean",
        "imaging_adequate": "boolean"
    }
}

# After: Essential schema only
ESSENTIAL_SCHEMA = {
    "t_stage": "string",
    "confidence": "float", 
    "rationale": "string"
}
```

**Expected Reduction**: 200-300 → 50-100 characters (50-75% reduction)

## Implementation Roadmap

### Phase 1: Guideline Filtering (Week 1)
1. **Implement medical table preservation**
2. **Add stage-specific content filtering**  
3. **Test with existing cases for accuracy**
4. **Measure context size reduction**

### Phase 2: Report Optimization (Week 2)
1. **Implement staging-relevant extraction**
2. **Create T/N-specific report versions**
3. **Validate medical accuracy maintained**
4. **Measure performance improvement**

### Phase 3: Prompt Streamlining (Week 3)
1. **Redesign prompt templates**
2. **Simplify JSON output requirements**
3. **Test instruction comprehension**
4. **Optimize for clarity and brevity**

### Phase 4: Integration Testing (Week 4)
1. **Combine all optimizations**
2. **End-to-end performance testing**
3. **Medical accuracy validation**
4. **Production deployment**

## Expected Performance Impact

### Conservative Estimates:
| Component | Current Size | Optimized Size | Reduction |
|-----------|--------------|----------------|-----------|
| Guidelines | 2,000-8,000 chars | 800-2,500 chars | 50-70% |
| Report | 1,000-5,000 chars | 400-2,000 chars | 50-60% |
| Prompt | 1,330-1,440 chars | 800-1,000 chars | 25-40% |
| **Total Context** | **4,500-14,500 chars** | **2,000-5,500 chars** | **55-62%** |

### Performance Improvements:
- **Current response time**: 37-40 seconds per staging agent
- **Expected response time**: 15-25 seconds per staging agent (**50-60% improvement**)
- **Total analysis time**: 170s → 85-110s (**35-50% improvement**)

## Risk Mitigation

### Medical Accuracy Safeguards:
1. **Preserve all medical tables** completely
2. **Validate staging results** against full guidelines in testing
3. **Maintain comprehensive rationale** requirements
4. **Test with diverse case types** before deployment

### Fallback Mechanisms:
1. **Context expansion**: If confidence drops, revert to full context
2. **Accuracy monitoring**: Track staging accuracy metrics continuously  
3. **Gradual rollout**: Implement optimizations incrementally
4. **A/B testing**: Compare optimized vs. original performance

---

**Next Steps**: Begin with Phase 1 (Guideline Filtering) as it offers the highest impact with lowest risk to medical accuracy.