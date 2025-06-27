# Workflow Optimization Guide

## Overview

The TN staging system has been optimized to avoid unnecessary re-staging when user responses are provided. This reduces LLM API calls by up to 50% while maintaining accuracy.

## Problem Solved

**Before optimization:**
- User query scenario: T2 (high confidence) + NX (low confidence)
- User provides lymph node information
- System re-runs BOTH T and N staging agents
- Wastes computational resources on T staging (already confident)

**After optimization:**
- Same scenario: T2 (0.95 confidence) + NX (0.4 confidence)
- User provides lymph node information
- System only re-runs N staging agent
- Preserves T2 result, updates N staging with new information

## Implementation

### Using Optimized Context Manager

```python
from contexts.context_manager_optimized import OptimizedContextManager, OptimizedWorkflowOrchestrator

# Replace standard context manager
context_manager = OptimizedContextManager()
orchestrator = OptimizedWorkflowOrchestrator(agents, context_manager)

# Run initial analysis
results = await orchestrator.run_initial_workflow()

# Continue with user response (optimized)
if results.get("query_needed"):
    user_response = "Multiple enlarged lymph nodes in right neck"
    final_results = await orchestrator.continue_workflow_with_response(user_response)
```

### Re-staging Logic

The system decides whether to re-run staging agents based on:

1. **T Staging Re-run Criteria:**
   - Current stage is "TX" (undetermined)
   - Confidence score < 0.7

2. **N Staging Re-run Criteria:**
   - Current stage is "NX" (undetermined)
   - Confidence score < 0.7

### Integration with Structured Outputs

The optimization works seamlessly with structured JSON outputs:

```python
from config.llm_providers_structured import create_structured_provider
from contexts.context_manager_optimized import OptimizedWorkflowOrchestrator

# Create structured provider
provider = create_structured_provider("ollama")

# Use with optimized workflow
orchestrator = OptimizedWorkflowOrchestrator(agents, context_manager)
```

## Performance Benefits

### Scenario Analysis

| Scenario | T Stage | T Conf | N Stage | N Conf | T Re-run | N Re-run | Savings |
|----------|---------|--------|---------|--------|----------|----------|---------|
| 1        | T2      | 0.95   | NX      | 0.4    | ❌       | ✅       | 50%     |
| 2        | T2      | 0.9    | N2      | 0.85   | ❌       | ❌       | 100%    |
| 3        | TX      | 0.3    | NX      | 0.2    | ✅       | ✅       | 0%      |

### Real-world Impact

- **Common case (T2NX)**: 50% reduction in LLM calls
- **High confidence cases**: 100% reduction (no re-staging)
- **Uncertain cases (TX/NX)**: No performance loss, same accuracy

## Usage Examples

### Example 1: T2NX Scenario
```python
# Initial staging: T2 (confident) + NX (uncertain)
# User provides: "Multiple 2cm nodes in right neck"
# Result: Only N staging re-runs, T2 preserved

orchestrator = OptimizedWorkflowOrchestrator(agents, context_manager)
results = await orchestrator.run_initial_workflow()

if results["query_needed"]:
    # Only N staging will be re-run
    final = await orchestrator.continue_workflow_with_response(
        "Multiple enlarged lymph nodes, largest 2cm in right level II"
    )
```

### Example 2: Both High Confidence
```python
# Initial staging: T2 (0.9) + N2 (0.85)
# Result: No query generated, no re-staging needed

results = await orchestrator.run_initial_workflow()
# results["query_needed"] will be False
# Final report generated immediately
```

## Monitoring and Logging

The optimized workflow provides detailed logging:

```python
# Enable session logging to track optimization
session_logger.log_event("workflow_optimization", {
    "agents_rerun": ["N"],  # Only N staging re-run
    "t_skipped": True,      # T staging skipped
    "n_skipped": False,     # N staging re-run
    "t_confidence": 0.95,   # High T confidence
    "n_confidence": 0.4     # Low N confidence
})
```

## Migration Guide

To migrate from the standard workflow to optimized:

1. **Replace imports:**
   ```python
   # Old
   from contexts.context_manager import ContextManager, WorkflowOrchestrator
   
   # New
   from contexts.context_manager_optimized import OptimizedContextManager, OptimizedWorkflowOrchestrator
   ```

2. **Update initialization:**
   ```python
   # Old
   context_manager = ContextManager()
   orchestrator = WorkflowOrchestrator(agents, context_manager)
   
   # New
   context_manager = OptimizedContextManager()
   orchestrator = OptimizedWorkflowOrchestrator(agents, context_manager)
   ```

3. **No API changes needed** - same methods, optimized behavior

## Configuration

### Confidence Threshold

The default confidence threshold is 0.7. To customize:

```python
class CustomOptimizedContextManager(OptimizedContextManager):
    def __init__(self, confidence_threshold: float = 0.8):
        super().__init__()
        self.confidence_threshold = confidence_threshold
    
    def needs_t_restaging(self) -> bool:
        return (
            self.context.context_T == "TX" or 
            (self.context.context_CT is not None and 
             self.context.context_CT < self.confidence_threshold)
        )
```

## Testing

Run the optimization tests:

```bash
python tests/test_workflow_optimization.py
```

Expected output confirms:
- T2NX: Only N staging re-runs
- High confidence: No re-staging
- TX/NX: Both agents re-run as needed

## Backwards Compatibility

The optimized workflow is fully backwards compatible:
- Same API as standard workflow
- Same output format
- Enhanced performance without accuracy loss