"""Global language validation utilities for LLM outputs."""

import re
import logging
from typing import Any, Dict, List, Union

logger = logging.getLogger("language_validation")

def validate_english_only(text: str, context: str = "LLM output", 
                         enable_validation: bool = True) -> str:
    """Validate and clean text to ensure English-only output.
    
    Args:
        text: Input text to validate
        context: Context description for logging
        enable_validation: Whether to enable validation (can be disabled globally)
        
    Returns:
        Cleaned English-only text
    """
    if not enable_validation:
        return text
    
    if not text or not isinstance(text, str):
        return text
    
    # Check for non-Latin characters (Chinese, Korean, Japanese, etc.)
    non_latin_pattern = r'[\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7af\u3040-\u309f\u30a0-\u30ff]'
    has_non_latin = bool(re.search(non_latin_pattern, text))
    
    if has_non_latin:
        logger.warning(f"Non-English characters detected in {context}: {text[:50]}...")
        
        # Apply replacements for common medical terms
        cleaned_text = apply_medical_term_replacements(text)
        
        # Check if cleaning resolved the issue
        if re.search(non_latin_pattern, cleaned_text):
            logger.warning(f"Could not clean all non-English characters from {context}")
            # Return original text but log the issue for monitoring
            return cleaned_text
        else:
            logger.info(f"Successfully cleaned non-English characters from {context}")
            return cleaned_text
    
    return text

def apply_medical_term_replacements(text: str) -> str:
    """Apply common medical term replacements for mixed-language text.
    
    Args:
        text: Input text that may contain non-English medical terms
        
    Returns:
        Text with replaced terms
    """
    # Common Chinese medical terms to English
    replacements = {
        # Lymph node terms
        "颈内淋巴结": "cervical lymph nodes",
        "淋巴结": "lymph nodes", 
        "颈部淋巴结": "cervical lymph nodes",
        "腋窝淋巴结": "axillary lymph nodes",
        "锁骨上淋巴结": "supraclavicular lymph nodes",
        
        # Anatomical regions
        "颈部": "neck",
        "上颈": "upper cervical",
        "下颈": "lower cervical",
        "胸部": "chest",
        "腹部": "abdomen",
        
        # Tumor/staging terms
        "肿瘤": "tumor",
        "癌": "cancer",
        "分期": "staging",
        "大小": "size",
        
        # General medical terms
        "患者": "patient",
        "病例": "case",
        "诊断": "diagnosis",
        "治疗": "treatment"
    }
    
    cleaned_text = text
    for chinese, english in replacements.items():
        cleaned_text = cleaned_text.replace(chinese, english)
    
    return cleaned_text

def validate_json_output(json_obj: Union[Dict, List], context: str = "JSON output") -> Union[Dict, List]:
    """Validate JSON object for English-only content.
    
    Args:
        json_obj: JSON object (dict or list) to validate
        context: Context description for logging
        
    Returns:
        Validated JSON object
    """
    def clean_recursive(obj):
        if isinstance(obj, str):
            return validate_english_only(obj, f"{context} string")
        elif isinstance(obj, dict):
            return {k: clean_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_recursive(item) for item in obj]
        else:
            return obj
    
    return clean_recursive(json_obj)

def add_language_validation_to_prompt(prompt: str) -> str:
    """Add language validation instructions to any LLM prompt.
    
    Args:
        prompt: Original prompt
        
    Returns:
        Prompt with language validation instructions
    """
    language_instructions = """
CRITICAL LANGUAGE REQUIREMENT: 
- OUTPUT MUST BE IN ENGLISH ONLY
- NO Chinese, Korean, Japanese, or other non-English characters
- NO mixed language output
- Use only standard English medical terminology

"""
    
    # Insert language instructions after any existing instructions
    if prompt.strip().startswith("INSTRUCTIONS:") or prompt.strip().startswith("You are"):
        # Find end of first instruction block
        lines = prompt.split('\n')
        insert_pos = 1
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "" or not line.startswith(("INSTRUCTIONS", "You are", "-", "•")):
                insert_pos = i
                break
        
        lines.insert(insert_pos, language_instructions)
        return '\n'.join(lines)
    else:
        # Prepend to prompt
        return language_instructions + prompt

# Global configuration
ENABLE_LANGUAGE_VALIDATION = True

def set_language_validation(enabled: bool):
    """Enable or disable language validation globally.
    
    Args:
        enabled: Whether to enable validation
    """
    global ENABLE_LANGUAGE_VALIDATION
    ENABLE_LANGUAGE_VALIDATION = enabled
    logger.info(f"Language validation {'enabled' if enabled else 'disabled'}")

def is_validation_enabled() -> bool:
    """Check if language validation is enabled."""
    return ENABLE_LANGUAGE_VALIDATION