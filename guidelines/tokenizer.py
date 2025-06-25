"""Enhanced PDF tokenization system with table extraction for AJCC guidelines."""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
import streamlit as st

class EnhancedPDFTokenizer:
    """Enhanced PDF tokenizer with medical table extraction."""
    
    def __init__(
        self,
        embeddings_provider,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        output_dir: str = "faiss_stores"
    ):
        """Initialize the tokenizer.
        
        Args:
            embeddings_provider: Embeddings provider (OpenAI or local)
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            output_dir: Output directory for vector stores
        """
        self.embeddings_provider = embeddings_provider
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger("pdf_tokenizer")
        self._setup_logging()
        
        # Text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Medical patterns for table detection
        self.medical_table_patterns = [
            r"T\d+[a-z]?\s*[-–]\s*",  # T staging patterns
            r"N\d+[a-z]?\s*[-–]\s*",  # N staging patterns
            r"Stage\s+[IVX]+[ABC]?\s*[-–]\s*",  # Stage grouping
            r"Tumor\s+size\s*[:\s]",  # Tumor size criteria
            r"Regional\s+lymph\s+node[s]?\s*[:\s]",  # LN criteria
            r"TNM\s+Classification\s*[:\s]",  # TNM classification
            r"AJCC\s+Stage\s*[:\s]",  # AJCC staging
        ]
        
        # Table structure indicators
        self.table_indicators = [
            "┌", "└", "├", "┤", "┬", "┴", "┼",  # Box drawing
            "╔", "╚", "╠", "╣", "╦", "╩", "╬",  # Double box drawing
            "━", "┃", "─", "│", "┏", "┓", "┗", "┛",  # Additional box chars
            "\t", "   ", "      "  # Tab and multiple spaces
        ]
    
    def _setup_logging(self):
        """Set up logging for tokenizer."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] [PDFTokenizer] %(levelname)s: %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def process_pdf_directory(
        self,
        pdf_directory: str,
        store_name: str = "ajcc_guidelines"
    ) -> Tuple[FAISS, Dict[str, Any]]:
        """Process all PDFs in a directory and create vector store.
        
        Args:
            pdf_directory: Directory containing PDF files
            store_name: Name for the vector store
            
        Returns:
            Tuple of (vector_store, processing_summary)
        """
        pdf_dir = Path(pdf_directory)
        if not pdf_dir.exists():
            raise FileNotFoundError(f"PDF directory not found: {pdf_directory}")
        
        pdf_files = list(pdf_dir.glob("*.pdf"))
        if not pdf_files:
            raise ValueError(f"No PDF files found in {pdf_directory}")
        
        self.logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        all_documents = []
        processing_summary = {
            "files_processed": 0,
            "total_chunks": 0,
            "tables_extracted": 0,
            "processing_errors": [],
            "file_summaries": {},
            "start_time": datetime.now().isoformat()
        }
        
        # Process each PDF file
        for pdf_file in pdf_files:
            try:
                self.logger.info(f"Processing: {pdf_file.name}")
                
                documents, file_summary = self.extract_from_pdf(str(pdf_file))
                all_documents.extend(documents)
                
                processing_summary["files_processed"] += 1
                processing_summary["total_chunks"] += len(documents)
                processing_summary["tables_extracted"] += file_summary.get("tables_found", 0)
                processing_summary["file_summaries"][pdf_file.name] = file_summary
                
                # Progress update for Streamlit
                if hasattr(st, 'session_state'):
                    progress = processing_summary["files_processed"] / len(pdf_files)
                    st.progress(
                        progress,
                        text=f"Processed {pdf_file.name} ({processing_summary['files_processed']}/{len(pdf_files)})"
                    )
                
            except Exception as e:
                error_msg = f"Error processing {pdf_file.name}: {str(e)}"
                self.logger.error(error_msg)
                processing_summary["processing_errors"].append(error_msg)
        
        if not all_documents:
            raise ValueError("No documents were successfully processed")
        
        # Create vector store
        self.logger.info(f"Creating vector store with {len(all_documents)} documents")
        vector_store = FAISS.from_documents(all_documents, self.embeddings_provider)
        
        # Save vector store
        store_path = self.output_dir / store_name
        vector_store.save_local(str(store_path))
        
        # Save processing summary
        processing_summary["end_time"] = datetime.now().isoformat()
        processing_summary["vector_store_path"] = str(store_path)
        
        summary_path = store_path / "processing_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(processing_summary, f, indent=2)
        
        self.logger.info(f"Vector store saved to: {store_path}")
        self.logger.info(f"Processing complete: {processing_summary['total_chunks']} chunks, {processing_summary['tables_extracted']} tables")
        
        return vector_store, processing_summary
    
    def extract_from_pdf(self, pdf_path: str) -> Tuple[List[Document], Dict[str, Any]]:
        """Extract text and tables from a single PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (documents, file_summary)
        """
        pdf_document = fitz.open(pdf_path)
        all_text = []
        tables_found = 0
        file_summary = {
            "filename": Path(pdf_path).name,
            "pages": len(pdf_document),
            "tables_found": 0,
            "chunks_created": 0,
            "processing_method": "enhanced_extraction"
        }
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Extract text
            page_text = page.get_text()
            
            # Detect and enhance tables
            enhanced_text, page_tables = self._detect_and_enhance_tables(
                page_text, page_num + 1
            )
            
            all_text.append(enhanced_text)
            tables_found += page_tables
        
        pdf_document.close()
        
        # Combine all text
        full_text = "\n\n".join(all_text)
        
        # Create chunks
        chunks = self.text_splitter.split_text(full_text)
        
        # Create documents with metadata
        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    "source": Path(pdf_path).name,
                    "chunk_id": i,
                    "total_chunks": len(chunks),
                    "has_table": "[MEDICAL TABLE]" in chunk,
                    "extraction_method": "enhanced"
                }
            )
            documents.append(doc)
        
        file_summary["tables_found"] = tables_found
        file_summary["chunks_created"] = len(documents)
        
        return documents, file_summary
    
    def _detect_and_enhance_tables(
        self,
        page_text: str,
        page_number: int
    ) -> Tuple[str, int]:
        """Detect and enhance medical tables on a page.
        
        Args:
            page_text: Text content of the page
            page_number: Page number
            
        Returns:
            Tuple of (enhanced_text, tables_found)
        """
        tables_found = 0
        
        # Check for medical table patterns
        has_medical_content = any(
            re.search(pattern, page_text, re.IGNORECASE)
            for pattern in self.medical_table_patterns
        )
        
        # Check for table structure indicators
        has_table_structure = any(
            indicator in page_text
            for indicator in self.table_indicators
        )
        
        if has_medical_content or has_table_structure:
            # This looks like a medical table
            enhanced_text = f"[MEDICAL TABLE - Page {page_number}]\n\n{page_text}\n\n[/MEDICAL TABLE]"
            tables_found = 1
            
            # Additional processing for TNM staging tables
            if re.search(r"T\d+.*N\d+.*M\d+", page_text, re.IGNORECASE):
                enhanced_text = f"[TNM STAGING TABLE - Page {page_number}]\n\n{page_text}\n\n[/TNM STAGING TABLE]"
            
        else:
            enhanced_text = page_text
        
        return enhanced_text, tables_found
    
    def create_streamlit_interface(self, backend: str = "openai"):
        """Create Streamlit interface for PDF processing.
        
        Args:
            backend: Backend to use ("openai" or "ollama")
        """
        st.title("AJCC Guidelines Tokenizer")
        st.write(f"Enhanced PDF processing with table extraction - {backend.upper()} Backend")
        
        # File upload
        uploaded_files = st.file_uploader(
            "Upload AJCC Guideline PDFs",
            type="pdf",
            accept_multiple_files=True
        )
        
        # Configuration
        col1, col2 = st.columns(2)
        with col1:
            chunk_size = st.slider("Chunk Size", 500, 2000, 1000)
            chunk_overlap = st.slider("Chunk Overlap", 50, 200, 100)
        
        with col2:
            store_name = st.text_input(
                "Vector Store Name",
                f"ajcc_guidelines_{backend}"
            )
        
        if uploaded_files and st.button("Process PDFs"):
            # Save uploaded files temporarily
            temp_dir = Path("temp_pdfs")
            temp_dir.mkdir(exist_ok=True)
            
            try:
                # Save files
                for uploaded_file in uploaded_files:
                    with open(temp_dir / uploaded_file.name, "wb") as f:
                        f.write(uploaded_file.getvalue())
                
                # Initialize tokenizer with updated settings
                self.chunk_size = chunk_size
                self.chunk_overlap = chunk_overlap
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    length_function=len,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
                
                # Process PDFs
                with st.spinner("Processing PDFs..."):
                    vector_store, summary = self.process_pdf_directory(
                        str(temp_dir),
                        store_name
                    )
                
                # Display results
                st.success("Processing complete!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Files Processed", summary["files_processed"])
                with col2:
                    st.metric("Total Chunks", summary["total_chunks"])
                with col3:
                    st.metric("Tables Extracted", summary["tables_extracted"])
                
                # Detailed summary
                with st.expander("Processing Details"):
                    st.json(summary)
                
                # Sample chunks
                if st.checkbox("Show Sample Chunks"):
                    sample_docs = vector_store.similarity_search("T staging criteria", k=3)
                    for i, doc in enumerate(sample_docs):
                        st.write(f"**Sample Chunk {i+1}:**")
                        st.write(doc.page_content[:500] + "...")
                        st.write(f"*Metadata:* {doc.metadata}")
                        st.write("---")
                
            except Exception as e:
                st.error(f"Error processing PDFs: {str(e)}")
            
            finally:
                # Cleanup temporary files
                import shutil
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)