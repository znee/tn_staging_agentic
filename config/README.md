# Guideline Configuration Management

This directory contains the CSV-based configuration system for managing cancer type to guideline mappings.

## Files

- **`guideline_mapping.csv`** - Main configuration file (edit this to change mappings)
- **`guideline_config.py`** - Python loader for the CSV configuration
- **`manage_guidelines.py`** - Command-line utility for managing mappings

## Quick Start

### View Current Mappings
```bash
python config/manage_guidelines.py list
```

### Add New Guideline (when PDF becomes available)
```bash
python config/manage_guidelines.py add lung lung lung_guidelines "Lung cancer staging guidelines"
```

### Mark Cancer Type as Unavailable
```bash
python config/manage_guidelines.py unavailable thyroid "No specific AJCC guidelines available"
```

### Check Specific Cancer Type
```bash
python config/manage_guidelines.py check "oral cavity"
```

### Validate Configuration
```bash
python config/manage_guidelines.py validate
```

## CSV Format

The `guideline_mapping.csv` file has the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `cancer_type` | Cancer type identifier | `oral_cavity` |
| `body_part` | Body part name (used for matching) | `oral cavity` |
| `guideline_store` | Store name for specialized guidelines | `oral_oropharyngeal` |
| `status` | `available` (only list available mappings) | `available` |
| `notes` | Optional description | `Primary oral cavity cancers` |

**Important**: Only include cancer types with specialized guidelines. All unmapped cancer types automatically use the general AJCC guidelines (`ajcc_guidelines_local`).

## Manual Editing

You can directly edit `guideline_mapping.csv` in any spreadsheet application:

1. Open `config/guideline_mapping.csv` in Excel/Google Sheets
2. Add/modify entries as needed
3. Save the file
4. The system will automatically use the updated configuration

## Adding New Guidelines

When a new AJCC guideline PDF becomes available:

1. **Add PDF to system**: Place PDF in `guidelines/pdfs/`
2. **Build vector store**: Run the tokenizer to create vector store
3. **Update mapping**: Either:
   - Edit CSV: Change `UNAVAILABLE` to the new store name
   - Use script: `python config/manage_guidelines.py add cancer_type body_part store_name`

## System Integration

The configuration is automatically loaded by `agents/retrieve_guideline.py`:

- ✅ **Specialized mappings**: Routes to specific vector stores (e.g., oral_oropharyngeal)
- 📚 **All unmapped types**: Automatically use general AJCC guidelines (ajcc_guidelines_local)
- 🔄 **No LLM generation**: Always uses guideline-based staging (principle-driven)
- 🛡️ **Fallback handling**: Graceful degradation if CSV loading fails

## Examples

### Current Configuration (Simplified)
```csv
cancer_type,body_part,guideline_store,status,notes
oral_cavity,oral cavity,oral_oropharyngeal,available,Primary oral cavity cancers
oropharynx,oropharynx,oral_oropharyngeal,available,Oropharyngeal cancers
tongue,tongue,oral_oropharyngeal,available,Tongue cancers
# Note: All unmapped cancer types (hypopharynx, lung, breast, etc.) 
# automatically use ajcc_guidelines_local
```

### Adding Lung Guidelines (Future)
When lung cancer PDF becomes available:
```csv
cancer_type,body_part,guideline_store,status,notes
lung,lung,lung_guidelines,available,Lung cancer staging guidelines added
```

## Benefits

- 📝 **Easy editing**: No Python code changes needed
- 🔄 **Hot reloading**: Changes take effect immediately  
- 📊 **Clear overview**: See all mappings in one file
- 🛡️ **Safe fallback**: System works even if CSV has issues
- 🎯 **Explicit control**: Clear distinction between available/unavailable guidelines

## Technical Notes

- CSV encoding: UTF-8
- Headers required: `cancer_type,body_part,guideline_store,status,notes`
- Case sensitivity: Body part matching is case-insensitive
- Validation: Built-in validation and error handling