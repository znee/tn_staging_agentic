# Language Validation System

## Overview

The language validation system ensures that all LLM outputs in the TN staging system are in English only, preventing mixed-language outputs that can confuse users and reduce system reliability.

## Problem Addressed

**Issue**: LLM outputs occasionally contained mixed English-Chinese text, such as:
- "upper颈内淋巴结" instead of "upper cervical lymph nodes"
- Medical terms appearing in Chinese characters
- Inconsistent language mixing affecting user experience

## Solution Components

### 1. Core Validation Function

```python
from utils.language_validation import validate_english_only

# Validate and clean text
cleaned_text = validate_english_only(
    text="Are there enlarged upper颈内淋巴结?",
    context="query_output"
)
# Result: "Are there enlarged upper cervical lymph nodes?"
```

### 2. Medical Term Replacements

Automatic replacement of common Chinese medical terms:

| Chinese | English |
|---------|---------|
| 颈内淋巴结 | cervical lymph nodes |
| 淋巴结 | lymph nodes |
| 颈部淋巴结 | cervical lymph nodes |
| 腋窝淋巴结 | axillary lymph nodes |
| 锁骨上淋巴结 | supraclavicular lymph nodes |
| 颈部 | neck |
| 肿瘤 | tumor |
| 癌 | cancer |

### 3. JSON Output Validation

```python
from utils.language_validation import validate_json_output

# Clean entire JSON structures
cleaned_json = validate_json_output(
    {"question": "What is the 肿瘤 size?"},
    context="agent_response"
)
# Result: {"question": "What is the tumor size?"}
```

### 4. Prompt Enhancement

```python
from utils.language_validation import add_language_validation_to_prompt

# Automatically add language requirements to prompts
enhanced_prompt = add_language_validation_to_prompt(
    "Generate questions about lymph nodes."
)
```

## Implementation Details

### File Location
`utils/language_validation.py`

### Key Functions

#### `validate_english_only(text, context, enable_validation)`
- **Purpose**: Validate and clean text for English-only output
- **Parameters**:
  - `text`: Input text to validate
  - `context`: Context description for logging
  - `enable_validation`: Whether validation is enabled (default: True)
- **Returns**: Cleaned English text

#### `apply_medical_term_replacements(text)`
- **Purpose**: Replace Chinese medical terms with English equivalents
- **Parameters**: `text` - Input text with potential Chinese terms
- **Returns**: Text with replaced terms

#### `validate_json_output(json_obj, context)`
- **Purpose**: Recursively validate JSON objects for English-only content
- **Parameters**: 
  - `json_obj` - JSON object (dict or list) to validate
  - `context` - Context description for logging
- **Returns**: Validated JSON object

#### `add_language_validation_to_prompt(prompt)`
- **Purpose**: Add language validation instructions to LLM prompts
- **Parameters**: `prompt` - Original prompt text
- **Returns**: Enhanced prompt with language requirements

### Global Configuration

```python
from utils.language_validation import set_language_validation, is_validation_enabled

# Enable/disable validation globally
set_language_validation(True)

# Check current status
if is_validation_enabled():
    print("Language validation is active")
```

## Usage Patterns

### 1. Agent Output Validation

```python
# In agent implementations
async def process(self, context):
    # Generate response
    response = await self.llm_provider.generate(prompt)
    
    # Validate language
    validated_response = validate_english_only(
        response, 
        f"{self.agent_id}_output"
    )
    
    return AgentMessage(data={"result": validated_response})
```

### 2. Query Agent Enhancement

The query agent now includes automatic validation:

```python
# Enhanced prompts with language requirements
prompt = f"""Generate questions about lymph nodes.

CRITICAL LANGUAGE REQUIREMENT: 
- OUTPUT MUST BE IN ENGLISH ONLY
- NO Chinese, Korean, Japanese, or other non-English characters
- Use only standard English medical terminology
"""

# Automatic validation of generated questions
validated_questions = self._validate_english_output(parsed_questions)
```

### 3. Error Handling

```python
try:
    cleaned_text = validate_english_only(text, "agent_output")
except Exception as e:
    logger.warning(f"Language validation failed: {e}")
    # Use fallback or original text
```

## Integration Points

### Current Implementations

1. **Query Agent** (`agents/query.py`):
   - Enhanced prompts with language requirements
   - Validation of generated questions
   - Fallback for mixed-language outputs

2. **Prompt Templates**:
   - Automatic addition of language validation instructions
   - Explicit English-only requirements in all LLM calls

### Future Applications

The validation system can be applied to:
- All agent outputs
- User input processing
- Report generation
- Error messages
- Logging output

## Configuration Options

### Environment Variables

```bash
# Disable language validation globally (for testing)
export TN_STAGING_LANGUAGE_VALIDATION=false
```

### Runtime Configuration

```python
# Temporary disable for specific operations
set_language_validation(False)
# ... perform operations
set_language_validation(True)
```

## Monitoring and Logging

The system provides detailed logging for:
- Detection of non-English characters
- Successful term replacements
- Validation failures
- Fallback usage

Example log output:
```
[language_validation] WARNING: Non-English characters detected in query_output: Are there enlarged upper颈内淋巴结...
[language_validation] INFO: Successfully cleaned non-English characters from query_output
```

## Testing

### Unit Tests

```python
def test_language_validation():
    # Test Chinese term replacement
    result = validate_english_only("enlarged 颈内淋巴结")
    assert "cervical lymph nodes" in result
    
    # Test JSON validation
    input_json = {"question": "What is the 肿瘤 size?"}
    result = validate_json_output(input_json)
    assert result["question"] == "What is the tumor size?"
```

### Integration Tests

```python
def test_query_agent_language_validation():
    # Test that query agent produces English-only output
    agent = QueryAgent(llm_provider)
    result = await agent.process(context)
    
    # Verify no non-English characters
    questions = result.data.get("context_Q", "")
    assert not re.search(r'[\u4e00-\u9fff]', questions)
```

## Best Practices

1. **Apply Early**: Validate LLM outputs immediately after generation
2. **Context Logging**: Always provide meaningful context for debugging
3. **Fallback Strategy**: Have fallback text for critical failures
4. **Global Toggle**: Allow disabling for testing/debugging
5. **Comprehensive Coverage**: Apply to all user-facing outputs

## Performance Impact

- **Minimal overhead**: Unicode regex operations are fast
- **Caching**: Term replacements use simple string operations
- **Optional**: Can be disabled for performance testing
- **Logging only**: No impact on functionality when validation passes

## Future Enhancements

1. **Extended Language Support**: Add support for other language combinations
2. **Smart Detection**: Use ML models for language detection
3. **User Preferences**: Allow users to choose preferred language
4. **Term Learning**: Automatically learn new medical term mappings
5. **Integration**: Connect with medical terminology databases