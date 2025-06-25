#!/usr/bin/env python3
"""Quick test of improved staging system."""

import asyncio
from contexts.context_manager import ContextManager, WorkflowOrchestrator
from config.llm_providers import OllamaProvider

async def test_staging():
    """Test the improved staging system with a sample report."""
    
    # Test with sample report
    report = """CT CHEST WITH CONTRAST:
There is a 2.1 x 1.8 cm spiculated mass in the right upper lobe. 
The mass does not invade the pleural surface or chest wall.
No enlarged lymph nodes identified.
IMPRESSION: Right upper lobe lung mass, no nodal involvement."""
    
    print("Testing improved staging with sample report...")
    print("=" * 60)
    
    try:
        # Initialize provider and orchestrator
        provider = OllamaProvider()
        orchestrator = WorkflowOrchestrator(provider)
        
        # Create context
        context = ContextManager()
        context.update_context({"context_R": report})
        
        # Test detection step
        print("1. Testing detection...")
        result = await orchestrator.detect_body_part_and_cancer(context)
        print(f"   Detection result: {result.data}")
        print(f"   Status: {result.status.value}")
        
        if result.status.value == "success":
            context.update_context(result.data)
            
            # Get guidelines (will fallback to LLM if no vector store)
            print("\n2. Testing guideline retrieval...")
            guideline_result = await orchestrator.retrieve_guidelines(context)
            print(f"   Guidelines status: {guideline_result.status.value}")
            
            if guideline_result.status.value in ["success", "fallback"]:
                context.update_context(guideline_result.data)
                
                # Test T and N staging with improved prompts
                print("\n3. Testing T staging...")
                t_result = await orchestrator.stage_tumor(context)
                
                print("\n4. Testing N staging...")
                n_result = await orchestrator.stage_nodes(context)
                
                # Display results
                print("\n" + "=" * 60)
                print("STAGING RESULTS:")
                print("=" * 60)
                
                t_stage = t_result.data.get("context_T", "unknown")
                n_stage = n_result.data.get("context_N", "unknown")
                t_conf = t_result.data.get("context_CT", 0)
                n_conf = n_result.data.get("context_CN", 0)
                
                print(f"T staging: {t_stage} (confidence: {t_conf:.2f})")
                print(f"N staging: {n_stage} (confidence: {n_conf:.2f})")
                print(f"Combined: {t_stage}{n_stage}")
                print(f"\nT rationale: {t_result.data.get('context_RationaleT', 'none')}")
                print(f"N rationale: {n_result.data.get('context_RationaleN', 'none')}")
                
                # Check if we fixed the TXNX issue
                if t_stage != "TX" and n_stage != "NX":
                    print("\n✅ SUCCESS: Proper staging achieved (not TXNX)")
                    print("Expected for this report: T1bN0 or similar")
                else:
                    print("\n⚠️  PARTIAL: Still getting TX/NX results")
                    print("This indicates JSON parsing or reasoning issues")
                    
                    if t_stage == "TX":
                        print("- T staging failed: Check tumor size extraction and prompts")
                    if n_stage == "NX":
                        print("- N staging failed: Check lymph node parsing and prompts")
                        
            else:
                print("❌ Guidelines retrieval failed")
        else:
            print("❌ Detection failed")
    
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_staging())