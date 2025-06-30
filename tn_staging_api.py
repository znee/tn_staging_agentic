#!/usr/bin/env python3
"""TN Staging Core API - No GUI Dependencies"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Environment setup
os.environ.update({
    'TORCH_JIT': '0',
    'TOKENIZERS_PARALLELISM': 'false'
})

# Block PyTorch
class TorchBlocker:
    def __getattr__(self, name):
        return None
if 'torch' not in sys.modules:
    sys.modules['torch'] = TorchBlocker()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from main import TNStagingSystem

class TNStagingAPI:
    """Core TN Staging API without GUI dependencies."""
    
    def __init__(self, backend: str = "ollama", debug: bool = False):
        """Initialize the API.
        
        Args:
            backend: Backend to use ("ollama", "openai", "hybrid")
            debug: Enable debug logging
        """
        self.backend = backend
        self.debug = debug
        self.system = None
        self._initialize_system()
    
    def _initialize_system(self):
        """Initialize the staging system."""
        try:
            self.system = TNStagingSystem(
                backend=self.backend,
                debug=self.debug
            )
            if self.debug:
                print(f"✅ Initialized {self.backend} backend")
        except Exception as e:
            print(f"❌ Failed to initialize {self.backend} backend: {e}")
            raise
    
    async def analyze_report(self, report_text: str) -> Dict[str, Any]:
        """Analyze a radiologic report.
        
        Args:
            report_text: The radiologic report text
            
        Returns:
            Analysis results dictionary
        """
        if not self.system:
            raise RuntimeError("System not initialized")
        
        if not report_text.strip():
            return {
                "success": False,
                "error": "Empty report text",
                "backend": self.backend
            }
        
        try:
            result = await self.system.analyze_report(report_text)
            
            # Ensure we have success field
            if "success" not in result:
                result["success"] = True
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "backend": self.backend,
                "report_length": len(report_text)
            }
    
    def analyze_report_sync(self, report_text: str) -> Dict[str, Any]:
        """Synchronous wrapper for analyze_report.
        
        Args:
            report_text: The radiologic report text
            
        Returns:
            Analysis results dictionary
        """
        return asyncio.run(self.analyze_report(report_text))
    
    async def continue_analysis(self, session_id: str, user_response: str) -> Dict[str, Any]:
        """Continue analysis with user response to query.
        
        Args:
            session_id: Session ID from previous analysis
            user_response: User's response to query
            
        Returns:
            Continued analysis results
        """
        if not self.system:
            raise RuntimeError("System not initialized")
        
        # Check if we have the right session
        current_session_id = getattr(self.system, 'session_id', None)
        
        if session_id != current_session_id:
            # Session mismatch - this happens with subprocess calls
            # For now, return an error suggesting to use the optimized GUI
            return {
                "success": False,
                "error": f"Session mismatch. Expected: {current_session_id}, Got: {session_id}. Use optimized GUI for session continuation.",
                "backend": self.backend,
                "session_id": current_session_id,
                "suggested_action": "use_optimized_gui"
            }
        
        try:
            # Add user response and continue analysis using optimized workflow
            result = await self.system.continue_analysis_with_response(user_response)
            
            if "success" not in result:
                result["success"] = True
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "backend": self.backend,
                "session_id": session_id
            }
    
    def continue_analysis_sync(self, session_id: str, user_response: str) -> Dict[str, Any]:
        """Synchronous wrapper for continue_analysis.
        
        Args:
            session_id: Session ID from previous analysis
            user_response: User's response to query
            
        Returns:
            Continued analysis results
        """
        return asyncio.run(self.continue_analysis(session_id, user_response))
    
    async def analyze_with_selective_preservation(
        self, 
        enhanced_report: str, 
        preserved_contexts: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Analyze report with selective preservation of high-confidence contexts.
        
        Args:
            enhanced_report: Enhanced report text with additional information
            preserved_contexts: Contexts to preserve from previous analysis
            
        Returns:
            Analysis results with selective preservation applied
        """
        if not self.system:
            raise RuntimeError("System not initialized")
        
        if not enhanced_report.strip():
            return {
                "success": False,
                "error": "Empty enhanced report text",
                "backend": self.backend
            }
        
        try:
            # Use existing system but reset context for fresh analysis
            selective_system = self.system
            
            # Preserve existing guidelines before resetting context
            existing_context = selective_system.context_manager.get_context()
            existing_t_guidelines = existing_context.context_GT
            existing_n_guidelines = existing_context.context_GN
            
            # Reset context for fresh analysis while preserving system state
            from contexts.context_manager_optimized import AgentContext
            selective_system.context_manager.context = AgentContext()
            
            # Preserve session metadata
            if hasattr(selective_system.context_manager, 'session_id'):
                selective_system.context_manager.context.metadata["session_id"] = selective_system.context_manager.session_id
            
            # Preserve round tracking for multi-round scenarios
            if preserved_contexts and preserved_contexts.get("round_number"):
                selective_system.context_manager.context.metadata["round_number"] = preserved_contexts["round_number"]
            
            # Initialize context with enhanced report
            selective_system.context_manager.context.context_R = enhanced_report
            
            # Apply preserved contexts if provided
            if preserved_contexts:
                selective_system.logger.info(f"🚀 SELECTIVE PRESERVATION ACTIVE - Contexts: {list(preserved_contexts.keys())}")
                context = selective_system.context_manager.context
                
                # Preserve body part and cancer type detection
                if preserved_contexts.get("body_part") and preserved_contexts.get("cancer_type"):
                    context.context_B = {
                        "body_part": preserved_contexts["body_part"],
                        "cancer_type": preserved_contexts["cancer_type"]
                    }
                
                # Preserve T staging if high confidence
                if (preserved_contexts.get("t_stage") and 
                    preserved_contexts.get("t_stage") != "TX" and
                    preserved_contexts.get("t_confidence", 0) >= 0.7):
                    context.context_T = preserved_contexts["t_stage"]
                    context.context_CT = preserved_contexts["t_confidence"]
                    context.context_RationaleT = preserved_contexts.get("t_rationale")
                    selective_system.logger.info(f"✅ Preserved T staging: {context.context_T} (confidence: {context.context_CT:.1%})")
                else:
                    selective_system.logger.info(f"❌ T staging not preserved - stage: {preserved_contexts.get('t_stage')}, confidence: {preserved_contexts.get('t_confidence', 0):.1%}")
                
                # Preserve N staging if high confidence
                if (preserved_contexts.get("n_stage") and 
                    preserved_contexts.get("n_stage") != "NX" and
                    preserved_contexts.get("n_confidence", 0) >= 0.7):
                    context.context_N = preserved_contexts["n_stage"]
                    context.context_CN = preserved_contexts["n_confidence"]
                    context.context_RationaleN = preserved_contexts.get("n_rationale")
                    selective_system.logger.info(f"✅ Preserved N staging: {context.context_N} (confidence: {context.context_CN:.1%})")
                else:
                    selective_system.logger.info(f"❌ N staging not preserved - stage: {preserved_contexts.get('n_stage')}, confidence: {preserved_contexts.get('n_confidence', 0):.1%}")
                
                # Preserve guidelines (from preserved_contexts OR existing context)
                if preserved_contexts.get("t_guidelines"):
                    context.context_GT = preserved_contexts["t_guidelines"]
                elif existing_t_guidelines:
                    context.context_GT = existing_t_guidelines
                    
                if preserved_contexts.get("n_guidelines"):
                    context.context_GN = preserved_contexts["n_guidelines"]
                elif existing_n_guidelines:
                    context.context_GN = existing_n_guidelines
            
            # Run selective workflow
            if preserved_contexts:
                # Skip detection if we have preserved body part info
                if not (preserved_contexts.get("body_part") and preserved_contexts.get("cancer_type")):
                    await selective_system.orchestrator._run_agent("detect")
                else:
                    selective_system.logger.info("Skipping detection - body part and cancer type preserved from previous session")
                
                # Check if guideline retrieval is needed
                needs_t_restaging = selective_system.context_manager.needs_t_restaging()
                needs_n_restaging = selective_system.context_manager.needs_n_restaging()
                
                # Check if guidelines are available (either preserved or already in context)
                current_context = selective_system.context_manager.get_context()
                has_guidelines_available = bool(
                    current_context.context_GT and current_context.context_GN
                )
                
                guidelines_reuse = "reuse" if has_guidelines_available else "retrieve"
                selective_system.logger.info(f"🔍 Re-assessment needed: T={needs_t_restaging}, N={needs_n_restaging}, Guidelines={guidelines_reuse}")
                
                if (needs_t_restaging or needs_n_restaging) and not has_guidelines_available:
                    # Need guidelines for re-staging and don't have them available
                    selective_system.logger.info("Retrieving guidelines for re-staging")
                    await selective_system.orchestrator._run_agent("retrieve_guideline")
                elif has_guidelines_available and (needs_t_restaging or needs_n_restaging):
                    # Have guidelines available - reuse them for re-staging
                    selective_system.logger.info("Reusing existing guidelines for re-staging")
                elif not (needs_t_restaging or needs_n_restaging):
                    # No re-staging needed
                    selective_system.logger.info("Skipping guideline retrieval - no re-staging needed")
                
                # Run only necessary staging agents
                tasks = []
                agents_rerun = []
                
                # Check if T staging needs to be re-run
                if selective_system.context_manager.needs_t_restaging():
                    tasks.append(selective_system.orchestrator._run_agent("staging_t"))
                    agents_rerun.append("T")
                
                # Check if N staging needs to be re-run
                if selective_system.context_manager.needs_n_restaging():
                    tasks.append(selective_system.orchestrator._run_agent("staging_n"))
                    agents_rerun.append("N")
                
                # Run necessary staging agents
                if tasks:
                    await asyncio.gather(*tasks)
                
                # Generate final report
                await selective_system.orchestrator._run_agent("report")
                
                # Log what was preserved vs re-analyzed
                selective_system.logger.info(f"Selective preservation: Re-ran {agents_rerun}, preserved others")
                
            else:
                # No preserved contexts - run full analysis
                results = await selective_system.orchestrator.run_initial_workflow()
                if results.get("query_needed"):
                    # Still need query even after enhancement
                    final_context = selective_system.context_manager.get_context()
                    return {
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
                        "session_id": selective_system.session_id,
                        "backend": self.backend
                    }
            
            # Get final results
            final_context = selective_system.context_manager.get_context()
            
            result = {
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
                "session_id": selective_system.session_id,
                "backend": self.backend
            }
            
            # Add selective preservation metadata
            if preserved_contexts:
                # Recalculate these for metadata (they're in local scope from the workflow)
                final_context = selective_system.context_manager.get_context()
                preserved_t = (preserved_contexts.get("t_stage") and 
                              preserved_contexts.get("t_stage") != "TX" and
                              preserved_contexts.get("t_confidence", 0) >= 0.7)
                preserved_n = (preserved_contexts.get("n_stage") and 
                              preserved_contexts.get("n_stage") != "NX" and
                              preserved_contexts.get("n_confidence", 0) >= 0.7)
                
                skipped_agents = []
                if preserved_contexts.get("body_part") and preserved_contexts.get("cancer_type"):
                    skipped_agents.append("detection")
                if preserved_t and preserved_n:
                    skipped_agents.append("guideline_retrieval")
                
                result["metadata"] = {
                    "selective_preservation": True,
                    "preserved_contexts": preserved_contexts,
                    "agents_rerun": agents_rerun if 'agents_rerun' in locals() else [],
                    "agents_skipped": skipped_agents,
                    "optimization_details": {
                        "detection_skipped": "detection" in skipped_agents,
                        "guideline_retrieval_skipped": "guideline_retrieval" in skipped_agents,
                        "t_staging_preserved": preserved_t,
                        "n_staging_preserved": preserved_n
                    }
                }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "backend": self.backend,
                "report_length": len(enhanced_report)
            }
    
    def analyze_with_selective_preservation_sync(
        self, 
        enhanced_report: str, 
        preserved_contexts: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Synchronous wrapper for selective preservation analysis.
        
        Args:
            enhanced_report: Enhanced report text with additional information
            preserved_contexts: Contexts to preserve from previous analysis
            
        Returns:
            Analysis results with selective preservation applied
        """
        return asyncio.run(self.analyze_with_selective_preservation(enhanced_report, preserved_contexts))
    
    def check_backend_status(self) -> Dict[str, Any]:
        """Check backend status and requirements.
        
        Returns:
            Status information
        """
        status = {
            "backend": self.backend,
            "available": False,
            "message": "",
            "requirements": []
        }
        
        if self.backend == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                status["available"] = True
                status["message"] = "OpenAI API key configured"
            else:
                status["message"] = "OpenAI API key not set"
                status["requirements"] = ["Set OPENAI_API_KEY environment variable"]
                
        elif self.backend in ["ollama", "hybrid"]:
            try:
                import requests
                response = requests.get("http://localhost:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    required_models = ["qwen3:8b", "nomic-embed-text:latest"]
                    available_models = [m.get("name", "") for m in models]
                    
                    missing_models = []
                    for req_model in required_models:
                        if not any(req_model in avail for avail in available_models):
                            missing_models.append(req_model)
                    
                    if missing_models:
                        status["message"] = f"Missing models: {', '.join(missing_models)}"
                        status["requirements"] = [f"Pull model: ollama pull {model}" for model in missing_models]
                    else:
                        status["available"] = True
                        status["message"] = f"Ollama running with {len(models)} models"
                else:
                    status["message"] = "Ollama server not responding"
                    status["requirements"] = ["Start Ollama server: ollama serve"]
            except Exception as e:
                status["message"] = f"Ollama connection failed: {e}"
                status["requirements"] = ["Install and start Ollama: https://ollama.ai"]
        
        # Check hybrid additional requirements
        if self.backend == "hybrid":
            if not os.getenv("OPENAI_API_KEY"):
                status["available"] = False
                status["requirements"].append("Set OPENAI_API_KEY for hybrid mode")
        
        return status
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information.
        
        Returns:
            System information dictionary
        """
        info = {
            "backend": self.backend,
            "debug": self.debug,
            "system_initialized": self.system is not None,
            "agents": [],
            "vector_stores": []
        }
        
        if self.system:
            info["agents"] = list(self.system.agents.keys())
            info["session_id"] = getattr(self.system, 'session_id', 'unknown')
        
        # Check vector stores
        vector_stores = {
            "ollama": Path("faiss_stores/ajcc_guidelines_local"),
            "openai": Path("faiss_stores/ajcc_guidelines_openai")
        }
        
        for name, path in vector_stores.items():
            info["vector_stores"].append({
                "name": name,
                "path": str(path),
                "exists": path.exists()
            })
        
        return info

def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description="TN Staging Analysis Core API")
    parser.add_argument(
        "--backend", 
        choices=["ollama", "openai", "hybrid"], 
        default="ollama",
        help="Analysis backend"
    )
    parser.add_argument(
        "--report", 
        help="Radiologic report text or path to file"
    )
    parser.add_argument(
        "--file", 
        help="Path to radiologic report file"
    )
    parser.add_argument(
        "--status", 
        action="store_true",
        help="Check backend status"
    )
    parser.add_argument(
        "--info", 
        action="store_true",
        help="Show system information"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--json", 
        action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--continue-session",
        help="Continue analysis with session ID and user response"
    )
    parser.add_argument(
        "--user-response",
        help="User response to query (use with --continue-session)"
    )
    
    args = parser.parse_args()
    
    # Initialize API
    try:
        api = TNStagingAPI(backend=args.backend, debug=args.debug)
    except Exception as e:
        result = {"error": f"Failed to initialize API: {e}", "success": False}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ {result['error']}")
        return 1
    
    # Handle different commands
    if args.status:
        status = api.check_backend_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(f"Backend: {status['backend']}")
            print(f"Status: {'✅ Available' if status['available'] else '❌ Not Available'}")
            print(f"Message: {status['message']}")
            if status['requirements']:
                print("Requirements:")
                for req in status['requirements']:
                    print(f"  - {req}")
        return 0
    
    # Continue analysis
    if args.continue_session:
        if not args.user_response:
            result = {"error": "User response required with --continue-session", "success": False}
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"❌ {result['error']}")
            return 1
        
        if not args.json:
            print("🔄 Continuing analysis...")
        
        result = api.continue_analysis_sync(args.continue_session, args.user_response)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                print(f"✅ Analysis continued successfully")
                print(f"TN Stage: {result.get('tn_stage', 'Unknown')}")
                print(f"Duration: {result.get('duration', 0):.2f}s")
            else:
                print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        return 0
    
    if args.info:
        info = api.get_system_info()
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print(f"Backend: {info['backend']}")
            print(f"Agents: {', '.join(info['agents'])}")
            print(f"Vector Stores:")
            for vs in info['vector_stores']:
                status = "✅" if vs['exists'] else "❌"
                print(f"  {status} {vs['name']}: {vs['path']}")
        return 0
    
    # Analyze report
    report_text = None
    if args.report:
        # Check if it looks like a file path (not too long and no newlines)
        if (len(args.report) < 260 and 
            '\n' not in args.report and 
            not args.report.startswith(' ') and
            '/' in args.report):
            try:
                if Path(args.report).exists():
                    with open(args.report) as f:
                        report_text = f.read()
                else:
                    report_text = args.report
            except (OSError, ValueError):
                # If path check fails, treat as text
                report_text = args.report
        else:
            # Treat as report text directly
            report_text = args.report
    elif args.file:
        if Path(args.file).exists():
            with open(args.file) as f:
                report_text = f.read()
        else:
            print(f"❌ File not found: {args.file}")
            return 1
    else:
        print("❌ No report provided. Use --report or --file")
        return 1
    
    # Run analysis
    if args.json:
        print("Starting analysis...")
    else:
        print(f"🔍 Analyzing report with {args.backend} backend...")
    
    try:
        result = api.analyze_report_sync(report_text)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("success"):
                print("\n" + "="*50)
                print("TN STAGING ANALYSIS RESULTS")
                print("="*50)
                print(f"T Stage: {result.get('t_stage', 'Unknown')}")
                print(f"N Stage: {result.get('n_stage', 'Unknown')}")
                print(f"Combined: {result.get('tn_stage', 'Unknown')}")
                print(f"Confidence T: {result.get('t_confidence', 0):.1%}")
                print(f"Confidence N: {result.get('n_confidence', 0):.1%}")
                print(f"Backend: {result.get('backend', 'Unknown')}")
                print(f"Duration: {result.get('duration', 0):.2f}s")
                
                if result.get('t_rationale'):
                    print(f"\nT Staging Rationale:")
                    print(result['t_rationale'])
                    
                if result.get('n_rationale'):
                    print(f"\nN Staging Rationale:")
                    print(result['n_rationale'])
                    
            else:
                print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
                return 1
                
    except Exception as e:
        result = {"error": str(e), "success": False}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Analysis failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())