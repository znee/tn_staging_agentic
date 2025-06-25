#!/usr/bin/env python3
"""Direct vector store rebuilder for AJCC guidelines."""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF for PDF processing
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
# Use updated langchain-ollama package
try:
    from langchain_ollama import OllamaEmbeddings
except ImportError:
    from langchain_community.embeddings import OllamaEmbeddings

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF with table preservation."""
    print(f"📄 Processing: {pdf_path}")
    
    doc = fitz.open(pdf_path)
    full_text = ""
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # Extract tables first
        try:
            tables = page.find_tables()
            table_text = ""
            
            if tables:
                table_list = list(tables)
                print(f"  Found {len(table_list)} tables on page {page_num + 1}")
                for table_num, table in enumerate(table_list):
                    try:
                        table_data = table.extract()
                        if table_data and len(table_data) > 1:  # Skip empty or single-row tables
                            table_text += f"\n\n[MEDICAL TABLE {table_num + 1}]\n"
                            for row in table_data:
                                if row:  # Skip empty rows
                                    clean_row = [str(cell).strip() if cell else "" for cell in row]
                                    if any(clean_row):  # Only add rows with content
                                        table_text += " | ".join(clean_row) + "\n"
                            table_text += "[END TABLE]\n"
                    except Exception as e:
                        print(f"    Table extraction error: {e}")
        except Exception as e:
            print(f"  Table finding error: {e}")
            table_text = ""
        
        # Extract regular text
        page_text = page.get_text()
        
        # Combine with preference for table content
        if table_text:
            full_text += f"\n\n=== PAGE {page_num + 1} ===\n{table_text}\n{page_text}\n"
        else:
            full_text += f"\n\n=== PAGE {page_num + 1} ===\n{page_text}\n"
    
    doc.close()
    
    print(f"  ✅ Extracted {len(full_text)} characters")
    return full_text

def build_vector_store():
    """Build FAISS vector store from PDF guidelines."""
    print("🔧 Building Vector Store for AJCC Guidelines")
    print("=" * 50)
    
    # Setup paths
    pdf_dir = Path("guidelines/pdfs")
    output_dir = Path("faiss_stores/ajcc_guidelines_local")
    
    if not pdf_dir.exists():
        print(f"❌ PDF directory not found: {pdf_dir}")
        return False
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize embeddings with Ollama (matching the original system)
    print("🔄 Initializing Ollama embeddings...")
    embeddings = OllamaEmbeddings(
        model="nomic-embed-text:latest",
        base_url="http://localhost:11434"
    )
    
    # Process PDFs
    all_docs = []
    processed_files = []
    
    for pdf_file in pdf_dir.glob("*.pdf"):
        print(f"\n📖 Processing: {pdf_file.name}")
        
        try:
            # Extract text
            text = extract_text_from_pdf(str(pdf_file))
            
            if len(text.strip()) < 100:
                print(f"  ⚠️  Warning: Very short text extracted ({len(text)} chars)")
                continue
            
            # Split into chunks
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", ". ", ".", " ", ""]
            )
            
            chunks = splitter.split_text(text)
            print(f"  ✂️  Split into {len(chunks)} chunks")
            
            # Add metadata
            for i, chunk in enumerate(chunks):
                doc_metadata = {
                    "source": pdf_file.name,
                    "chunk_id": i,
                    "page_content": chunk
                }
                all_docs.append(doc_metadata)
            
            processed_files.append(pdf_file.name)
            print(f"  ✅ Successfully processed {pdf_file.name}")
            
        except Exception as e:
            print(f"  ❌ Error processing {pdf_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    if not all_docs:
        print("❌ No documents processed successfully")
        return False
    
    print(f"\n🔧 Building FAISS index with {len(all_docs)} document chunks...")
    
    # Prepare texts and metadata for FAISS
    texts = [doc["page_content"] for doc in all_docs]
    metadatas = [{"source": doc["source"], "chunk_id": doc["chunk_id"]} for doc in all_docs]
    
    try:
        # Create FAISS vector store
        vector_store = FAISS.from_texts(texts, embeddings, metadatas=metadatas)
        
        # Save vector store
        vector_store.save_local(str(output_dir))
        print(f"💾 Vector store saved to: {output_dir}")
        
        # Test the vector store
        print("\n🧪 Testing vector store...")
        test_results = vector_store.similarity_search("T staging tumor", k=3)
        print(f"  ✅ Test successful: Found {len(test_results)} results")
        
        if test_results:
            print(f"  📋 Sample result: {test_results[0].page_content[:100]}...")
        
        # Save processing summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "files_processed": processed_files,
            "total_documents": len(processed_files),
            "total_chunks": len(all_docs),
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "embedding_model": "nomic-embed-text:latest",
            "test_results": len(test_results),
            "errors": []
        }
        
        with open(output_dir / "processing_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"✅ Vector store build complete!")
        print(f"   📊 {len(processed_files)} PDFs processed")
        print(f"   📄 {len(all_docs)} total chunks")
        print(f"   🔍 Test query successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to build vector store: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = build_vector_store()
    sys.exit(0 if success else 1)