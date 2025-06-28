# Model-Agnostic Response Handling Strategy

**Date**: June 28, 2025  
**Purpose**: Implement centralized, model-agnostic handling of LLM response artifacts  
**Priority**: High - affects all agents and model compatibility

## Problem Statement

Different LLM models produce different output artifacts:
- **Qwen3**: Generates `<think>...</think>` tags with reasoning
- **Claude**: May use `<thinking>...</thinking>` tags
- **GPT/Llama/Mistral**: Typically don't use thinking tags

Current issues:
1. **Inconsistent handling**: Only 3/6 agents strip think tags
2. **Model-specific logic**: Hardcoded for Qwen3
3. **Context pollution**: Think tags may leak to downstream agents
4. **Maintenance burden**: Duplicated cleaning code

## Solution Architecture

### 1. Centralized Response Cleaner (`utils/llm_response_cleaner.py`)

```python
from utils.llm_response_cleaner import LLMResponseCleaner

# Create cleaner for specific model
cleaner = LLMResponseCleaner("qwen3:8b")

# Clean for display (removes all thinking)
display_text = cleaner.clean_for_display(raw_response)

# Clean for agent context (removes thinking but preserves content)
agent_context = cleaner.clean_for_agent_context(raw_response)

# Extract thinking for debugging/logging
thinking_content = cleaner.extract_thinking(raw_response)
```

### 2. Integration Points

#### Option A: Provider-Level Integration (RECOMMENDED)

Modify LLM providers to automatically clean responses:

```python
# In StructuredOllamaProvider
from utils.llm_response_cleaner import LLMResponseCleaner

class StructuredOllamaProvider(OllamaProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_cleaner = LLMResponseCleaner(self.model)
    
    async def generate(self, prompt: str, **kwargs) -> str:
        # Get raw response
        response = await super().generate(prompt, **kwargs)
        
        # Clean for agent use (preserve in logs for debugging)
        cleaned, thinking = self.response_cleaner.clean_response(response)
        
        # Log thinking content if present
        if thinking:
            self.logger.debug(f"Model thinking: {thinking[:200]}...")
        
        return cleaned
```

#### Option B: Agent-Level Integration

Each agent cleans responses individually:

```python
# In agents/staging_t.py
from utils.llm_response_cleaner import LLMResponseCleaner

class TStagingAgent(BaseAgent):
    def __init__(self, llm_provider):
        super().__init__("t_staging_agent", llm_provider)
        self.response_cleaner = LLMResponseCleaner.create_for_provider(llm_provider)
    
    async def _determine_t_stage_manual(self, ...):
        response = await self.llm_provider.generate(prompt)
        
        # Clean response before processing
        cleaned_response = self.response_cleaner.clean_for_agent_context(response)
        
        # Continue with JSON parsing...
```

### 3. Implementation Strategy

#### Phase 1: Provider Integration ✅
1. Update `OllamaProvider` and `OpenAIProvider` base classes
2. Add response cleaning to `generate()` method
3. Preserve thinking content in debug logs

#### Phase 2: Remove Agent-Level Cleaning
1. Remove regex patterns from individual agents
2. Trust provider-cleaned responses
3. Simplify agent code

#### Phase 3: Enhanced Features
1. Add thinking content to session metadata
2. Create thinking analysis tools
3. Model-specific optimization

### 4. Benefits

1. **Model Agnostic**: Easy to add new models
2. **Centralized Logic**: One place to maintain
3. **Consistent Behavior**: All agents get clean responses
4. **Debugging Support**: Thinking preserved in logs
5. **Performance**: No redundant cleaning

### 5. Configuration

Add to provider configuration:

```python
# In config/llm_providers_structured.py
RESPONSE_CLEANING_CONFIG = {
    "enabled": True,
    "preserve_thinking_in_logs": True,
    "log_thinking_threshold": 200,  # Log first 200 chars of thinking
    "model_overrides": {
        "qwen3:8b": {"strip_thinking": True},
        "claude-3": {"strip_thinking": True},
        "gpt-4": {"strip_thinking": False}
    }
}
```

### 6. Testing Considerations

1. **Model Switching**: Test with different models
2. **Content Preservation**: Ensure no medical content is lost
3. **Performance**: Measure cleaning overhead
4. **Edge Cases**: Handle malformed tags

### 7. Migration Path

1. **Week 1**: Implement LLMResponseCleaner
2. **Week 2**: Integrate into providers with feature flag
3. **Week 3**: Test with all models
4. **Week 4**: Remove agent-level cleaning

## Example: Current vs Proposed

### Current (Agent-Level)
```python
# In 6 different agents, inconsistently applied
cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
```

### Proposed (Provider-Level)
```python
# Automatically handled by provider
response = await self.llm_provider.generate(prompt)  # Already cleaned!
```

## Conclusion

This model-agnostic approach:
- **Solves** the think tag inconsistency
- **Prepares** for multi-model support
- **Simplifies** agent implementations
- **Improves** maintainability

The centralized cleaner handles model-specific quirks while providing a consistent interface for all agents.