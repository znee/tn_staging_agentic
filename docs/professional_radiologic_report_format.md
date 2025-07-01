# Professional Radiologic Cancer Staging Report Format

## Current Issues with Report Format

Our current report format lacks the professional structure and detailed findings expected in radiologic cancer staging reports. The format needs to follow established radiology reporting standards.

## Professional Radiologic Report Structure

### Standard Radiologic Cancer Staging Report Components

#### 1. **CLINICAL INFORMATION**
- Patient demographics (anonymized for our system)
- Clinical history and presentation
- Referring physician and indication
- Previous imaging/studies

#### 2. **TECHNIQUE**
- Imaging modality and protocol
- Contrast administration details
- Technical parameters
- Limitations or quality issues

#### 3. **FINDINGS**
- **Primary Tumor Assessment**
  - Location and anatomical relationships
  - Size measurements (multi-dimensional)
  - Morphological characteristics
  - Local extension and invasion patterns
  - Enhancement characteristics
  - Signal/density characteristics

- **Regional Lymph Nodes**
  - Systematic evaluation by anatomical levels
  - Size, morphology, and enhancement patterns
  - Number and distribution
  - Suspicious characteristics (necrosis, extra-capsular extension)

- **Distant Disease Assessment**
  - Systematic organ evaluation
  - Suspicious lesions with characteristics
  - Additional findings

#### 4. **IMPRESSION**
- **TNM Staging Assessment**
  - T-stage with specific criteria referenced
  - N-stage with nodal level specification
  - M-stage if assessed
  - Overall stage grouping

- **Key Imaging Features**
  - Critical findings for staging
  - Surgical planning considerations
  - Response assessment (if follow-up)

#### 5. **RECOMMENDATIONS**
- Further imaging if needed
- Correlation with clinical/pathological findings
- Follow-up timing and modality
- Multidisciplinary team discussion

## Enhanced LLM Prompts for Professional Format

### Primary Tumor Assessment Prompt
```
Generate detailed radiologic findings for the primary tumor based on this report:
[Report text]

Format as professional radiologic findings including:
- Precise anatomical location with adjacent structure relationships
- Multi-dimensional measurements
- Morphological characteristics (irregular/smooth margins, heterogeneous/homogeneous)
- Local extension patterns with specific anatomical structures involved
- Enhancement characteristics if described
- Critical features for T-staging determination

Use professional radiologic terminology and be specific about anatomical relationships.
```

### Regional Lymph Node Assessment Prompt
```
Generate systematic lymph node assessment based on this report:
[Report text]

Format as professional radiologic findings including:
- Systematic evaluation by cervical levels (I, II, III, IV, V) or appropriate anatomical regions
- Individual node characteristics: size (short and long axis), morphology, enhancement
- Suspicious features: central necrosis, extra-capsular extension, round morphology
- Distribution patterns and laterality
- Correlation with primary tumor drainage patterns

Use standard anatomical nomenclature for lymph node levels and professional descriptive language.
```

### Professional Report Template
```
RADIOLOGIC STAGING ASSESSMENT

CLINICAL INFORMATION:
Primary Site: [body_part]
Histology: [cancer_type] (if known)
Clinical Stage: [clinical_stage_group]

IMAGING FINDINGS:

PRIMARY TUMOR:
Location: [detailed anatomical location]
Size: [multi-dimensional measurements]
Morphology: [detailed morphological description]
Local Extension: [specific anatomical structures involved]
Enhancement: [enhancement characteristics if available]
Staging Considerations: [specific features relevant to T-staging]

REGIONAL LYMPH NODES:
[Systematic evaluation by anatomical levels]
Level I: [findings]
Level II: [findings]
Level III: [findings]
Level IV: [findings]
Level V: [findings]
[Additional levels as appropriate]

Suspicious Features: [necrosis, ECE, morphology]
Staging Considerations: [specific features relevant to N-staging]

DISTANT DISEASE:
[Assessment if available, otherwise note limitation]

RADIOLOGIC STAGING ASSESSMENT:
Primary Tumor (T): [T-stage] - [specific AJCC criteria referenced]
Regional Nodes (N): [N-stage] - [specific criteria and levels involved]
Distant Metastases (M): [M-stage or "not assessed"]

Overall Clinical Stage: [stage grouping]

CONFIDENCE ASSESSMENT:
T-staging confidence: [percentage] - [rationale]
N-staging confidence: [percentage] - [rationale]

LIMITATIONS:
[Technical limitations, incomplete coverage, correlation needs]

RECOMMENDATIONS:
[Specific imaging recommendations]
[Clinical correlation needs]
[Follow-up recommendations]
[Multidisciplinary discussion suggestions]
```

## Implementation Plan

### 1. Enhanced Report Agent Modifications
- Separate prompts for primary tumor and lymph node assessment
- Professional radiologic terminology integration
- Structured findings generation with anatomical detail
- Systematic evaluation protocols

### 2. New Report Sections
- Detailed FINDINGS section with systematic assessment
- Professional TECHNIQUE section (even if limited from reports)
- Enhanced RECOMMENDATIONS with imaging-specific guidance
- LIMITATIONS section for transparency

### 3. LLM Prompt Engineering
- Anatomically-specific prompts for different cancer types
- Professional radiology language requirements
- Systematic evaluation protocols
- Reference to standard nomenclature (BI-RADS, LI-RADS analogs)

### 4. Quality Improvements
- Multi-dimensional size reporting
- Anatomical level-specific lymph node assessment
- Enhancement pattern descriptions
- Professional morphological characterization

This approach will transform our reports from generic staging summaries to professional radiologic cancer staging assessments that follow established medical imaging standards.