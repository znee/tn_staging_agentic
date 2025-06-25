#!/usr/bin/env python3
"""Quick test of the analysis workflow."""

import asyncio
import sys
from main import TNStagingSystem

async def test_analysis():
    """Test the complete analysis workflow."""
    print("🧪 Testing TN Staging Analysis Workflow")
    print("=" * 45)
    
    # Sample report for oral cavity cancer
    test_report = """
    CT scan of the head and neck reveals a 2.3 cm mass in the right oral cavity, 
    involving the lateral tongue. The tumor appears to extend into the floor of mouth 
    but does not involve the mandible. Multiple enlarged lymph nodes are seen in the 
    right cervical chain, with the largest measuring 1.8 cm in the level II region.
    No distant metastases are identified.
    """
    
    try:
        # Initialize system
        print("🔄 Initializing system...")
        system = TNStagingSystem(backend="ollama", debug=True)
        print("✅ System initialized")
        
        # Run analysis
        print(f"\n📋 Analyzing report...")
        print(f"Report: {test_report[:100]}...")
        
        result = await system.analyze_report(test_report)
        
        print(f"\n📊 Analysis Results:")
        print(f"Status: {result.get('status', 'unknown')}")
        
        if result.get('success'):
            print(f"✅ Analysis completed successfully!")
            print(f"T Stage: {result.get('t_stage', 'unknown')}")
            print(f"N Stage: {result.get('n_stage', 'unknown')}")
            print(f"Confidence T: {result.get('t_confidence', 'unknown')}")
            print(f"Confidence N: {result.get('n_confidence', 'unknown')}")
            return True
        else:
            print(f"❌ Analysis failed: {result.get('error', 'unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_analysis())
    sys.exit(0 if success else 1)