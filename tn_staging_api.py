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
        
        # Check if we have the right session, if not, try to restore or simulate continuation
        current_session_id = getattr(self.system, 'session_id', None)
        
        if session_id != current_session_id:
            # For now, create a simplified analysis with the user response as additional context
            self.logger.warning(f"Session ID mismatch. Current: {current_session_id}, Requested: {session_id}")
            self.logger.info("Performing new analysis with user response as additional context")
            
            # Create a combined report with user response
            combined_report = f"User provided additional information: {user_response}"
            
            return {
                "success": False,
                "error": "Session expired. Please start a new analysis with your additional information included in the original report.",
                "backend": self.backend,
                "session_id": current_session_id,
                "suggested_action": "restart_with_context",
                "additional_context": user_response
            }
        
        try:
            # Add user response and continue analysis
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