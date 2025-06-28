#!/usr/bin/env python3
"""Test if the real system actually uses structured outputs."""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tn_staging_api import TNStagingAPI

async def test_real_structured():
    """Test the real system with a simple report."""
    
    print("=== Testing Real System for Structured Outputs ===")
    
    # Simple test report
    test_report = """
    CT scan shows a 2.5 cm mass in the left oral cavity. 
    No lymph node enlargement noted.
    No distant metastases.
    """
    
    # Create API (same as GUI uses)
    api = TNStagingAPI(backend="ollama", debug=True)
    
    # Check provider type
    system = api.system
    provider = system.llm_provider
    
    print(f"Provider type: {type(provider).__name__}")
    print(f"Has generate_structured: {hasattr(provider, 'generate_structured')}")
    
    if hasattr(provider, 'generate_structured'):
        print("✅ System is using structured provider!")
        
        # Check if T staging agent will use structured output
        t_agent = system.agents["staging_t"]
        print(f"T agent has structured method: {hasattr(t_agent, '_determine_t_stage_structured')}")
        
        # Try to check if the staging agent will actually use structured output
        # by inspecting the provider it received
        print(f"T agent provider type: {type(t_agent.llm_provider).__name__}")
        print(f"T agent provider has generate_structured: {hasattr(t_agent.llm_provider, 'generate_structured')}")
        
    else:
        print("❌ System is still using regular provider")
        
    print(f"\n🧪 Running actual analysis to test structured outputs...")
    
    try:
        # This should use structured outputs if they're properly integrated
        result = await api.analyze_report(test_report)
        
        print(f"✅ Analysis completed successfully!")
        print(f"   T stage: {result.get('context_T', 'N/A')}")
        print(f"   N stage: {result.get('context_N', 'N/A')}")
        
        # Check the metadata for unit formatting (structured output indicator)
        metadata = result.get('metadata', {})
        tumor_info = metadata.get('tumor_info', {})
        if tumor_info:
            largest_dim = tumor_info.get('largest_dimension', 'N/A')
            print(f"   Largest dimension: {largest_dim}")
            
            if isinstance(largest_dim, str) and ('cm' in largest_dim or 'mm' in largest_dim):
                print("   ✅ STRUCTURED OUTPUTS WORKING: Proper unit formatting detected!")
            elif isinstance(largest_dim, (int, float)):
                print("   ❌ MANUAL PARSING: Numeric value suggests old JSON parsing")
            else:
                print(f"   ❓ UNCLEAR: Dimension format: {type(largest_dim)} = {largest_dim}")
                
    except Exception as e:
        print(f"❌ Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_structured())