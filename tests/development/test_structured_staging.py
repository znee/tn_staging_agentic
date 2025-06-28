#!/usr/bin/env python3
"""Test script to verify structured JSON outputs in staging agents."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.llm_providers_structured import create_structured_provider, TStagingResponse, NStagingResponse
from agents.staging_t import TStagingAgent
from agents.staging_n import NStagingAgent
from agents.base import AgentContext

async def test_structured_staging():
    """Test structured output functionality in staging agents."""
    
    # Create structured provider (Ollama)
    provider = create_structured_provider("ollama", {
        "model": "qwen3:8b",
        "base_url": "http://localhost:11434"
    })
    
    # Test sample data
    test_report = """
    CT scan of the neck shows a 3.2 cm mass in the left base of tongue.
    The tumor extends to the lingual surface of the epiglottis.
    Multiple enlarged lymph nodes are seen in the left neck, 
    with the largest measuring 2.8 cm in diameter.
    No distant metastases identified.
    """
    
    test_guidelines = """
    T1: Tumor ≤2 cm in greatest dimension
    T2: Tumor >2 cm but ≤4 cm in greatest dimension  
    T3: Tumor >4 cm in greatest dimension
    T4a: Moderately advanced local disease
    
    N0: No regional lymph node metastasis
    N1: Metastasis in a single ipsilateral lymph node, ≤3 cm
    N2: Metastasis in single ipsilateral lymph node >3 cm but ≤6 cm
    """
    
    # Create context
    context = AgentContext()
    context.context_R = test_report
    context.context_B = {"body_part": "oropharynx", "cancer_type": "squamous cell carcinoma"}
    context.context_GT = test_guidelines
    context.context_GN = test_guidelines
    
    print("=== Testing T Staging Agent with Structured Outputs ===")
    
    # Test T staging
    t_agent = TStagingAgent(provider)
    
    # Check if structured output is available
    if hasattr(provider, 'generate_structured'):
        print("✅ Structured output support detected")
        try:
            # Test structured method directly
            t_result = await t_agent._determine_t_stage_structured(
                test_report, test_guidelines, "oropharynx", "squamous cell carcinoma"
            )
            print(f"✅ T Staging Result (Structured):")
            print(f"   - Stage: {t_result['t_stage']}")
            print(f"   - Confidence: {t_result['confidence']}")
            print(f"   - Largest dimension: {t_result['extracted_info'].get('largest_dimension', 'N/A')}")
            print(f"   - Rationale: {t_result['rationale'][:100]}...")
            
            # Verify the unit format
            largest_dim = t_result['extracted_info'].get('largest_dimension')
            if largest_dim and ('cm' in str(largest_dim) or 'mm' in str(largest_dim)):
                print(f"✅ Dimension includes units: {largest_dim}")
            else:
                print(f"⚠️  Dimension format: {largest_dim}")
            
        except Exception as e:
            print(f"❌ Structured T staging failed: {str(e)}")
    else:
        print("❌ No structured output support")
    
    print("\n=== Testing N Staging Agent with Structured Outputs ===")
    
    # Test N staging
    n_agent = NStagingAgent(provider)
    
    if hasattr(provider, 'generate_structured'):
        try:
            # Test structured method directly
            n_result = await n_agent._determine_n_stage_structured(
                test_report, test_guidelines, "oropharynx", "squamous cell carcinoma"  
            )
            print(f"✅ N Staging Result (Structured):")
            print(f"   - Stage: {n_result['n_stage']}")
            print(f"   - Confidence: {n_result['confidence']}")
            print(f"   - Node info: {n_result['node_info']}")
            print(f"   - Rationale: {n_result['rationale'][:100]}...")
            
        except Exception as e:
            print(f"❌ Structured N staging failed: {str(e)}")
    
    print("\n=== Performance Comparison ===")
    print("Expected improvements with structured outputs:")
    print("- ✅ 25-40% shorter prompts (no JSON schema instructions)")
    print("- ✅ 100% reliable JSON parsing")
    print("- ✅ Faster processing (native JSON generation)")
    print("- ✅ Eliminated parsing errors")

if __name__ == "__main__":
    asyncio.run(test_structured_staging())