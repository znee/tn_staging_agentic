"""Guideline retrieval agent for fetching relevant TN staging guidelines."""

from typing import Dict, List, Tuple, Optional
import os
from pathlib import Path
from .base import BaseAgent, AgentContext, AgentMessage, AgentStatus
from config.llm_providers_structured import CaseCharacteristicsResponse

class GuidelineRetrievalAgent(BaseAgent):
    """Agent that retrieves relevant staging guidelines from vector store with body part routing."""
    
    def __init__(self, llm_provider, vector_store_path: str = None):
        """Initialize guideline retrieval agent.
        
        Args:
            llm_provider: LLM provider instance
            vector_store_path: Path to vector store
        """
        super().__init__("guideline_retrieval_agent", llm_provider)
        self.vector_store_path = vector_store_path or "faiss_stores/ajcc_guidelines"
        self.vector_store = None
        self.body_part_store_mapping = self._initialize_body_part_mapping()
        self.current_store_info = None  # Track which store is being used
        self._load_vector_store()
    
    def _initialize_body_part_mapping(self) -> Dict[str, str]:
        """Initialize mapping of body parts to specialized vector stores.
        
        Returns:
            Dictionary mapping body part names to store paths
        """
        # Current mapping based on available PDFs
        # When new PDFs are added, extend this mapping
        mapping = {
            # Oral cavity and oropharyngeal cancers (current PDF)
            "oral cavity": "oral_oropharyngeal",
            "oropharynx": "oral_oropharyngeal", 
            "oropharyngeal": "oral_oropharyngeal",
            "mouth": "oral_oropharyngeal",
            "tongue": "oral_oropharyngeal",
            "floor of mouth": "oral_oropharyngeal",
            "hard palate": "oral_oropharyngeal",
            "soft palate": "oral_oropharyngeal",
            "tonsil": "oral_oropharyngeal",
            "base of tongue": "oral_oropharyngeal",
            
            # Future body parts - will use general store until specific PDFs added
            # "lung": "lung",
            # "breast": "breast", 
            # "liver": "liver",
            # "pancreas": "pancreas",
            # etc.
        }
        
        self.logger.debug(f"Initialized body part mapping with {len(mapping)} entries")
        return mapping
    
    def _determine_store_path(self, body_part: str, cancer_type: str) -> Tuple[str, Dict[str, str]]:
        """Determine which vector store to use based on body part and cancer type.
        
        Args:
            body_part: Detected body part
            cancer_type: Detected cancer type
            
        Returns:
            Tuple of (store_path, store_info) where store_info contains routing metadata
        """
        store_info = {
            "body_part": body_part,
            "cancer_type": cancer_type,
            "routing_strategy": "general",  # Default
            "store_type": "general",
            "specialized_available": False
        }
        
        # Check if we have a specialized store for this body part
        body_part_lower = body_part.lower() if body_part else ""
        specialized_store = None
        
        for mapped_part, store_name in self.body_part_store_mapping.items():
            if mapped_part in body_part_lower:
                specialized_store = store_name
                break
        
        if specialized_store:
            # For oral/oropharyngeal, use the dedicated high-quality store
            if specialized_store == "oral_oropharyngeal":
                provider_type = getattr(self.llm_provider, 'provider_type', 'ollama')
                if provider_type == 'openai' or hasattr(self.llm_provider, 'openai_client'):
                    specialized_path = f"faiss_stores/oral_oropharyngeal_openai"
                else:
                    specialized_path = f"faiss_stores/oral_oropharyngeal_local"
                
                # Check if the high-quality specialized store exists
                if Path(specialized_path).exists():
                    store_info.update({
                        "routing_strategy": "specialized",
                        "store_type": "specialized", 
                        "specialized_available": True,
                        "specialized_store": specialized_store,
                        "routing_note": "Using dedicated high-quality oral/oropharyngeal store"
                    })
                    self.logger.info(f"🎯 Using specialized store for {body_part}: {specialized_path}")
                    return specialized_path, store_info
                else:
                    # Fallback to main store if specialized store not found
                    provider_type = getattr(self.llm_provider, 'provider_type', 'ollama')
                    if provider_type == 'openai' or hasattr(self.llm_provider, 'openai_client'):
                        fallback_path = self.vector_store_path + "_openai"
                    else:
                        fallback_path = self.vector_store_path + "_local"
                    
                    store_info.update({
                        "routing_strategy": "fallback_to_main",
                        "store_type": "fallback", 
                        "specialized_available": False,
                        "specialized_store": specialized_store,
                        "routing_note": "Specialized store not found, using main store as fallback"
                    })
                    self.logger.warning(f"⚠️  Specialized store not found: {specialized_path}, falling back to main store")
                    return fallback_path, store_info
            
            # For future body parts, check if dedicated store exists
            else:
                specialized_path = f"faiss_stores/{specialized_store}"
                provider_type = getattr(self.llm_provider, 'provider_type', 'ollama')
                
                if provider_type == 'openai' or hasattr(self.llm_provider, 'openai_client'):
                    specialized_path += "_openai"
                else:
                    specialized_path += "_local"
                
                if Path(specialized_path).exists():
                    store_info.update({
                        "routing_strategy": "specialized",
                        "store_type": "specialized", 
                        "specialized_available": True,
                        "specialized_store": specialized_store
                    })
                    self.logger.info(f"🎯 Using specialized store for {body_part}: {specialized_path}")
                    return specialized_path, store_info
                else:
                    self.logger.warning(f"⚠️  Specialized store not found: {specialized_path}, falling back to general")
                    store_info.update({
                        "specialized_available": False,
                        "routing_note": f"Specialized store for {specialized_store} not yet built"
                    })
        
        # Fall back to general store
        provider_type = getattr(self.llm_provider, 'provider_type', 'ollama')
        if provider_type == 'openai' or hasattr(self.llm_provider, 'openai_client'):
            general_path = self.vector_store_path + "_openai"
        else:
            general_path = self.vector_store_path + "_local"
        
        self.logger.info(f"📚 Using general store for {body_part}: {general_path}")
        return general_path, store_info
    
    def _load_specific_vector_store(self, store_path: str, store_info: Dict[str, str]):
        """Load a specific vector store based on routing decision.
        
        Args:
            store_path: Path to the vector store to load
            store_info: Store routing metadata
        """
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_openai import OpenAIEmbeddings
            
            try:
                from langchain_ollama import OllamaEmbeddings
            except ImportError:
                from langchain_community.embeddings import OllamaEmbeddings
            
            # Determine embedding provider
            provider_type = getattr(self.llm_provider, 'provider_type', 'ollama')
            
            if provider_type == 'openai' or hasattr(self.llm_provider, 'openai_client'):
                embeddings = OpenAIEmbeddings()
            else:
                embeddings = OllamaEmbeddings(
                    model="nomic-embed-text:latest",
                    base_url="http://localhost:11434"
                )
            
            self.logger.info(f"📂 LOADING VECTOR STORE: {store_path}")
            
            if Path(store_path).exists():
                self.vector_store = FAISS.load_local(
                    store_path, 
                    embeddings, 
                    allow_dangerous_deserialization=True
                )
                self.current_store_info = store_info
                
                # Test the loaded store
                test_docs = self.vector_store.similarity_search("test query", k=1)
                
                # Enhanced logging for store type visibility
                if store_info['store_type'] == 'specialized':
                    self.logger.info(f"🎯 ✅ SPECIALIZED STORE LOADED: {store_info.get('specialized_store', 'unknown')}")
                    self.logger.info(f"   Body Part: {store_info.get('body_part', 'unknown')}")
                    self.logger.info(f"   Test Results: {len(test_docs)} documents found")
                    self.logger.info(f"   Store Quality: High-quality cancer-specific")
                else:
                    self.logger.info(f"📚 ✅ GENERAL STORE LOADED (fallback)")
                    self.logger.info(f"   Body Part: {store_info.get('body_part', 'unknown')}")
                    self.logger.info(f"   Test Results: {len(test_docs)} documents found")
                    self.logger.info(f"   Store Quality: General purpose")
                
                # Store summary info
                if hasattr(self.vector_store, 'index') and hasattr(self.vector_store.index, 'ntotal'):
                    doc_count = self.vector_store.index.ntotal
                    self.logger.info(f"📊 Vector store contains {doc_count} total documents")
                    
            else:
                self.logger.error(f"Vector store not found: {store_path}")
                self.vector_store = None
                self.current_store_info = None
                
        except Exception as e:
            self.logger.error(f"Failed to load vector store {store_path}: {str(e)}")
            self.vector_store = None
            self.current_store_info = None
    
    def _load_vector_store(self):
        """Load vector store for guideline retrieval."""
        try:
            # Import necessary libraries
            from langchain_community.vectorstores import FAISS
            from langchain_openai import OpenAIEmbeddings
            
            # Use updated langchain-ollama package
            try:
                from langchain_ollama import OllamaEmbeddings
                self.logger.debug("Using updated langchain-ollama package")
            except ImportError:
                from langchain_community.embeddings import OllamaEmbeddings
                self.logger.warning("Using legacy OllamaEmbeddings - consider upgrading to langchain-ollama")
            
            # Determine embedding provider based on LLM provider type
            provider_type = getattr(self.llm_provider, 'provider_type', 'ollama')
            
            if provider_type == 'openai' or hasattr(self.llm_provider, 'openai_client'):
                self.logger.info("Using OpenAI embeddings for guidelines (cloud-based)")
                embeddings = OpenAIEmbeddings()
                store_path = self.vector_store_path + "_openai"
                
            elif provider_type == 'hybrid':
                # For hybrid, use OpenAI embeddings (cloud) for better quality
                self.logger.info("Using OpenAI embeddings for hybrid setup (cloud component)")
                embeddings = OpenAIEmbeddings()
                store_path = self.vector_store_path + "_openai"
                
            else:  # Default to Ollama
                self.logger.info("Using Ollama embeddings for guidelines (local)")
                embeddings = OllamaEmbeddings(
                    model="nomic-embed-text:latest",
                    base_url="http://localhost:11434"
                )
                # Fix the path - don't add _local suffix if path already ends with _local
                if self.vector_store_path.endswith("_local"):
                    store_path = self.vector_store_path
                else:
                    store_path = self.vector_store_path + "_local"
            
            self.logger.debug(f"Attempting to load vector store from: {store_path}")
            
            if Path(store_path).exists():
                self.vector_store = FAISS.load_local(
                    store_path, 
                    embeddings, 
                    allow_dangerous_deserialization=True
                )
                self.logger.info(f"Loaded vector store from {store_path}")
                
                # Test the vector store with comprehensive diagnostics
                try:
                    # First check if vector store has documents
                    if hasattr(self.vector_store, 'index') and hasattr(self.vector_store.index, 'ntotal'):
                        doc_count = self.vector_store.index.ntotal
                        self.logger.debug(f"Vector store contains {doc_count} documents")
                        
                        if doc_count == 0:
                            self.logger.error("Vector store is empty - no documents indexed")
                            self.vector_store = None
                            return
                    
                    # Test with actual search
                    self.logger.debug("Testing vector store similarity search...")
                    test_docs = self.vector_store.similarity_search("test query", k=1)
                    self.logger.info(f"✅ Vector store test successful: found {len(test_docs)} documents")
                    
                    if len(test_docs) == 0:
                        self.logger.warning("Vector store test: No documents found but search successful")
                    else:
                        # Test with a medical query
                        med_docs = self.vector_store.similarity_search("T staging tumor", k=1)
                        self.logger.debug(f"Medical query test: found {len(med_docs)} documents")
                        
                except AssertionError as ae:
                    self.logger.error(f"❌ FAISS AssertionError during vector store test")
                    self.logger.error(f"This indicates a FAISS compatibility issue - disabling vector store")
                    self.logger.debug(f"AssertionError details: {str(ae)}")
                    import traceback
                    self.logger.debug(f"Full traceback: {traceback.format_exc()}")
                    self.vector_store = None
                    
                except Exception as test_e:
                    error_msg = str(test_e) if str(test_e).strip() else f"Unknown error ({type(test_e).__name__})"
                    self.logger.error(f"❌ Vector store test failed: {error_msg}")
                    self.logger.debug(f"Error type: {type(test_e).__name__}")
                    import traceback
                    self.logger.debug(f"Full traceback: {traceback.format_exc()}")
                    self.vector_store = None
                
                if self.vector_store is None:
                    self.logger.warning("⚠️  Vector store disabled - using LLM fallback only")
                else:
                    self.logger.info("✅ Vector store operational and ready")
                    
            else:
                self.logger.warning(f"Vector store not found at {store_path}")
                
        except Exception as e:
            error_msg = str(e) if str(e).strip() else "Unknown vector store loading error"
            self.logger.error(f"Failed to load vector store: {error_msg}")
            import traceback
            self.logger.debug(f"Vector store loading traceback: {traceback.format_exc()}")
            self.vector_store = None
            self.logger.info("Vector store unavailable - will use LLM fallback for guidelines")
    
    def validate_input(self, context: AgentContext) -> bool:
        """Validate that body part and cancer type are present.
        
        Args:
            context: Current agent context
            
        Returns:
            True if required inputs are present
        """
        return (
            context.context_B is not None and
            context.context_B.get("body_part") is not None and
            context.context_B.get("cancer_type") is not None
        )
    
    async def process(self, context: AgentContext) -> AgentMessage:
        """Retrieve relevant guidelines for T and N staging with store routing.
        
        Args:
            context: Current agent context
            
        Returns:
            AgentMessage with guideline retrieval results
        """
        body_part = context.context_B["body_part"]
        cancer_type = context.context_B["cancer_type"]
        case_report = context.context_R  # Get the original case report for semantic retrieval
        
        # Determine appropriate vector store based on body part/cancer type
        target_store_path, store_info = self._determine_store_path(body_part, cancer_type)
        
        # Enhanced logging for store selection visibility
        self.logger.info(f"🔍 VECTOR STORE SELECTION for {body_part} ({cancer_type}):")
        self.logger.info(f"   Strategy: {store_info['routing_strategy']}")
        self.logger.info(f"   Store Type: {store_info['store_type']}")
        self.logger.info(f"   Store Path: {target_store_path}")
        if store_info.get('specialized_store'):
            self.logger.info(f"   Specialized Store: {store_info['specialized_store']}")
        
        # Load the appropriate vector store if different from current
        if not self.vector_store or self.current_store_info != store_info:
            self.logger.info(f"🔄 Loading vector store (current store different or not loaded)")
            self._load_specific_vector_store(target_store_path, store_info)
        else:
            self.logger.info(f"♻️  Reusing already loaded vector store")
        
        # Retrieve guidelines using enhanced semantic approach
        t_guidelines = await self._retrieve_t_guidelines_semantic(body_part, cancer_type, case_report)
        n_guidelines = await self._retrieve_n_guidelines_semantic(body_part, cancer_type, case_report)
        
        if t_guidelines and n_guidelines:
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={
                    "context_GT": t_guidelines,
                    "context_GN": n_guidelines
                },
                metadata={
                    "retrieval_method": "vector_store" if self.vector_store else "fallback",
                    "body_part": body_part,
                    "cancer_type": cancer_type,
                    "store_routing": store_info,  # Pass routing info to session
                    "store_path": target_store_path,
                    "guideline_source": store_info.get("specialized_store", "general")
                }
            )
        else:
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.FAILED,
                data={},
                error=f"Could not retrieve guidelines for {cancer_type} of {body_part}",
                metadata={
                    "store_routing": store_info,
                    "store_path": target_store_path
                }
            )
    
    async def _retrieve_t_guidelines(self, body_part: str, cancer_type: str) -> Optional[str]:
        """Retrieve T staging guidelines.
        
        Args:
            body_part: Body part/organ
            cancer_type: Specific cancer type
            
        Returns:
            T staging guidelines text
        """
        if self.vector_store:
            query = f"T staging criteria for {cancer_type} of {body_part} TNM classification tumor size depth invasion"
            
            try:
                self.logger.debug(f"🔍 Searching vector store for T guidelines: {query[:100]}...")
                docs = self.vector_store.similarity_search(query, k=5)
                self.logger.info(f"📄 Found {len(docs)} documents for T staging")
                
                # Filter and combine relevant sections
                t_sections = []
                for doc in docs:
                    content = doc.page_content
                    # Look for T staging content
                    if any(marker in content.lower() for marker in ["t1", "t2", "t3", "t4", "t staging", "tumor"]):
                        t_sections.append(content)
                        self.logger.debug(f"✅ Added T section (length: {len(content)})")
                
                if t_sections:
                    # Check for medical tables
                    table_sections = [s for s in t_sections if "[MEDICAL TABLE]" in s]
                    if table_sections:
                        # Prioritize sections with tables
                        result = "\n\n".join(table_sections[:2])
                        self.logger.info(f"📊 Retrieved T guidelines with {len(table_sections)} table sections")
                        return result
                    else:
                        result = "\n\n".join(t_sections[:3])
                        self.logger.info(f"📝 Retrieved T guidelines with {len(t_sections)} text sections")
                        return result
                else:
                    self.logger.warning(f"⚠️  No relevant T staging sections found for {cancer_type} of {body_part}")
                        
            except AssertionError as ae:
                self.logger.error(f"❌ FAISS AssertionError during T guideline retrieval")
                self.logger.error(f"Disabling vector store due to compatibility issue")
                self.vector_store = None
                
            except Exception as e:
                error_msg = str(e) if str(e) else "Unknown error"
                self.logger.error(f"❌ Vector store T retrieval failed for '{query[:50]}...': {error_msg}")
                self.logger.debug(f"Error type: {type(e).__name__}")
                import traceback
                self.logger.debug(f"Full traceback: {traceback.format_exc()}")
                # Disable vector store if it keeps failing
                self.vector_store = None
        
        # Fallback to LLM knowledge
        return await self._llm_fallback_guidelines("T", body_part, cancer_type)
    
    async def _retrieve_n_guidelines(self, body_part: str, cancer_type: str) -> Optional[str]:
        """Retrieve N staging guidelines.
        
        Args:
            body_part: Body part/organ
            cancer_type: Specific cancer type
            
        Returns:
            N staging guidelines text
        """
        if self.vector_store:
            query = f"N staging criteria for {cancer_type} of {body_part} TNM lymph node regional metastasis"
            
            try:
                self.logger.debug(f"🔍 Searching vector store for N guidelines: {query[:100]}...")
                docs = self.vector_store.similarity_search(query, k=5)
                self.logger.info(f"📄 Found {len(docs)} documents for N staging")
                
                # Filter and combine relevant sections
                n_sections = []
                for doc in docs:
                    content = doc.page_content
                    # Look for N staging content
                    if any(marker in content.lower() for marker in ["n0", "n1", "n2", "n3", "n staging", "lymph", "node"]):
                        n_sections.append(content)
                        self.logger.debug(f"✅ Added N section (length: {len(content)})")
                
                if n_sections:
                    # Check for medical tables
                    table_sections = [s for s in n_sections if "[MEDICAL TABLE]" in s]
                    if table_sections:
                        # Prioritize sections with tables
                        result = "\n\n".join(table_sections[:2])
                        self.logger.info(f"📊 Retrieved N guidelines with {len(table_sections)} table sections")
                        return result
                    else:
                        result = "\n\n".join(n_sections[:3])
                        self.logger.info(f"📝 Retrieved N guidelines with {len(n_sections)} text sections")
                        return result
                else:
                    self.logger.warning(f"⚠️  No relevant N staging sections found for {cancer_type} of {body_part}")
                        
            except AssertionError as ae:
                self.logger.error(f"❌ FAISS AssertionError during N guideline retrieval")
                self.logger.error(f"Disabling vector store due to compatibility issue")
                self.vector_store = None
                
            except Exception as e:
                error_msg = str(e) if str(e) else "Unknown error"
                self.logger.error(f"❌ Vector store N retrieval failed for '{query[:50]}...': {error_msg}")
                self.logger.debug(f"Error type: {type(e).__name__}")
                import traceback
                self.logger.debug(f"Full traceback: {traceback.format_exc()}")
                # Disable vector store if it keeps failing
                self.vector_store = None
        
        # Fallback to LLM knowledge
        return await self._llm_fallback_guidelines("N", body_part, cancer_type)
    
    async def _llm_fallback_guidelines(self, stage_type: str, body_part: str, cancer_type: str) -> str:
        """Use LLM knowledge as fallback for guidelines.
        
        Args:
            stage_type: "T" or "N"
            body_part: Body part/organ
            cancer_type: Specific cancer type
            
        Returns:
            Guidelines from LLM
        """
        prompt = f"""Provide the AJCC {stage_type} staging criteria for {cancer_type} of {body_part}.

Format the response as a clear list of staging criteria, for example:
- {stage_type}0: [criteria]
- {stage_type}1: [criteria]
- {stage_type}2: [criteria]
- {stage_type}3: [criteria]
- {stage_type}4: [criteria if applicable]

Include specific size measurements, depth of invasion, or lymph node criteria as appropriate.
Be precise and use standard AJCC terminology."""

        try:
            response = await self.llm_provider.generate(prompt)
            return f"[LLM Fallback Guidelines]\n{response}"
        except Exception as e:
            self.logger.error(f"LLM fallback failed: {str(e)}")
            return f"[Error: Could not retrieve {stage_type} staging guidelines for {cancer_type}]"

    async def _extract_case_characteristics(self, case_report: str, body_part: str, cancer_type: str) -> str:
        """Extract case characteristics for semantic retrieval.
        
        Args:
            case_report: Original case report
            body_part: Body part
            cancer_type: Cancer type
            
        Returns:
            Case summary for semantic matching
        """
        # Try structured output first for better feature extraction
        if hasattr(self.llm_provider, 'generate_structured'):
            try:
                result = await self._extract_case_characteristics_structured(case_report, body_part, cancer_type)
                return result["case_summary"]
            except Exception as e:
                self.logger.warning(f"Structured case extraction failed, falling back to manual: {str(e)}")
        
        # Fallback to simple text generation
        return await self._extract_case_characteristics_manual(case_report, body_part, cancer_type)
    
    async def _extract_case_characteristics_structured(self, case_report: str, body_part: str, cancer_type: str) -> Dict[str, any]:
        """Extract case characteristics using structured output (preferred method)."""
        prompt = f"""Analyze this medical case report and extract key characteristics relevant for cancer staging.

CASE REPORT:
{case_report}

CONTEXT:
- Body part: {body_part}
- Cancer type: {cancer_type}

Extract and summarize the staging-relevant characteristics including tumor size, invasion patterns, lymph node involvement, and other relevant features."""

        result = await self.llm_provider.generate_structured(
            prompt,
            CaseCharacteristicsResponse,
            temperature=0.1
        )
        return result
    
    async def _extract_case_characteristics_manual(self, case_report: str, body_part: str, cancer_type: str) -> str:
        """Extract case characteristics using text generation (fallback method)."""
        prompt = f"""Analyze this medical case report and extract the key characteristics that would be relevant for cancer staging:

CASE REPORT:
{case_report}

CONTEXT:
- Body part: {body_part}
- Cancer type: {cancer_type}

Extract and summarize the key staging-relevant characteristics in a single sentence that includes:
- Tumor size/dimensions
- Invasion patterns/structures involved
- Lymph node involvement
- Any other staging-relevant features

Respond with ONLY the summary sentence, no explanations."""

        try:
            response = await self.llm_provider.generate(prompt)
            return response.strip()
        except Exception as e:
            self.logger.error(f"Failed to extract case characteristics: {str(e)}")
            # Fallback to basic description
            return f"{cancer_type} of {body_part} with clinical findings"

    async def _retrieve_t_guidelines_semantic(self, body_part: str, cancer_type: str, case_report: str) -> Optional[str]:
        """Retrieve T staging guidelines using enhanced semantic approach.
        
        Args:
            body_part: Body part/organ
            cancer_type: Specific cancer type
            case_report: Original case report
            
        Returns:
            T staging guidelines text
        """
        if not self.vector_store:
            return await self._llm_fallback_guidelines("T", body_part, cancer_type)
        
        # Log which store is being used for retrieval
        store_type = self.current_store_info.get('store_type', 'unknown') if self.current_store_info else 'unknown'
        specialized_store = self.current_store_info.get('specialized_store') if self.current_store_info else None
        
        if store_type == 'specialized' and specialized_store:
            self.logger.info(f"🔍 T-STAGING RETRIEVAL using SPECIALIZED store: {specialized_store}")
        else:
            self.logger.info(f"🔍 T-STAGING RETRIEVAL using GENERAL store (fallback)")
            
        try:
            # Extract case characteristics for semantic matching
            case_summary = await self._extract_case_characteristics(case_report, body_part, cancer_type)
            self.logger.debug(f"🧠 Case summary for T staging: {case_summary}")
            
            # Multiple semantic queries for comprehensive retrieval
            queries = [
                # Direct case description (most effective from testing)
                case_summary,
                
                # General staging guidelines
                f"T staging guidelines {body_part} {cancer_type}",
                f"tumor staging criteria {body_part} cancer",
                
                # Invasion-focused queries
                f"invasion patterns {body_part} cancer staging",
                f"deep invasion staging {cancer_type}",
                
                # Size-based queries (derived from case characteristics)
                f"tumor size staging {body_part} cancer",
                f"advanced T stage {body_part} {cancer_type}"
            ]
            
            # Collect results from all queries
            all_results = []
            unique_contents = set()
            
            for query in queries:
                self.logger.debug(f"🔍 T staging query: {query[:60]}...")
                try:
                    docs = self.vector_store.similarity_search(query, k=3)
                    for doc in docs:
                        content = doc.page_content
                        # Deduplicate based on content hash
                        content_hash = hash(content[:200])  # Use first 200 chars for dedup
                        if content_hash not in unique_contents:
                            unique_contents.add(content_hash)
                            all_results.append(content)
                except Exception as e:
                    self.logger.warning(f"Query failed: {query[:30]}... - {str(e)}")
                    continue
            
            self.logger.info(f"📄 Found {len(all_results)} unique documents for T staging")
            
            # Filter and prioritize results
            t_sections = self._filter_and_combine_results(all_results, "T")
            
            if t_sections:
                # Prioritize sections with medical tables
                table_sections = [s for s in t_sections if "[MEDICAL TABLE]" in s]
                if table_sections:
                    result = "\n\n".join(table_sections[:3])
                    self.logger.info(f"📊 Retrieved T guidelines with {len(table_sections)} table sections")
                else:
                    result = "\n\n".join(t_sections[:4])
                    self.logger.info(f"📝 Retrieved T guidelines with {len(t_sections)} text sections")
                
                # Analyze T staging coverage using LLM (guideline-based, not hardcoded)
                staging_coverage = await self._analyze_staging_coverage_llm(result, "T", body_part, cancer_type)
                self.logger.info(f"🎯 T staging coverage: {staging_coverage}")
                
                return result
            else:
                self.logger.warning(f"⚠️  No relevant T staging sections found for {cancer_type} of {body_part}")
                return await self._llm_fallback_guidelines("T", body_part, cancer_type)
                
        except Exception as e:
            self.logger.error(f"❌ Enhanced T retrieval failed: {str(e)}")
            return await self._llm_fallback_guidelines("T", body_part, cancer_type)

    async def _retrieve_n_guidelines_semantic(self, body_part: str, cancer_type: str, case_report: str) -> Optional[str]:
        """Retrieve N staging guidelines using enhanced semantic approach.
        
        Args:
            body_part: Body part/organ
            cancer_type: Specific cancer type
            case_report: Original case report
            
        Returns:
            N staging guidelines text
        """
        if not self.vector_store:
            return await self._llm_fallback_guidelines("N", body_part, cancer_type)
        
        # Log which store is being used for retrieval
        store_type = self.current_store_info.get('store_type', 'unknown') if self.current_store_info else 'unknown'
        specialized_store = self.current_store_info.get('specialized_store') if self.current_store_info else None
        
        if store_type == 'specialized' and specialized_store:
            self.logger.info(f"🔍 N-STAGING RETRIEVAL using SPECIALIZED store: {specialized_store}")
        else:
            self.logger.info(f"🔍 N-STAGING RETRIEVAL using GENERAL store (fallback)")
            
        try:
            # Extract case characteristics for semantic matching
            case_summary = await self._extract_case_characteristics(case_report, body_part, cancer_type)
            self.logger.debug(f"🧠 Case summary for N staging: {case_summary}")
            
            # Multiple semantic queries for comprehensive retrieval
            queries = [
                # Direct case description (most effective from testing)
                case_summary,
                
                # General staging guidelines
                f"N staging guidelines {body_part} {cancer_type}",
                f"lymph node staging criteria {body_part} cancer",
                
                # Node-focused queries
                f"lymph node involvement {cancer_type} staging",
                f"regional lymph nodes {body_part} staging",
                f"metastatic lymph nodes staging {cancer_type}",
                
                # Advanced staging
                f"advanced N stage {body_part} {cancer_type}",
                f"multiple lymph nodes staging criteria"
            ]
            
            # Collect results from all queries
            all_results = []
            unique_contents = set()
            
            for query in queries:
                self.logger.debug(f"🔍 N staging query: {query[:60]}...")
                try:
                    docs = self.vector_store.similarity_search(query, k=3)
                    for doc in docs:
                        content = doc.page_content
                        # Deduplicate based on content hash
                        content_hash = hash(content[:200])  # Use first 200 chars for dedup
                        if content_hash not in unique_contents:
                            unique_contents.add(content_hash)
                            all_results.append(content)
                except Exception as e:
                    self.logger.warning(f"Query failed: {query[:30]}... - {str(e)}")
                    continue
            
            self.logger.info(f"📄 Found {len(all_results)} unique documents for N staging")
            
            # Filter and prioritize results
            n_sections = self._filter_and_combine_results(all_results, "N")
            
            if n_sections:
                # Prioritize sections with medical tables
                table_sections = [s for s in n_sections if "[MEDICAL TABLE]" in s]
                if table_sections:
                    result = "\n\n".join(table_sections[:3])
                    self.logger.info(f"📊 Retrieved N guidelines with {len(table_sections)} table sections")
                else:
                    result = "\n\n".join(n_sections[:4])
                    self.logger.info(f"📝 Retrieved N guidelines with {len(n_sections)} text sections")
                
                # Analyze N staging coverage using LLM (guideline-based, not hardcoded)
                staging_coverage = await self._analyze_staging_coverage_llm(result, "N", body_part, cancer_type)
                self.logger.info(f"🎯 N staging coverage: {staging_coverage}")
                
                return result
            else:
                self.logger.warning(f"⚠️  No relevant N staging sections found for {cancer_type} of {body_part}")
                return await self._llm_fallback_guidelines("N", body_part, cancer_type)
                
        except Exception as e:
            self.logger.error(f"❌ Enhanced N retrieval failed: {str(e)}")
            return await self._llm_fallback_guidelines("N", body_part, cancer_type)

    def _filter_and_combine_results(self, all_results: List[str], stage_type: str) -> List[str]:
        """Filter and combine retrieval results for staging.
        
        Args:
            all_results: List of retrieved content
            stage_type: "T" or "N"
            
        Returns:
            Filtered and prioritized sections
        """
        if stage_type == "T":
            markers = ["t1", "t2", "t3", "t4", "t staging", "tumor", "invasion", "size"]
        else:  # N staging
            markers = ["n0", "n1", "n2", "n3", "n staging", "lymph", "node", "metastasis"]
        
        relevant_sections = []
        for content in all_results:
            # Look for staging content
            if any(marker in content.lower() for marker in markers):
                relevant_sections.append(content)
        
        return relevant_sections

    async def _analyze_staging_coverage_llm(self, guidelines: str, stage_type: str, body_part: str, cancer_type: str) -> str:
        """Analyze staging coverage using LLM and guidelines (respects LLM-first principles).
        
        Args:
            guidelines: Retrieved guideline content
            stage_type: "T" or "N"
            body_part: Body part/organ
            cancer_type: Cancer type
            
        Returns:
            LLM-generated summary of staging levels covered
        """
        prompt = f"""INSTRUCTIONS: Analyze AJCC guidelines and list {stage_type} staging levels. NO THINKING, NO EXPLANATIONS, NO ADDITIONAL TEXT.

BODY PART: {body_part}
CANCER TYPE: {cancer_type}

GUIDELINES:
{guidelines[:2000]}

TASK: List the specific {stage_type} staging levels mentioned in these guidelines.

REQUIREMENTS:
- Find explicit {stage_type} stage definitions (e.g., {stage_type}0, {stage_type}1, {stage_type}2, etc.)
- Include subdivisions (e.g., {stage_type}4a, {stage_type}4b or {stage_type}2a, {stage_type}2b, {stage_type}2c)
- Respond with ONLY a comma-separated list
- If no stages found, respond with "none detected"

RESPOND WITH ONLY THE LIST: {stage_type.lower()}0, {stage_type.lower()}1, {stage_type.lower()}2, {stage_type.lower()}3, {stage_type.lower()}4a, {stage_type.lower()}4b"""

        try:
            response = await self.llm_provider.generate(prompt)
            # Clean response: remove thinking tags and extra whitespace
            import re
            cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            cleaned = cleaned.strip().lower()
            
            # Extract only the staging list if other text is present
            if "," in cleaned:
                # Look for pattern like "t0, t1, t2, t3" or "n2a, n2b, n2c"
                stage_pattern = rf'{stage_type.lower()}\d+[a-c]?'
                stages = re.findall(stage_pattern, cleaned)
                if stages:
                    return ", ".join(stages)
            
            return cleaned if cleaned else f"none detected for {stage_type.lower()}"
        except Exception as e:
            self.logger.error(f"Failed to analyze {stage_type} staging coverage: {str(e)}")
            return f"error analyzing {stage_type.lower()} coverage"