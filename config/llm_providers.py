"""LLM provider implementations for OpenAI and Ollama backends."""

import os
import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import asyncio

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agents.base import LLMProvider

class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (optional, will use env var)
            model: Model name to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.logger = logging.getLogger("openai_provider")
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Initialize OpenAI client
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
            self.openai_client = True  # Flag for other components
        except ImportError:
            raise ImportError("openai package is required for OpenAI provider")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt using OpenAI.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a medical AI assistant specialized in cancer staging. Provide accurate, evidence-based responses."},
                    {"role": "user", "content": prompt}
                ],
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=kwargs.get("max_tokens", 2000),
                top_p=kwargs.get("top_p", 0.9)
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"OpenAI generation failed: {str(e)}")
            raise
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            self.logger.error(f"OpenAI embedding failed: {str(e)}")
            raise

class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation."""
    
    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text"
    ):
        """Initialize Ollama provider.
        
        Args:
            model: Ollama model name
            base_url: Ollama server URL
            embedding_model: Model for embeddings
        """
        self.model = model
        self.base_url = base_url
        # Handle model names with and without :latest suffix
        if embedding_model == "nomic-embed-text" and not embedding_model.endswith(":latest"):
            # Check what's actually available
            try:
                import requests
                response = requests.get(f"{base_url}/api/tags", timeout=2)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m["name"] for m in models]
                    # Use the exact name that's available
                    for name in model_names:
                        if "nomic-embed-text" in name:
                            embedding_model = name
                            break
            except:
                pass
        self.embedding_model = embedding_model
        self.logger = logging.getLogger("ollama_provider")
        
        # Log the specific models being used
        self.logger.info(f"Initializing Ollama provider:")
        self.logger.info(f"  - Generation model: {self.model}")
        self.logger.info(f"  - Embedding model: {self.embedding_model}")
        self.logger.info(f"  - Base URL: {self.base_url}")
        
        # Initialize Ollama client
        try:
            import ollama
            # Create async client
            self.client = ollama.AsyncClient(host=base_url)
            self.embed_client = ollama.AsyncClient(host=base_url)
        except ImportError:
            raise ImportError("ollama package is required for Ollama provider")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt using Ollama.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text
        """
        try:
            # Log the generation request
            self.logger.debug(f"Generating with model: {self.model}, prompt length: {len(prompt)}")
            
            # Build system message for medical context
            system_message = """You are a medical AI assistant specialized in cancer staging using AJCC guidelines. 
Provide accurate, evidence-based responses. When analyzing reports:
1. Be conservative in staging decisions
2. Use TX/NX when information is insufficient
3. Provide clear rationale for all decisions
4. Focus on objective findings from imaging reports"""
            
            response = await self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
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
            
            generated_text = response['message']['content'].strip()
            self.logger.debug(f"Generated response length: {len(generated_text)}")
            
            return generated_text
            
        except Exception as e:
            self.logger.error(f"Ollama generation failed with model {self.model}: {str(e)}")
            raise
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using Ollama.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        try:
            response = await self.embed_client.embeddings(
                model=self.embedding_model,
                prompt=text
            )
            
            return response['embedding']
            
        except Exception as e:
            self.logger.error(f"Ollama embedding failed: {str(e)}")
            raise

class LLMProviderFactory:
    """Factory for creating LLM providers."""
    
    @staticmethod
    def create_provider(
        backend: str,
        config: Optional[Dict[str, Any]] = None
    ) -> LLMProvider:
        """Create LLM provider based on backend type.
        
        Args:
            backend: Backend type ("openai" or "ollama")
            config: Provider configuration
            
        Returns:
            LLM provider instance
        """
        config = config or {}
        
        if backend.lower() == "openai":
            return OpenAIProvider(
                api_key=config.get("api_key"),
                model=config.get("model", "gpt-3.5-turbo")
            )
        elif backend.lower() == "ollama":
            return OllamaProvider(
                model=config.get("model", "qwen2.5:7b"),
                base_url=config.get("base_url", "http://localhost:11434"),
                embedding_model=config.get("embedding_model", "nomic-embed-text")
            )
        else:
            raise ValueError(f"Unsupported backend: {backend}")
    
    @staticmethod
    def get_recommended_models(backend: str) -> Dict[str, List[str]]:
        """Get recommended models for each backend.
        
        Args:
            backend: Backend type
            
        Returns:
            Dictionary with model recommendations
        """
        if backend.lower() == "openai":
            return {
                "text_generation": ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"],
                "embeddings": ["text-embedding-3-small", "text-embedding-3-large"]
            }
        elif backend.lower() == "ollama":
            return {
                "text_generation": ["qwen3:8b", "qwen2.5:7b", "llama3.2:latest"],
                "embeddings": ["nomic-embed-text", "all-minilm:l6-v2"]
            }
        else:
            return {}

class HybridProvider(LLMProvider):
    """Hybrid provider that uses cloud embeddings and local generation."""
    
    def __init__(
        self,
        generation_provider: LLMProvider,
        embedding_provider: LLMProvider
    ):
        """Initialize hybrid provider.
        
        Args:
            generation_provider: Provider for text generation
            embedding_provider: Provider for embeddings
        """
        self.generation_provider = generation_provider
        self.embedding_provider = embedding_provider
        self.logger = logging.getLogger("hybrid_provider")
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using local provider.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        return await self.generation_provider.generate(prompt, **kwargs)
    
    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using cloud provider.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        return await self.embedding_provider.embed(text)

def create_hybrid_provider(config: Dict[str, Any]) -> HybridProvider:
    """Create hybrid provider with separate generation and embedding backends.
    
    Args:
        config: Configuration with 'generation' and 'embedding' sections
        
    Returns:
        Hybrid provider instance
    """
    factory = LLMProviderFactory()
    
    gen_config = config.get("generation", {})
    embed_config = config.get("embedding", {})
    
    generation_provider = factory.create_provider(
        gen_config.get("backend", "ollama"),
        gen_config
    )
    
    embedding_provider = factory.create_provider(
        embed_config.get("backend", "openai"),
        embed_config
    )
    
    return HybridProvider(generation_provider, embedding_provider)