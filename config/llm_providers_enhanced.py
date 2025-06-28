"""
Enhanced LLM providers with integrated response cleaning.
This module shows how to integrate model-agnostic response cleaning
into the existing provider architecture.
"""

from typing import Dict, Any, Optional
import logging
from config.llm_providers_structured import (
    StructuredOllamaProvider,
    StructuredOpenAIProvider,
    StructuredHybridProvider
)
from utils.llm_response_cleaner import LLMResponseCleaner


class EnhancedOllamaProvider(StructuredOllamaProvider):
    """Ollama provider with integrated response cleaning."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_cleaner = LLMResponseCleaner(self.model)
        self.preserve_thinking_in_logs = True
        self.logger = logging.getLogger(f"ollama_provider.{self.model}")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate response with automatic cleaning."""
        # Get raw response from parent
        raw_response = await super().generate(prompt, **kwargs)
        
        # Clean response
        cleaned_response, thinking_content = self.response_cleaner.clean_response(
            raw_response, 
            preserve_thinking=False
        )
        
        # Log thinking content if present and significant
        if thinking_content and self.preserve_thinking_in_logs:
            thinking_preview = thinking_content[:200] + "..." if len(thinking_content) > 200 else thinking_content
            self.logger.debug(f"Model thinking ({self.model}): {thinking_preview}")
            
            # Also log character count for performance tracking
            self.logger.debug(f"Removed {len(raw_response) - len(cleaned_response)} chars of thinking/artifacts")
        
        return cleaned_response
    
    async def generate_with_thinking(self, prompt: str, **kwargs) -> Dict[str, str]:
        """Generate response and return both cleaned content and thinking."""
        # Get raw response
        raw_response = await super().generate(prompt, **kwargs)
        
        # Clean and extract
        cleaned_response, thinking_content = self.response_cleaner.clean_response(
            raw_response, 
            preserve_thinking=True
        )
        
        return {
            "response": cleaned_response,
            "thinking": thinking_content,
            "raw": raw_response
        }


class EnhancedOpenAIProvider(StructuredOpenAIProvider):
    """OpenAI provider with integrated response cleaning."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response_cleaner = LLMResponseCleaner(self.model)
        self.logger = logging.getLogger(f"openai_provider.{self.model}")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate response with automatic cleaning."""
        # Get raw response
        raw_response = await super().generate(prompt, **kwargs)
        
        # Clean response (GPT models typically don't have thinking tags)
        cleaned_response, _ = self.response_cleaner.clean_response(raw_response)
        
        if len(raw_response) != len(cleaned_response):
            self.logger.debug(f"Cleaned {len(raw_response) - len(cleaned_response)} chars from response")
        
        return cleaned_response


def create_enhanced_provider(backend: str, config: Optional[Dict[str, Any]] = None):
    """
    Create enhanced LLM provider with integrated response cleaning.
    
    This is a drop-in replacement for create_structured_provider that adds
    automatic response cleaning for all models.
    """
    config = config or {}
    
    if backend.lower() == "openai":
        provider = EnhancedOpenAIProvider(
            api_key=config.get("api_key"),
            model=config.get("model", "gpt-3.5-turbo")
        )
    elif backend.lower() == "ollama":
        provider = EnhancedOllamaProvider(
            model=config.get("model", "qwen2.5:7b"),
            base_url=config.get("base_url", "http://localhost:11434"),
            embedding_model=config.get("embedding_model", "nomic-embed-text")
        )
    elif backend.lower() == "hybrid":
        # Create enhanced providers for hybrid
        gen_config = config.get("generation", {})
        embed_config = config.get("embedding", {})
        
        generation_provider = create_enhanced_provider(
            gen_config.get("backend", "ollama"),
            gen_config
        )
        
        embedding_provider = create_enhanced_provider(
            embed_config.get("backend", "openai"),
            embed_config
        )
        
        provider = StructuredHybridProvider(generation_provider, embedding_provider)
    else:
        raise ValueError(f"Unsupported backend: {backend}")
    
    return provider


# Example usage in main.py:
# Simply replace:
#   from config.llm_providers_structured import create_structured_provider
# With:
#   from config.llm_providers_enhanced import create_enhanced_provider
#
# And update the initialization:
#   self.llm_provider = create_enhanced_provider(self.backend, self.config)