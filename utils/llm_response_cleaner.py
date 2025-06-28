"""
Model-agnostic LLM response cleaning utilities.

This module provides centralized cleaning functions for different LLM models'
output formats, including thinking/reasoning sections, artifacts, and other
model-specific patterns.
"""

import re
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class LLMResponseCleaner:
    """Centralized cleaner for model-specific LLM output patterns."""
    
    # Model-specific patterns
    MODEL_PATTERNS = {
        "qwen": {
            "thinking": r'<think>.*?</think>',
            "artifacts": [r'```json\s*', r'```\s*$'],
            "description": "Qwen models with <think> reasoning tags"
        },
        "claude": {
            "thinking": r'<thinking>.*?</thinking>',
            "artifacts": [r'```json\s*', r'```\s*$'],
            "description": "Claude models with <thinking> tags"
        },
        "gpt": {
            "thinking": None,  # GPT models don't typically use thinking tags
            "artifacts": [r'```json\s*', r'```\s*$'],
            "description": "OpenAI GPT models"
        },
        "llama": {
            "thinking": None,  # Llama models don't use thinking tags
            "artifacts": [r'```json\s*', r'```\s*$'],
            "description": "Meta Llama models"
        },
        "mistral": {
            "thinking": None,  # Mistral models don't use thinking tags
            "artifacts": [r'```json\s*', r'```\s*$'],
            "description": "Mistral models"
        }
    }
    
    def __init__(self, model_name: str = None):
        """
        Initialize the response cleaner.
        
        Args:
            model_name: The model name (e.g., 'qwen3:8b', 'gpt-4', 'claude-3')
        """
        self.model_name = model_name
        self.model_type = self._detect_model_type(model_name)
        logger.info(f"Initialized LLMResponseCleaner for model type: {self.model_type}")
    
    def _detect_model_type(self, model_name: Optional[str]) -> str:
        """Detect the model type from the model name."""
        if not model_name:
            return "generic"
        
        model_lower = model_name.lower()
        
        # Check for known model patterns
        if "qwen" in model_lower:
            return "qwen"
        elif "claude" in model_lower:
            return "claude"
        elif "gpt" in model_lower:
            return "gpt"
        elif "llama" in model_lower:
            return "llama"
        elif "mistral" in model_lower:
            return "mistral"
        else:
            return "generic"
    
    def clean_response(self, response: str, preserve_thinking: bool = False) -> Tuple[str, Optional[str]]:
        """
        Clean LLM response based on model type.
        
        Args:
            response: Raw LLM response
            preserve_thinking: Whether to preserve thinking/reasoning content
            
        Returns:
            Tuple of (cleaned_response, thinking_content)
        """
        if not response:
            return "", None
        
        cleaned = response
        thinking_content = None
        
        # Extract and optionally remove thinking content
        if self.model_type in self.MODEL_PATTERNS:
            pattern_info = self.MODEL_PATTERNS[self.model_type]
            thinking_pattern = pattern_info.get("thinking")
            
            if thinking_pattern:
                # Extract thinking content first
                thinking_matches = re.findall(thinking_pattern, cleaned, flags=re.DOTALL)
                if thinking_matches:
                    thinking_content = "\n".join(thinking_matches)
                    logger.debug(f"Extracted {len(thinking_matches)} thinking sections")
                
                # Remove thinking tags unless we want to preserve them
                if not preserve_thinking:
                    cleaned = re.sub(thinking_pattern, '', cleaned, flags=re.DOTALL)
                    logger.debug("Removed thinking tags from response")
            
            # Clean common artifacts
            for artifact_pattern in pattern_info.get("artifacts", []):
                cleaned = re.sub(artifact_pattern, '', cleaned)
        
        # General cleaning
        cleaned = cleaned.strip()
        
        # Log if significant content was removed
        if len(response) - len(cleaned) > 100:
            logger.info(f"Cleaned {len(response) - len(cleaned)} characters from response")
        
        return cleaned, thinking_content
    
    def clean_for_display(self, response: str) -> str:
        """
        Clean response for display to users (removes all thinking/reasoning).
        
        Args:
            response: Raw LLM response
            
        Returns:
            Cleaned response suitable for display
        """
        cleaned, _ = self.clean_response(response, preserve_thinking=False)
        return cleaned
    
    def clean_for_agent_context(self, response: str) -> str:
        """
        Clean response for passing to other agents (removes thinking but preserves content).
        
        Args:
            response: Raw LLM response
            
        Returns:
            Cleaned response suitable for agent context
        """
        cleaned, _ = self.clean_response(response, preserve_thinking=False)
        return cleaned
    
    def extract_thinking(self, response: str) -> Optional[str]:
        """
        Extract only the thinking/reasoning content from response.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Extracted thinking content or None
        """
        _, thinking = self.clean_response(response, preserve_thinking=True)
        return thinking
    
    @classmethod
    def create_for_provider(cls, llm_provider) -> 'LLMResponseCleaner':
        """
        Create a response cleaner based on the LLM provider.
        
        Args:
            llm_provider: The LLM provider instance
            
        Returns:
            Configured LLMResponseCleaner instance
        """
        model_name = None
        
        # Extract model name from provider
        if hasattr(llm_provider, 'model'):
            model_name = llm_provider.model
        elif hasattr(llm_provider, 'model_name'):
            model_name = llm_provider.model_name
        
        return cls(model_name)


# Convenience functions for backward compatibility
def clean_llm_response(response: str, model_name: str = None, preserve_thinking: bool = False) -> Tuple[str, Optional[str]]:
    """
    Clean an LLM response with model-specific handling.
    
    Args:
        response: Raw LLM response
        model_name: The model that generated the response
        preserve_thinking: Whether to preserve thinking content
        
    Returns:
        Tuple of (cleaned_response, thinking_content)
    """
    cleaner = LLMResponseCleaner(model_name)
    return cleaner.clean_response(response, preserve_thinking)


def strip_thinking_tags(response: str, model_name: str = None) -> str:
    """
    Remove thinking tags from response (backward compatibility).
    
    Args:
        response: Raw LLM response
        model_name: The model that generated the response
        
    Returns:
        Response with thinking tags removed
    """
    cleaner = LLMResponseCleaner(model_name)
    return cleaner.clean_for_display(response)