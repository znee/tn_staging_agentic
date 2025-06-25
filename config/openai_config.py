"""OpenAI configuration settings."""

import os
from typing import Dict, Any

def get_openai_config() -> Dict[str, Any]:
    """Get OpenAI configuration from environment variables.
    
    Returns:
        OpenAI configuration dictionary
    """
    return {
        "backend": "openai",
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.1")),
        "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", "2000")),
        "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        
        # Vector store settings
        "vector_store": {
            "type": "faiss",
            "path": os.getenv("OPENAI_VECTOR_STORE_PATH", "faiss_stores/ajcc_guidelines_openai"),
            "index_name": "ajcc_guideline_openai",
            "similarity_top_k": int(os.getenv("SIMILARITY_TOP_K", "5")),
            "similarity_cutoff": float(os.getenv("SIMILARITY_CUTOFF", "0.7"))
        },
        
        # Staging confidence thresholds
        "confidence_thresholds": {
            "high": float(os.getenv("HIGH_CONFIDENCE_THRESHOLD", "0.8")),
            "medium": float(os.getenv("MEDIUM_CONFIDENCE_THRESHOLD", "0.6")),
            "minimum_for_staging": float(os.getenv("MIN_STAGING_CONFIDENCE", "0.5")),
            "require_query_below": float(os.getenv("QUERY_THRESHOLD", "0.7"))
        },
        
        # Rate limiting
        "rate_limit": {
            "requests_per_minute": int(os.getenv("OPENAI_RPM", "60")),
            "tokens_per_minute": int(os.getenv("OPENAI_TPM", "90000"))
        }
    }

def validate_openai_config(config: Dict[str, Any]) -> bool:
    """Validate OpenAI configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if configuration is valid
    """
    required_fields = ["api_key", "model"]
    
    for field in required_fields:
        if not config.get(field):
            print(f"Error: {field} is required for OpenAI configuration")
            return False
    
    return True

# Default configuration for development
DEFAULT_OPENAI_CONFIG = {
    "backend": "openai",
    "model": "gpt-3.5-turbo",
    "temperature": 0.1,
    "max_tokens": 2000,
    "embedding_model": "text-embedding-3-small",
    "vector_store": {
        "type": "faiss",
        "path": "faiss_stores/ajcc_guidelines_openai",
        "index_name": "ajcc_guideline_openai",
        "similarity_top_k": 5,
        "similarity_cutoff": 0.7
    },
    "confidence_thresholds": {
        "high": 0.8,
        "medium": 0.6,
        "minimum_for_staging": 0.5,
        "require_query_below": 0.7
    }
}