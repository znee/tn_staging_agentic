"""Enhanced LLM providers with structured JSON output support."""

import os
import logging
import json
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel
import asyncio

from agents.base import LLMProvider
from config.llm_providers import OpenAIProvider, OllamaProvider, HybridProvider


class StructuredOpenAIProvider(OpenAIProvider):
    """OpenAI provider with structured JSON output support."""
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON output using OpenAI's response_format.
        
        Args:
            prompt: Input prompt
            response_model: Pydantic model for response structure
            **kwargs: Additional generation parameters
            
        Returns:
            Parsed JSON response as dictionary
        """
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


class StructuredOllamaProvider(OllamaProvider):
    """Ollama provider with structured JSON output support."""
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured JSON output using Ollama's format parameter.
        
        Args:
            prompt: Input prompt
            response_model: Pydantic model for response structure
            **kwargs: Additional generation parameters
            
        Returns:
            Parsed JSON response as dictionary
        """
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
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    validated = response_model(**data)
                    return validated.model_dump()
            except:
                pass
            raise


class StructuredHybridProvider(HybridProvider):
    """Hybrid provider with structured output support."""
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate structured output using the generation provider.
        
        Args:
            prompt: Input prompt
            response_model: Pydantic model for response structure
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON response as dictionary
        """
        if hasattr(self.generation_provider, 'generate_structured'):
            return await self.generation_provider.generate_structured(
                prompt, response_model, **kwargs
            )
        else:
            # Fallback to standard generation + parsing
            response = await self.generation_provider.generate(prompt, **kwargs)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                validated = response_model(**data)
                return validated.model_dump()
            raise ValueError("Could not extract valid JSON from response")


# Staging response models using Pydantic
from pydantic import BaseModel, Field, field_validator
from typing import Optional


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


# Factory function to create structured providers
def create_structured_provider(backend: str, config: Optional[Dict[str, Any]] = None) -> LLMProvider:
    """Create structured LLM provider based on backend type.
    
    Args:
        backend: Backend type ("openai", "ollama", or "hybrid")
        config: Provider configuration
        
    Returns:
        Structured LLM provider instance
    """
    config = config or {}
    
    if backend.lower() == "openai":
        provider = StructuredOpenAIProvider(
            api_key=config.get("api_key"),
            model=config.get("model", "gpt-3.5-turbo")
        )
    elif backend.lower() == "ollama":
        provider = StructuredOllamaProvider(
            model=config.get("model", "qwen2.5:7b"),
            base_url=config.get("base_url", "http://localhost:11434"),
            embedding_model=config.get("embedding_model", "nomic-embed-text")
        )
    elif backend.lower() == "hybrid":
        gen_config = config.get("generation", {})
        embed_config = config.get("embedding", {})
        
        generation_provider = create_structured_provider(
            gen_config.get("backend", "ollama"),
            gen_config
        )
        
        embedding_provider = create_structured_provider(
            embed_config.get("backend", "openai"),
            embed_config
        )
        
        provider = StructuredHybridProvider(generation_provider, embedding_provider)
    else:
        raise ValueError(f"Unsupported backend: {backend}")
    
    return provider


# Export models for use in agents
__all__ = [
    'create_structured_provider',
    'TStagingResponse',
    'NStagingResponse', 
    'DetectionResponse',
    'QueryResponse',
    'CaseCharacteristicsResponse',
    'ReportResponse',
    'ExtractedInfo'
]