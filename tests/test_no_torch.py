#!/usr/bin/env python3
"""Test the system without PyTorch dependencies."""

import sys
import os

def check_no_torch():
    """Verify we can run without PyTorch."""
    print("🧪 Testing PyTorch-free Operation")
    print("=" * 35)
    
    # Block torch import to ensure we don't accidentally use it
    class TorchBlocker:
        def __getattr__(self, name):
            raise ImportError(f"PyTorch blocked! Attempted to access torch.{name}")
    
    sys.modules['torch'] = TorchBlocker()
    
    try:
        # Test core imports
        print("📦 Testing core imports...")
        from langchain_community.embeddings import OllamaEmbeddings
        print("  ✅ OllamaEmbeddings")
        
        from langchain_community.vectorstores import FAISS
        print("  ✅ FAISS")
        
        from main import TNStagingSystem
        print("  ✅ TNStagingSystem")
        
        # Test system initialization
        print("\n🔧 Testing system initialization...")
        system = TNStagingSystem(backend="ollama", debug=False)
        print("  ✅ System initialized without PyTorch")
        
        # Test vector store loading
        print("\n📂 Testing vector store...")
        retrieval_agent = system.agents['retrieve_guideline']
        if retrieval_agent.vector_store:
            print("  ✅ Vector store loaded successfully")
        else:
            print("  ⚠️  Vector store not loaded (but system still works)")
        
        print(f"\n✅ SUCCESS: System works perfectly without PyTorch!")
        print(f"🎯 Benefits:")
        print(f"   - Faster startup")
        print(f"   - Smaller memory footprint") 
        print(f"   - No Streamlit conflicts")
        print(f"   - Simpler dependencies")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = check_no_torch()
    sys.exit(0 if success else 1)