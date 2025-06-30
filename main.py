"""Main application for TN staging analysis system."""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.detect import DetectionAgent
from agents.retrieve_guideline import GuidelineRetrievalAgent
from agents.staging_t import TStagingAgent
from agents.staging_n import NStagingAgent
from agents.query import QueryAgent
from agents.report import ReportAgent
from contexts.context_manager_optimized import OptimizedContextManager, OptimizedWorkflowOrchestrator
from config import (
    LLMProviderFactory, create_hybrid_provider,
    get_openai_config, get_ollama_config, get_hybrid_config,
    validate_openai_config, validate_ollama_config
)
from config.llm_providers import create_llm_provider
from utils.logging_config import setup_logging, SessionLogger

class TNStagingSystem:
    """Main TN staging analysis system."""
    
    def __init__(self, backend: str, config: Optional[Dict[str, Any]] = None, 
                 session_id: Optional[str] = None, debug: bool = False):
        """Initialize the TN staging system.
        
        Args:
            backend: Backend to use ("openai", "ollama", or "hybrid")
            config: Optional configuration override
            session_id: Optional session ID for logging
            debug: Enable debug logging
        """
        self.backend = backend
        self.config = config or self._get_default_config(backend)
        self.llm_provider = None
        self.agents = {}
        self.context_manager = None
        self.orchestrator = None
        self.debug = debug
        
        # Set up session logging
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())[:8]
        
        self.session_logger = setup_logging(session_id, debug)
        self.session_id = session_id
        self.logger = logging.getLogger("tn_staging_system")
        
        # Log system initialization
        self.session_logger.log_event("system_init", {
            "backend": backend,
            "session_id": session_id,
            "debug": debug
        })
        
        # Initialize system
        self._initialize_system()
    
    
    def _get_default_config(self, backend: str) -> Dict[str, Any]:
        """Get default configuration for backend.
        
        Args:
            backend: Backend type
            
        Returns:
            Configuration dictionary
        """
        if backend == "openai":
            return get_openai_config()
        elif backend == "ollama":
            return get_ollama_config()
        elif backend == "hybrid":
            return get_hybrid_config()
        else:
            raise ValueError(f"Unknown backend: {backend}")
    
    def _initialize_system(self):
        """Initialize the system components."""
        self.logger.info(f"Initializing TN staging system with {self.backend} backend")
        
        # Validate configuration
        if not self._validate_config():
            raise ValueError(f"Invalid configuration for {self.backend} backend")
        
        # Create enhanced LLM provider with response cleaning and structured outputs
        if self.backend == "hybrid":
            # TODO: Add structured hybrid provider support
            self.llm_provider = create_hybrid_provider(self.config)
        else:
            # Use unified LLM provider with all features (structured + enhanced)
            self.llm_provider = create_llm_provider(self.backend, self.config)
            
            # Pass session logger to enhanced provider for detailed LLM response logging
            if hasattr(self.llm_provider, 'session_logger'):
                self.llm_provider.session_logger = self.session_logger
        
        # Initialize agents
        self._initialize_agents()
        
        # Initialize optimized context manager and orchestrator
        self.context_manager = OptimizedContextManager(session_id=self.session_id)
        # Attach session logger to context manager for detailed logging
        self.context_manager.session_logger = self.session_logger
        self.orchestrator = OptimizedWorkflowOrchestrator(self.agents, self.context_manager)
        
        self.logger.info("System initialization complete")
    
    def _validate_config(self) -> bool:
        """Validate the configuration.
        
        Returns:
            True if configuration is valid
        """
        if self.backend == "openai":
            return validate_openai_config(self.config)
        elif self.backend == "ollama":
            return validate_ollama_config(self.config)
        elif self.backend == "hybrid":
            # Validate both parts
            gen_config = self.config.get("generation", {})
            embed_config = self.config.get("embedding", {})
            return (
                validate_ollama_config(gen_config) and
                validate_openai_config(embed_config)
            )
        return False
    
    def _initialize_agents(self):
        """Initialize all agents."""
        self.logger.info("Initializing agents...")
        
        # Determine vector store path based on backend
        if self.backend == "hybrid":
            vector_store_path = self.config.get("vector_store", {}).get("path")
        else:
            vector_store_path = self.config.get("vector_store", {}).get("path")
        
        self.agents = {
            "detect": DetectionAgent(self.llm_provider),
            "retrieve_guideline": GuidelineRetrievalAgent(
                self.llm_provider,
                vector_store_path
            ),
            "staging_t": TStagingAgent(self.llm_provider),
            "staging_n": NStagingAgent(self.llm_provider),
            "query": QueryAgent(self.llm_provider),
            "report": ReportAgent(self.llm_provider)
        }
        
        self.logger.info(f"Initialized {len(self.agents)} agents")
    
    async def analyze_report(self, report: str) -> Dict[str, Any]:
        """Analyze a radiologic report for TN staging.
        
        Args:
            report: Radiologic report text
            
        Returns:
            Analysis results
        """
        start_time = time.time()
        self.logger.info("Starting TN staging analysis")
        
        # Log analysis start
        self.session_logger.log_analysis_start(report, self.backend)
        
        try:
            # Initialize context with report
            self.context_manager.context.context_R = report
            
            # Run the initial workflow (optimized)
            results = await self.orchestrator.run_initial_workflow()
            
            # Get final context
            final_context = self.context_manager.get_context()
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Check if workflow is paused for user query (optimized workflow uses query_needed)
            if results.get("query_needed") or results.get("workflow_status") == "awaiting_user_response":
                # Query needed - return partial results with query
                analysis_results = {
                    "success": True,
                    "query_needed": True,
                    "query_question": results.get("query_question") or final_context.context_Q,
                    "t_stage": final_context.context_T,
                    "n_stage": final_context.context_N,
                    "t_confidence": final_context.context_CT,
                    "n_confidence": final_context.context_CN,
                    "t_rationale": final_context.context_RationaleT,
                    "n_rationale": final_context.context_RationaleN,
                    "body_part": final_context.context_B.get("body_part") if final_context.context_B else None,
                    "cancer_type": final_context.context_B.get("cancer_type") if final_context.context_B else None,
                    "t_guidelines": final_context.context_GT,
                    "n_guidelines": final_context.context_GN,
                    "session_id": self.session_id,
                    "backend": self.backend,
                    "duration": duration
                }
            else:
                # Complete analysis
                analysis_results = {
                    "success": True,
                    "tn_stage": f"{final_context.context_T}{final_context.context_N}",
                    "t_stage": final_context.context_T,
                    "n_stage": final_context.context_N,
                    "t_confidence": final_context.context_CT,
                    "n_confidence": final_context.context_CN,
                    "t_rationale": final_context.context_RationaleT,
                    "n_rationale": final_context.context_RationaleN,
                    "body_part": final_context.context_B.get("body_part") if final_context.context_B else None,
                    "cancer_type": final_context.context_B.get("cancer_type") if final_context.context_B else None,
                    "final_report": final_context.final_report,
                    "query_generated": final_context.context_Q,
                    "user_response": final_context.context_RR,
                    "t_guidelines": final_context.context_GT,
                    "n_guidelines": final_context.context_GN,
                    "workflow_summary": results,
                    "session_id": self.session_id,
                    "backend": self.backend,
                    "duration": duration
                }
            
            # Log analysis completion
            self.session_logger.log_analysis_complete(analysis_results, duration)
            
            # Auto-save session for continuation (always save, regardless of query status)
            try:
                session_path = self.context_manager.save_session()
                self.logger.debug(f"Session auto-saved to {session_path}")
            except Exception as e:
                self.logger.warning(f"Failed to auto-save session: {e}")
            
            # Log appropriate message based on analysis state
            if analysis_results.get("query_needed"):
                stage_summary = f"T{analysis_results.get('t_stage', '?')}N{analysis_results.get('n_stage', '?')} (query pending)"
                self.logger.info(f"Analysis paused for user query: {stage_summary} (duration: {duration:.2f}s)")
            else:
                tn_stage = analysis_results.get('tn_stage', f"T{analysis_results.get('t_stage', '?')}N{analysis_results.get('n_stage', '?')}")
                self.logger.info(f"Analysis complete: {tn_stage} (duration: {duration:.2f}s)")
            
            return analysis_results
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.logger.error(f"Analysis failed: {error_msg}")
            self.session_logger.log_error("analysis_failed", error_msg, {
                "backend": self.backend,
                "duration": duration
            })
            
            return {
                "success": False,
                "error": error_msg,
                "session_id": self.session_id,
                "backend": self.backend,
                "duration": duration
            }
    
    def add_user_response(self, response: str) -> None:
        """Add user response to query and re-run staging if needed.
        
        Args:
            response: User's response to query
        """
        self.context_manager.add_user_response(response)
        
        # Log user interaction
        self.session_logger.log_user_interaction("query_response", {
            "response_length": len(response),
            "response_text": response  # Store full response, no truncation
        })
        
        self.logger.info("User response added to context")
    
    async def continue_analysis_with_response(self, user_response: str) -> Dict[str, Any]:
        """Continue analysis workflow with user response.
        
        Args:
            user_response: User's response to query
            
        Returns:
            Final analysis results
        """
        start_time = time.time()
        self.logger.info("Continuing analysis with user response")
        
        try:
            # Continue workflow with response
            results = await self.orchestrator.continue_workflow_with_response(user_response)
            
            # Get final context
            final_context = self.context_manager.get_context()
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Compile results
            analysis_results = {
                "success": True,
                "tn_stage": f"{final_context.context_T}{final_context.context_N}",
                "t_stage": final_context.context_T,
                "n_stage": final_context.context_N,
                "t_confidence": final_context.context_CT,
                "n_confidence": final_context.context_CN,
                "t_rationale": final_context.context_RationaleT,
                "n_rationale": final_context.context_RationaleN,
                "body_part": final_context.context_B.get("body_part") if final_context.context_B else None,
                "cancer_type": final_context.context_B.get("cancer_type") if final_context.context_B else None,
                "final_report": final_context.final_report,
                "query_generated": final_context.context_Q,
                "user_response": final_context.context_RR,
                "workflow_summary": results,
                "session_id": self.session_id,
                "backend": self.backend,
                "duration": duration
            }
            
            # Log analysis completion
            self.session_logger.log_analysis_complete(analysis_results, duration)
            
            self.logger.info(f"Analysis continued: {analysis_results['tn_stage']} (duration: {duration:.2f}s)")
            return analysis_results
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.logger.error(f"Continue analysis failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "session_id": self.session_id,
                "backend": self.backend,
                "duration": duration
            }

    async def rerun_staging_with_response(self) -> Dict[str, Any]:
        """Re-run staging agents after user response.
        
        Returns:
            Updated analysis results
        """
        self.logger.info("Re-running staging with user response")
        
        try:
            # Re-run T and N staging with updated context
            await asyncio.gather(
                self.orchestrator._run_agent("staging_t"),
                self.orchestrator._run_agent("staging_n")
            )
            
            # Generate updated report
            await self.orchestrator._run_agent("report")
            
            # Return updated results
            return await self.get_current_results()
            
        except Exception as e:
            self.logger.error(f"Re-run failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_current_results(self) -> Dict[str, Any]:
        """Get current analysis results.
        
        Returns:
            Current results dictionary
        """
        context = self.context_manager.get_context()
        
        return {
            "success": True,
            "tn_stage": f"{context.context_T}{context.context_N}",
            "t_stage": context.context_T,
            "n_stage": context.context_N,
            "t_confidence": context.context_CT,
            "n_confidence": context.context_CN,
            "t_rationale": context.context_RationaleT,
            "n_rationale": context.context_RationaleN,
            "body_part": context.context_B.get("body_part") if context.context_B else None,
            "cancer_type": context.context_B.get("cancer_type") if context.context_B else None,
            "final_report": context.final_report,
            "query_generated": context.context_Q,
            "user_response": context.context_RR,
            "session_id": self.context_manager.session_id,
            "backend": self.backend,
            "needs_query": self.context_manager.needs_query()
        }
    
    def save_session(self, filepath: Optional[Path] = None) -> Path:
        """Save the current session.
        
        Args:
            filepath: Optional path to save to
            
        Returns:
            Path where session was saved
        """
        # Convert Path to string if provided
        filepath_str = str(filepath) if filepath else None
        session_path = self.context_manager.save_session(filepath_str)
        
        # Log session save
        self.session_logger.log_event("session_saved", {
            "session_path": str(session_path)
        })
        
        return session_path
    
    def get_session_logs(self) -> Dict[str, Any]:
        """Get session logs for display.
        
        Returns:
            Session logs and metadata
        """
        return self.session_logger.get_session_logs()
    
    def finalize_session(self) -> None:
        """Finalize the session and close logging."""
        # Get final session summary
        context = self.context_manager.get_context()
        summary = {
            "final_tn_stage": f"{context.context_T}{context.context_N}" if context.context_T and context.context_N else None,
            "backend": self.backend,
            "messages_processed": len(self.context_manager.get_message_history()),
            "had_query": context.context_Q is not None,
            "had_user_response": context.context_RR is not None
        }
        
        # Finalize session logging
        self.session_logger.finalize_session(summary)
    
    @classmethod
    def load_session(cls, filepath: Path, backend: str) -> "TNStagingSystem":
        """Load a saved session.
        
        Args:
            filepath: Path to session file
            backend: Backend to use
            
        Returns:
            TNStagingSystem instance with loaded session
        """
        system = cls(backend)
        system.context_manager = OptimizedContextManager.load_session(filepath)
        system.orchestrator = OptimizedWorkflowOrchestrator(system.agents, system.context_manager)
        return system

async def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(description="TN Staging Analysis System")
    parser.add_argument(
        "--backend",
        choices=["openai", "ollama", "hybrid"],
        default="hybrid",
        help="LLM backend to use"
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to radiologic report file or report text"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enable interactive mode for queries"
    )
    parser.add_argument(
        "--save-session",
        help="Save session to specified file"
    )
    parser.add_argument(
        "--load-session",
        help="Load session from specified file"
    )
    parser.add_argument(
        "--config",
        help="Path to configuration file"
    )
    
    args = parser.parse_args()
    
    # Load configuration if provided
    config = None
    if args.config:
        import json
        with open(args.config) as f:
            config = json.load(f)
    
    # Initialize system
    if args.load_session:
        system = TNStagingSystem.load_session(Path(args.load_session), args.backend)
        print(f"Loaded session from {args.load_session}")
    else:
        system = TNStagingSystem(args.backend, config)
    
    # Load report
    if Path(args.report).exists():
        with open(args.report) as f:
            report_text = f.read()
    else:
        report_text = args.report
    
    # Analyze report
    print("Analyzing radiologic report...")
    results = await system.analyze_report(report_text)
    
    if results["success"]:
        print("\n" + "="*50)
        print("TN STAGING ANALYSIS RESULTS")
        print("="*50)
        print(f"Body Part: {results['body_part']}")
        print(f"Cancer Type: {results['cancer_type']}")
        print(f"TN Stage: {results['tn_stage']}")
        print(f"T Stage: {results['t_stage']} (Confidence: {results['t_confidence']:.1%})")
        print(f"N Stage: {results['n_stage']} (Confidence: {results['n_confidence']:.1%})")
        print(f"Backend: {results['backend']}")
        
        # Handle queries if needed
        if results.get("query_generated") and args.interactive:
            print("\n" + "-"*40)
            print("ADDITIONAL INFORMATION NEEDED")
            print("-"*40)
            print(results["query_generated"])
            
            response = input("\nPlease provide additional information: ")
            system.add_user_response(response)
            
            print("Re-analyzing with additional information...")
            updated_results = await system.rerun_staging_with_response()
            
            if updated_results["success"]:
                print(f"\nUpdated TN Stage: {updated_results['tn_stage']}")
                print(f"Updated T Stage: {updated_results['t_stage']} (Confidence: {updated_results['t_confidence']:.1%})")
                print(f"Updated N Stage: {updated_results['n_stage']} (Confidence: {updated_results['n_confidence']:.1%})")
        
        # Save session if requested
        if args.save_session:
            session_path = system.save_session(Path(args.save_session))
            print(f"\nSession saved to: {session_path}")
    
    else:
        print(f"Analysis failed: {results['error']}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))