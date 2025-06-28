# ROLLBACK MEMO - Phase 1 Implementation

**Date**: June 28, 2025  
**Task**: Implementing model-agnostic response cleaning (Phase 1)  
**Safety**: Rollback capability documented

## Current System State

### Git Status
- **Current Branch**: master
- **Last Commit**: `26a4bf6` - "chore: Clean up project folder structure"
- **GitHub Sync**: Up to date with origin/master
- **Working Directory**: Clean (no staged changes)

### Local Modifications (NOT YET COMMITTED)
#### Modified Files:
- `ARCHITECTURE.md` - Updated with v2.0.4 info
- `CHANGELOG.md` - Added v2.0.4 entry
- `README.md` - Updated version to v2.0.4
- `docs/structured_json_implementation.md` - Updated status to production

#### New Files (Documentation):
- `docs/model_agnostic_response_handling.md` - Strategy document
- `docs/release_notes_v2.0.4.md` - Release notes
- `config/llm_providers_enhanced.py` - Enhanced providers (NOT USED YET)
- `utils/llm_response_cleaner.py` - Response cleaner (NOT USED YET)

### Current Think Tag Handling (TO BE TESTED)

Current implementation in 3 agents uses this pattern:
```python
cleaned_response = re.sub(r'<think>.*?</think>', '', cleaned_response, flags=re.DOTALL)
```

**Agents with think tag cleaning**:
1. `agents/staging_t.py` (line ~206)
2. `agents/staging_n.py` (line ~232) 
3. `agents/retrieve_guideline.py` (line ~873)

**Agents WITHOUT think tag cleaning**:
1. `agents/detect.py`
2. `agents/query.py`
3. `agents/report.py`

## Phase 1 Plan

### Step 1: Test LLMResponseCleaner ✅
- Create unit tests for response cleaner
- Verify it properly handles Qwen3's `<think>` tags
- Ensure no content loss

### Step 2: Modify JSONL Logging
- Update logging to preserve raw LLM outputs
- Add `raw_response` field to JSONL entries
- Maintain existing `response` field with cleaned output

### Step 3: Test Integration Points
- Test with existing Qwen3:8b model
- Compare cleaned vs raw outputs
- Verify staging accuracy unchanged

### Step 4: Rollback Preparation
- Create rollback script if needed
- Document exact file changes
- Test rollback procedure

## Rollback Instructions

### If Phase 1 Fails - Quick Rollback:

1. **Undo file changes**:
```bash
# Reset to last commit (keeps documentation)
git checkout HEAD -- agents/ config/llm_providers.py main.py utils/logging_config.py

# OR restore specific files if needed
git checkout HEAD -- <specific-file>
```

2. **Keep new documentation**:
- All `docs/*.md` files should be preserved
- New utility files can remain but won't be used

3. **Verify system works**:
```bash
python main.py --backend ollama --report "test report"
```

### Critical Files to Monitor:
- `main.py` - If we modify provider initialization
- `utils/logging_config.py` - If we modify JSONL logging
- `config/llm_providers.py` - If we add cleaning integration

## Success Criteria for Phase 1

1. **Functionality**: System works exactly as before
2. **Performance**: No degradation in analysis speed
3. **Accuracy**: Same staging results for test cases
4. **Logging**: Raw responses preserved in JSONL
5. **Debugging**: Think content available for analysis

## Test Cases to Verify

1. **Standard Report**: Run existing test report through system
2. **Think Tag Report**: Verify `<think>` content removed from display
3. **JSONL Logging**: Check raw vs cleaned content in logs
4. **Model Switching**: Test if ready for other models (future)

## Contingency Plan

If any issues arise:
1. **Immediate**: Use rollback instructions above
2. **Debug**: Keep raw response files for analysis  
3. **Report**: Document specific failure points
4. **Retry**: Fix issues and re-attempt with safer approach

---

**Note**: This memo ensures we can safely test the new response cleaning without risking the current working system. All changes will be incremental and reversible.