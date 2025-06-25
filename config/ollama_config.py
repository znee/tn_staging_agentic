"""Ollama configuration settings."""

import os
from typing import Dict, Any

def get_ollama_config() -> Dict[str, Any]:
    """Get Ollama configuration from environment variables.
    
    Returns:
        Ollama configuration dictionary
    """
    return {
        "backend": "ollama",
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "model": os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        "embedding_model": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.1")),
        "max_tokens": int(os.getenv("OLLAMA_MAX_TOKENS", "2000")),
        "top_p": float(os.getenv("OLLAMA_TOP_P", "0.9")),
        "top_k": int(os.getenv("OLLAMA_TOP_K", "40")),
        
        # Vector store settings
        "vector_store": {
            "type": "faiss",
            "path": os.getenv("OLLAMA_VECTOR_STORE_PATH", "faiss_stores/ajcc_guidelines_local"),
            "index_name": "ajcc_guideline_local",
            "similarity_top_k": int(os.getenv("SIMILARITY_TOP_K", "5")),
            "similarity_cutoff": float(os.getenv("SIMILARITY_CUTOFF", "0.7"))
        },
        
        # Staging confidence thresholds (more conservative for local models)
        "confidence_thresholds": {
            "high": float(os.getenv("HIGH_CONFIDENCE_THRESHOLD", "0.7")),
            "medium": float(os.getenv("MEDIUM_CONFIDENCE_THRESHOLD", "0.5")),
            "minimum_for_staging": float(os.getenv("MIN_STAGING_CONFIDENCE", "0.4")),
            "require_query_below": float(os.getenv("QUERY_THRESHOLD", "0.6"))
        },
        
        # Local model performance settings
        "performance": {
            "timeout_seconds": int(os.getenv("OLLAMA_TIMEOUT", "120")),
            "max_retries": int(os.getenv("OLLAMA_MAX_RETRIES", "3")),
            "context_length": int(os.getenv("OLLAMA_CONTEXT_LENGTH", "4096"))
        }
    }

def get_hybrid_config() -> Dict[str, Any]:
    """Get hybrid configuration (local generation + cloud embeddings).
    
    Returns:
        Hybrid configuration dictionary
    """
    return {
        "backend": "hybrid",
        "generation": {
            "backend": "ollama",
            "model": os.getenv("OLLAMA_MODEL", "qwen3:8b"),
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.1")),
            "max_tokens": int(os.getenv("OLLAMA_MAX_TOKENS", "2000"))
        },
        "embedding": {
            "backend": "openai",
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        },
        "vector_store": {
            "type": "faiss",
            "path": os.getenv("HYBRID_VECTOR_STORE_PATH", "faiss_stores/ajcc_guidelines_hybrid"),
            "index_name": "ajcc_guideline_hybrid",
            "similarity_top_k": int(os.getenv("SIMILARITY_TOP_K", "5")),
            "similarity_cutoff": float(os.getenv("SIMILARITY_CUTOFF", "0.7"))
        },
        "confidence_thresholds": {
            "high": float(os.getenv("HIGH_CONFIDENCE_THRESHOLD", "0.75")),
            "medium": float(os.getenv("MEDIUM_CONFIDENCE_THRESHOLD", "0.55")),
            "minimum_for_staging": float(os.getenv("MIN_STAGING_CONFIDENCE", "0.45")),
            "require_query_below": float(os.getenv("QUERY_THRESHOLD", "0.65"))
        }
    }

def validate_ollama_config(config: Dict[str, Any]) -> bool:
    """Validate Ollama configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if configuration is valid
    """
    required_fields = ["base_url", "model", "embedding_model"]
    
    for field in required_fields:
        if not config.get(field):
            print(f"Error: {field} is required for Ollama configuration")
            return False
    
    # Test connection to Ollama server
    try:
        import requests
        response = requests.get(f"{config['base_url']}/api/tags", timeout=5)
        if response.status_code != 200:
            print(f"Error: Cannot connect to Ollama server at {config['base_url']}")
            return False
    except Exception as e:
        print(f"Error: Cannot connect to Ollama server: {str(e)}")
        return False
    
    return True

# Model recommendations based on performance testing
RECOMMENDED_MODELS = {
    "text_generation": {
        "best_performance": "qwen3:8b",
        "alternative": "qwen2.5:7b", 
        "lightweight": "llama3.2:latest"
    },
    "embeddings": {
        "best_performance": "nomic-embed-text",
        "alternative": "all-minilm:l6-v2"
    }
}

# Default configuration for development
DEFAULT_OLLAMA_CONFIG = {
    "backend": "ollama",
    "base_url": "http://localhost:11434",
    "model": "qwen3:8b",
    "embedding_model": "nomic-embed-text",
    "temperature": 0.1,
    "max_tokens": 2000,
    "top_p": 0.9,
    "top_k": 40,
    "vector_store": {
        "type": "faiss",
        "path": "faiss_stores/ajcc_guidelines_local",
        "index_name": "ajcc_guideline_local",
        "similarity_top_k": 5,
        "similarity_cutoff": 0.7
    },
    "confidence_thresholds": {
        "high": 0.7,
        "medium": 0.5,
        "minimum_for_staging": 0.4,
        "require_query_below": 0.6
    }
}