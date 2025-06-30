"""Unified LLM provider implementations with all features integrated.

This module consolidates:
- Base providers (OpenAI, Ollama, Hybrid)
- Structured JSON output with Pydantic validation
- Enhanced response cleaning with model-agnostic support
- All Pydantic response models for staging agents
"""

import os
import logging
import json
import re
from typing import Dict, Any, Optional, List, Type
from abc import ABC, abstractmethod
import asyncio
from pathlib import Path

# Pydantic imports for structured responses
from pydantic import BaseModel, Field, field_validator

# Base LLM provider interface
import sys
sys.path.append(str(Path(__file__).parent.parent))
from agents.base import LLMProvider

# Response cleaner for enhanced functionality
from utils.llm_response_cleaner import LLMResponseCleaner


# ============================================================================
# Pydantic Response Models (from llm_providers_structured.py)
# ============================================================================

class ExtractedInfo(BaseModel):
    """Information extracted from radiologic report."""
    tumor_size: Optional[str] = Field(None, description="Tumor dimensions from report")
    largest_dimension: Optional[str] = Field(None, description="Largest dimension with units (e.g., '5.4 cm')")
    invasions: List[str] = Field(default_factory=list, description="Invaded structures")
    extensions: List[str] = Field(default_factory=list, description="Extension locations")
    multiple_tumors: bool = Field(False, description="Multiple tumors present")
    key_findings: List[str] = Field(default_factory=list, description="Key findings")


class TStagingResponse(BaseModel):
    """T staging response structure."""
    t_stage: str = Field(..., pattern=r'^(T[0-4][a-z]?|TX)$', description="T stage classification")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    rationale: str = Field(..., min_length=10, description="Staging rationale")
    extracted_info: ExtractedInfo = Field(default_factory=ExtractedInfo)
    
    @field_validator('t_stage')
    @classmethod
    def validate_t_stage(cls, v: str) -> str:
        """Ensure T stage is uppercase."""
        return v.upper()


class NStagingResponse(BaseModel):
    """N staging response structure."""
    n_stage: str = Field(..., pattern=r'^(N[0-3][a-c]?|NX)$', description="N stage classification")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    rationale: str = Field(..., min_length=10, description="Staging rationale")
    node_info: Dict[str, Any] = Field(default_factory=dict, description="Node information")
    
    @field_validator('n_stage')
    @classmethod
    def validate_n_stage(cls, v: str) -> str:
        """Ensure N stage is uppercase."""
        return v.upper()


class DetectionResponse(BaseModel):
    """Body part and cancer type detection response."""
    body_part: str = Field(..., min_length=2, description="Detected body part")
    cancer_type: str = Field(..., min_length=2, description="Cancer type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    additional_info: Optional[str] = Field(None, description="Additional information")


class QueryResponse(BaseModel):
    """Query generation response."""
    question: str = Field(..., min_length=10, description="Question for user")
    context_needed: List[str] = Field(..., description="Information needed")
    priority: str = Field("high", pattern=r'^(high|medium|low)$')


class CaseCharacteristicsResponse(BaseModel):
    """Case characteristics extraction response."""
    case_summary: str = Field(..., min_length=10, description="Extracted case characteristics for semantic retrieval")
    key_features: List[str] = Field(default_factory=list, description="Key staging-relevant features")


class ReportResponse(BaseModel):
    """Report generation response."""
    recommendations: str = Field(..., min_length=10, description="Clinical recommendations")
    next_steps: List[str] = Field(default_factory=list, description="Recommended next steps")
    confidence_notes: Optional[str] = Field(None, description="Notes about staging confidence")


# ============================================================================
# Unified Provider Implementations
# ============================================================================

class UnifiedOpenAIProvider(LLMProvider):
    """Unified OpenAI provider with all features: base, structured, and enhanced."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """Initialize unified OpenAI provider.
        
        Args:
            api_key: OpenAI API key (optional, will use env var)
            model: Model name to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.logger = logging.getLogger(f"openai_provider.{self.model}")
        self.provider_type = "openai"
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Initialize OpenAI client
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
            self.openai_client = True  # Flag for other components
        except ImportError:
            raise ImportError("openai package is required for OpenAI provider")
            
        # Enhanced features
        self.response_cleaner = LLMResponseCleaner(self.model)
        self.session_logger = None  # Will be set by main system
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text with response cleaning."""
        import time
        start_time = time.time()
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=kwargs.get("max_tokens", 2000),
                top_p=kwargs.get("top_p", 0.9)
            )
            
            raw_response = response.choices[0].message.content.strip()
            response_time = time.time() - start_time
            
            # Clean response (GPT models typically don't have thinking tags)
            cleaned_response, thinking_content = self.response_cleaner.clean_response(raw_response)
            
            # Log to session logger if available
            if self.session_logger and hasattr(self.session_logger, 'log_llm_response'):
                try:
                    import inspect
                    frame = inspect.currentframe()
                    agent_name = "unknown"
                    
                    # Walk up the stack to find agent context
                    while frame:
                        frame_info = frame.f_locals
                        if 'self' in frame_info:
                            obj = frame_info['self']
                            if hasattr(obj, '__class__') and 'Agent' in obj.__class__.__name__:
                                agent_name = obj.__class__.__name__.replace('Agent', '').lower()
                                break
                        frame = frame.f_back
                    
                    self.session_logger.log_llm_response(
                        agent_name=agent_name,
                        model_name=self.model,
                        raw_response=raw_response,
                        cleaned_response=cleaned_response,
                        thinking_content=thinking_content,
                        prompt_preview=prompt[:200] + "..." if len(prompt) > 200 else prompt,
                        response_time=response_time
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to log LLM response: {e}")
            
            if len(raw_response) != len(cleaned_response):
                self.logger.debug(f"Cleaned {len(raw_response) - len(cleaned_response)} chars from response")
            
            return cleaned_response
            
        except Exception as e:
            self.logger.error(f"OpenAI generation failed: {str(e)}")
            raise
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON output using OpenAI's response_format."""
        try:
            # Use response_format with JSON mode
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical AI assistant specialized in cancer staging. "
                                   "Provide accurate, evidence-based responses in valid JSON format."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=kwargs.get("max_tokens", 2000),
                top_p=kwargs.get("top_p", 0.9)
            )
            
            # Parse and validate with Pydantic model
            json_str = response.choices[0].message.content.strip()
            data = json.loads(json_str)
            
            # Validate with Pydantic model
            validated = response_model(**data)
            return validated.model_dump()
            
        except Exception as e:
            self.logger.error(f"OpenAI structured generation failed: {str(e)}")
            raise
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI."""
        try:
            response = await self.client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"OpenAI embedding failed: {str(e)}")
            raise


class UnifiedOllamaProvider(LLMProvider):
    """Unified Ollama provider with all features: base, structured, and enhanced."""
    
    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434", 
                 embedding_model: str = "nomic-embed-text"):
        """Initialize unified Ollama provider.
        
        Args:
            model: Model name to use
            base_url: Ollama server URL
            embedding_model: Model for embeddings
        """
        self.model = model
        self.base_url = base_url
        self.embedding_model = embedding_model
        self.logger = logging.getLogger(f"ollama_provider.{self.model}")
        self.provider_type = "ollama"
        
        # Initialize Ollama client
        try:
            import ollama
            self.client = ollama.AsyncClient(host=base_url)
        except ImportError:
            raise ImportError("ollama package is required for Ollama provider")
            
        # Enhanced features
        self.response_cleaner = LLMResponseCleaner(self.model)
        self.preserve_thinking_in_logs = True
        self.session_logger = None  # Will be set by main system
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text with response cleaning."""
        import time
        start_time = time.time()
        
        try:
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": kwargs.get("temperature", 0.1),
                    "top_p": kwargs.get("top_p", 0.9),
                    "top_k": kwargs.get("top_k", 40),
                    "num_predict": kwargs.get("max_tokens", 2000),
                    "stop": kwargs.get("stop", [])
                }
            )
            
            raw_response = response['message']['content']
            response_time = time.time() - start_time
            
            # Clean response
            cleaned_response, thinking_content = self.response_cleaner.clean_response(
                raw_response, 
                preserve_thinking=False
            )
            
            # Log to session logger if available
            if self.session_logger and hasattr(self.session_logger, 'log_llm_response'):
                try:
                    import inspect
                    frame = inspect.currentframe()
                    agent_name = "unknown"
                    
                    # Walk up the stack to find agent context
                    while frame:
                        frame_info = frame.f_locals
                        if 'self' in frame_info:
                            obj = frame_info['self']
                            if hasattr(obj, '__class__') and 'Agent' in obj.__class__.__name__:
                                agent_name = obj.__class__.__name__.replace('Agent', '').lower()
                                break
                        frame = frame.f_back
                    
                    self.session_logger.log_llm_response(
                        agent_name=agent_name,
                        model_name=self.model,
                        raw_response=raw_response,
                        cleaned_response=cleaned_response,
                        thinking_content=thinking_content,
                        prompt_preview=prompt[:200] + "..." if len(prompt) > 200 else prompt,
                        response_time=response_time
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to log LLM response: {e}")
            
            # Log thinking content if present and significant
            if thinking_content and self.preserve_thinking_in_logs:
                thinking_preview = thinking_content[:200] + "..." if len(thinking_content) > 200 else thinking_content
                self.logger.debug(f"Model thinking ({self.model}): {thinking_preview}")
                
                # Also log character count for performance tracking
                self.logger.debug(f"Removed {len(raw_response) - len(cleaned_response)} chars of thinking/artifacts")
            
            return cleaned_response
            
        except Exception as e:
            self.logger.error(f"Ollama generation failed: {str(e)}")
            raise
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON output using Ollama's format parameter."""
        try:
            # Build JSON schema from Pydantic model
            schema = response_model.model_json_schema()
            
            # Create system message with explicit JSON instruction
            system_message = (
                "You are a medical AI assistant specialized in cancer staging using AJCC guidelines. "
                "Provide accurate, evidence-based responses in valid JSON format matching the schema provided."
            )
            
            # Enhanced prompt with schema
            enhanced_prompt = f"""
{prompt}

CRITICAL: You must respond with ONLY valid JSON that matches this exact schema:
{json.dumps(schema, indent=2)}

Begin your response with {{ and end with }}. No other text allowed.
"""
            
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": enhanced_prompt}
                ],
                format=schema,  # Use Ollama's format parameter (dict, not JSON string)
                options={
                    "temperature": kwargs.get("temperature", 0.1),
                    "top_p": kwargs.get("top_p", 0.9),
                    "top_k": kwargs.get("top_k", 40),
                    "num_predict": kwargs.get("max_tokens", 2000),
                    "stop": kwargs.get("stop", [])
                }
            )
            
            # Parse and validate response
            json_str = response['message']['content'].strip()
            
            # Clean common artifacts
            json_str = json_str.strip('`').strip()
            if json_str.startswith('json'):
                json_str = json_str[4:].strip()
            
            data = json.loads(json_str)
            
            # Validate with Pydantic model
            validated = response_model(**data)
            return validated.model_dump()
            
        except Exception as e:
            self.logger.error(f"Ollama structured generation failed: {str(e)}")
            # Fallback to standard generation + parsing
            try:
                response = await self.generate(prompt, **kwargs)
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    validated = response_model(**data)
                    return validated.model_dump()
            except:
                pass
            raise
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using Ollama."""
        try:
            response = await self.client.embeddings(
                model=self.embedding_model,
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            self.logger.error(f"Ollama embedding failed: {str(e)}")
            raise


class UnifiedHybridProvider(LLMProvider):
    """Unified hybrid provider with separate generation and embedding providers."""
    
    def __init__(self, generation_provider: LLMProvider, embedding_provider: LLMProvider):
        """Initialize hybrid provider.
        
        Args:
            generation_provider: Provider for text generation
            embedding_provider: Provider for embeddings
        """
        self.generation_provider = generation_provider
        self.embedding_provider = embedding_provider
        self.logger = logging.getLogger("hybrid_provider")
        self.provider_type = "hybrid"
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate using the generation provider."""
        return await self.generation_provider.generate(prompt, **kwargs)
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured output using the generation provider."""
        if hasattr(self.generation_provider, 'generate_structured'):
            return await self.generation_provider.generate_structured(
                prompt, response_model, **kwargs
            )
        else:
            # Fallback to standard generation + parsing
            response = await self.generation_provider.generate(prompt, **kwargs)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                validated = response_model(**data)
                return validated.model_dump()
            raise ValueError("Could not extract valid JSON from response")
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using the embedding provider."""
        return await self.embedding_provider.embed(text)


# ============================================================================
# Configuration and Factory Functions
# ============================================================================

def get_openai_config() -> Dict[str, Any]:
    """Get OpenAI configuration."""
    return {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
        "embedding_model": "text-embedding-ada-002"
    }


def get_ollama_config() -> Dict[str, Any]:
    """Get Ollama configuration."""
    return {
        "model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "embedding_model": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    }


def get_hybrid_config() -> Dict[str, Any]:
    """Get hybrid configuration."""
    return {
        "generation": get_ollama_config(),
        "embedding": get_openai_config()
    }


def validate_openai_config(config: Dict[str, Any]) -> bool:
    """Validate OpenAI configuration."""
    return bool(config.get("api_key"))


def validate_ollama_config(config: Dict[str, Any]) -> bool:
    """Validate Ollama configuration."""
    return bool(config.get("model"))


def create_llm_provider(backend: str, config: Optional[Dict[str, Any]] = None) -> LLMProvider:
    """Unified factory function for creating LLM providers.
    
    This replaces create_enhanced_provider, create_structured_provider, etc.
    All providers now have full functionality (structured + enhanced).
    
    Args:
        backend: Backend type ("openai", "ollama", or "hybrid")
        config: Provider configuration
        
    Returns:
        Unified LLM provider instance with all features
    """
    config = config or {}
    
    if backend.lower() == "openai":
        provider = UnifiedOpenAIProvider(
            api_key=config.get("api_key"),
            model=config.get("model", "gpt-3.5-turbo")
        )
    elif backend.lower() == "ollama":
        provider = UnifiedOllamaProvider(
            model=config.get("model", "qwen2.5:7b"),
            base_url=config.get("base_url", "http://localhost:11434"),
            embedding_model=config.get("embedding_model", "nomic-embed-text")
        )
    elif backend.lower() == "hybrid":
        gen_config = config.get("generation", {})
        embed_config = config.get("embedding", {})
        
        generation_provider = create_llm_provider("ollama", gen_config)
        embedding_provider = create_llm_provider("openai", embed_config)
        
        provider = UnifiedHybridProvider(generation_provider, embedding_provider)
    else:
        raise ValueError(f"Unsupported backend: {backend}")
    
    return provider


# Note: Consolidated from create_enhanced_provider, create_structured_provider
# All providers now have full functionality (structured + enhanced)


def create_hybrid_provider(config: Dict[str, Any]) -> UnifiedHybridProvider:
    """Create hybrid provider (backward compatibility)."""
    return create_llm_provider("hybrid", config)


class LLMProviderFactory:
    """Factory for creating LLM providers (backward compatibility)."""
    
    @staticmethod
    def create_provider(backend: str, config: Optional[Dict[str, Any]] = None) -> LLMProvider:
        """Create provider using the unified factory."""
        return create_llm_provider(backend, config)


# Export everything for backward compatibility
__all__ = [
    # Unified providers
    'UnifiedOpenAIProvider',
    'UnifiedOllamaProvider', 
    'UnifiedHybridProvider',
    
    # Response models
    'TStagingResponse',
    'NStagingResponse',
    'DetectionResponse',
    'QueryResponse',
    'CaseCharacteristicsResponse',
    'ReportResponse',
    'ExtractedInfo',
    
    # Factory functions
    'create_llm_provider',
    'create_hybrid_provider',
    'LLMProviderFactory',
    
    # Configuration
    'get_openai_config',
    'get_ollama_config',
    'get_hybrid_config',
    'validate_openai_config',
    'validate_ollama_config'
]