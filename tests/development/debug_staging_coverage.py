#!/usr/bin/env python3
"""Debug staging coverage analysis."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import TNStagingSystem

async def debug_staging_coverage():
    """Debug why staging coverage analysis isn't working."""
    
    print("=== Debugging Staging Coverage Analysis ===")
    
    # Initialize system like the real workflow does
    system = TNStagingSystem(backend="ollama", debug=True)
    
    # Get the guideline retrieval agent
    retrieval_agent = system.agents["retrieve_guideline"]
    
    print(f"Retrieval agent type: {type(retrieval_agent)}")
    print(f"Has coverage method: {hasattr(retrieval_agent, '_analyze_staging_coverage_llm')}")
    
    # Test sample guidelines
    test_guidelines = """
    T STAGING FOR ORAL CAVITY CANCER
    T0: No evidence of primary tumor
    T1: Tumor ≤2 cm in greatest dimension
    T2: Tumor >2 cm but ≤4 cm in greatest dimension  
    T3: Tumor >4 cm in greatest dimension
    T4a: Moderately advanced local disease
    T4b: Very advanced local disease
    """
    
    try:
        print("\n--- Testing T Staging Coverage Analysis ---")
        t_coverage = await retrieval_agent._analyze_staging_coverage_llm(
            test_guidelines, "T", "oral cavity", "squamous cell carcinoma"
        )
        print(f"T Coverage Result: '{t_coverage}'")
        
        # Check if it looks like a stage list or error
        if "," in t_coverage and any(stage in t_coverage for stage in ["t0", "t1", "t2"]):
            print("✅ Coverage analysis working correctly!")
        else:
            print("⚠️ Coverage analysis not returning expected format")
            
    except Exception as e:
        print(f"❌ Coverage analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_staging_coverage())