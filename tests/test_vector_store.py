#!/usr/bin/env python3
"""Test script to verify vector store functionality."""

import sys
from pathlib import Path

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

from langchain_community.vectorstores import FAISS

def test_vector_store():
    """Test the rebuilt vector store."""
    print("🔍 Testing Vector Store Functionality")
    print("=" * 40)
    
    store_path = "faiss_stores/ajcc_guidelines_local"
    
    if not Path(store_path).exists():
        print(f"❌ Vector store not found at: {store_path}")
        return False
    
    try:
        # Initialize embeddings
        print("🔄 Loading embeddings...")
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Load vector store
        print("📂 Loading vector store...")
        vector_store = FAISS.load_local(
            store_path,
            embeddings,
            allow_dangerous_deserialization=True
        )
        
        # Check document count
        if hasattr(vector_store, 'index') and hasattr(vector_store.index, 'ntotal'):
            doc_count = vector_store.index.ntotal
            print(f"📊 Vector store contains {doc_count} documents")
        
        # Test searches that would be used in the app
        test_queries = [
            "T staging criteria for oral cavity cancer",
            "N staging lymph node oral cavity",
            "tumor size T1 T2 oral cavity",
            "lymph node metastasis N1 N2"
        ]
        
        print("\n🧪 Testing search queries...")
        for query in test_queries:
            print(f"\n🔍 Query: {query}")
            try:
                results = vector_store.similarity_search(query, k=3)
                print(f"  ✅ Found {len(results)} results")
                
                if results:
                    preview = results[0].page_content[:100].replace('\n', ' ')
                    print(f"  📋 Preview: {preview}...")
                    
                    # Check for staging content
                    has_staging = any(marker in results[0].page_content.lower() 
                                    for marker in ['t1', 't2', 'n1', 'n2', 'staging'])
                    if has_staging:
                        print(f"  ✅ Contains staging information")
                    else:
                        print(f"  ⚠️  No staging markers found")
                else:
                    print(f"  ⚠️  No results returned")
                    
            except Exception as e:
                print(f"  ❌ Search failed: {e}")
                return False
        
        print(f"\n✅ All vector store tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Vector store test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_vector_store()
    sys.exit(0 if success else 1)