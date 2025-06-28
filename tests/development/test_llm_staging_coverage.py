#!/usr/bin/env python3
"""Test LLM-based staging coverage analysis."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.llm_providers_structured import create_structured_provider
from agents.retrieve_guideline import GuidelineRetrievalAgent

async def test_llm_staging_coverage():
    """Test LLM-based staging coverage analysis."""
    
    print("=== Testing LLM-Based Staging Coverage Analysis ===")
    
    # Create provider
    provider = create_structured_provider("ollama", {
        "model": "qwen3:8b",
        "base_url": "http://localhost:11434"
    })
    
    # Test sample guidelines
    test_t_guidelines = """
    T STAGING FOR ORAL CAVITY CANCER
    
    T0: No evidence of primary tumor
    T1: Tumor ≤2 cm in greatest dimension and ≤5 mm depth of invasion
    T2: Tumor ≤2 cm in greatest dimension and depth of invasion >5 mm and ≤10 mm, 
        OR tumor >2 cm but ≤4 cm in greatest dimension and ≤10 mm depth of invasion
    T3: Tumor >4 cm in greatest dimension OR any tumor >10 mm depth of invasion
    T4a: Moderately advanced local disease
    T4b: Very advanced local disease
    """
    
    test_n_guidelines = """
    N STAGING FOR ORAL CAVITY CANCER
    
    N0: No regional lymph node metastasis
    N1: Metastasis in a single ipsilateral lymph node, ≤3 cm in greatest dimension
    N2a: Metastasis in a single ipsilateral lymph node >3 cm but ≤6 cm
    N2b: Metastasis in multiple ipsilateral lymph nodes, none >6 cm
    N2c: Metastasis in bilateral or contralateral lymph nodes, none >6 cm
    N3: Metastasis in any lymph node >6 cm in greatest dimension
    """
    
    # Create agent instance
    agent = GuidelineRetrievalAgent(provider)
    
    try:
        print("\n--- Testing T Staging Coverage Analysis ---")
        t_coverage = await agent._analyze_staging_coverage_llm(
            test_t_guidelines, "T", "oral cavity", "squamous cell carcinoma"
        )
        print(f"T Coverage Result: {t_coverage}")
        
        # Check if it found the expected stages
        expected_t_stages = ["t0", "t1", "t2", "t3", "t4a", "t4b"]
        found_stages = t_coverage.split(", ")
        
        print(f"Expected: {expected_t_stages}")
        print(f"Found: {found_stages}")
        
        if all(stage in t_coverage for stage in expected_t_stages):
            print("✅ T staging coverage analysis successful!")
        else:
            print("⚠️ Some T stages missing from analysis")
        
        print("\n--- Testing N Staging Coverage Analysis ---") 
        n_coverage = await agent._analyze_staging_coverage_llm(
            test_n_guidelines, "N", "oral cavity", "squamous cell carcinoma"
        )
        print(f"N Coverage Result: {n_coverage}")
        
        # Check if it found the expected stages
        expected_n_stages = ["n0", "n1", "n2a", "n2b", "n2c", "n3"]
        found_n_stages = n_coverage.split(", ")
        
        print(f"Expected: {expected_n_stages}")
        print(f"Found: {found_n_stages}")
        
        if all(stage in n_coverage for stage in expected_n_stages):
            print("✅ N staging coverage analysis successful!")
        else:
            print("⚠️ Some N stages missing from analysis")
            
        print(f"\n🎯 Benefits of LLM-based approach:")
        print(f"   - Adapts to different body part staging systems")
        print(f"   - No hardcoded medical rules")
        print(f"   - Understands context and subdivisions")
        print(f"   - Respects LLM-first architecture")
        
    except Exception as e:
        print(f"❌ Error testing staging coverage: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_llm_staging_coverage())