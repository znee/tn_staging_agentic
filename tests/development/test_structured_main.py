#!/usr/bin/env python3
"""Test script to verify main system uses structured providers."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import TNStagingSystem

async def test_main_structured():
    """Test that main system uses structured providers."""
    
    print("=== Testing Main System with Structured Providers ===")
    
    # Initialize system
    try:
        system = TNStagingSystem(backend="ollama", debug=True)
        # System initializes automatically in constructor
        
        # Check if the provider has structured output capability
        provider = system.llm_provider
        
        print(f"Provider type: {type(provider).__name__}")
        print(f"Has generate_structured: {hasattr(provider, 'generate_structured')}")
        
        if hasattr(provider, 'generate_structured'):
            print("✅ SUCCESS: Main system using structured provider!")
            
            # Check if staging agents are using structured methods
            t_agent = system.agents["staging_t"] 
            n_agent = system.agents["staging_n"]
            
            print(f"T agent has structured method: {hasattr(t_agent, '_determine_t_stage_structured')}")
            print(f"N agent has structured method: {hasattr(n_agent, '_determine_n_stage_structured')}")
            
        else:
            print("❌ FAIL: Main system still using regular provider")
            
    except Exception as e:
        print(f"❌ Error initializing system: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_main_structured())