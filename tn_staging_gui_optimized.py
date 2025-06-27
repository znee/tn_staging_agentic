#!/usr/bin/env python3
"""TN Staging GUI - Optimized with Session Continuation"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Environment setup
os.environ.update({
    'TORCH_JIT': '0',
    'TOKENIZERS_PARALLELISM': 'false'
})

import streamlit as st

# Page config
st.set_page_config(
    page_title="TN Staging Analysis",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

class OptimizedTNStagingGUI:
    """Streamlit GUI with session continuation optimization."""
    
    def __init__(self):
        # Instead of subprocess calls, maintain persistent API connection
        self.api_instances = {}  # Store API instances by session ID
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize Streamlit session state."""
        if 'api_instances' not in st.session_state:
            st.session_state.api_instances = {}
    
    def call_api(self, command: str, **kwargs) -> Dict[str, Any]:
        """Call the core API using direct imports instead of subprocess.
        
        Args:
            command: API command to run
            **kwargs: Additional arguments
            
        Returns:
            API response as dictionary
        """
        try:
            backend = kwargs.get("backend", "ollama")
            session_id = kwargs.get("session_id")
            
            # Handle different commands
            if command == "status":
                from tn_staging_api import TNStagingAPI
                api = TNStagingAPI(backend=backend)
                return api.check_backend_status()
                
            elif command == "info":
                from tn_staging_api import TNStagingAPI
                api = TNStagingAPI(backend=backend)
                return api.get_system_info()
                
            elif command == "analyze":
                report_text = kwargs.get("report")
                if not report_text:
                    return {"success": False, "error": "No report provided"}
                
                # Create new API instance for analysis
                from tn_staging_api import TNStagingAPI
                api = TNStagingAPI(backend=backend)
                
                # Run analysis
                result = api.analyze_report_sync(report_text)
                
                # Store API instance for potential continuation
                if result.get("success") and result.get("session_id"):
                    session_id = result["session_id"]
                    st.session_state.api_instances[session_id] = api
                
                return result
                
            elif command == "continue":
                session_id = kwargs.get("session_id")
                user_response = kwargs.get("user_response")
                
                if not session_id or not user_response:
                    return {"success": False, "error": "Missing session_id or user_response"}
                
                # Get existing API instance
                if session_id in st.session_state.api_instances:
                    api = st.session_state.api_instances[session_id]
                    return api.continue_analysis_sync(session_id, user_response)
                else:
                    return {
                        "success": False, 
                        "error": f"Session {session_id} not found in current GUI session"
                    }
            
            elif command == "analyze_selective":
                # Selective analysis with preserved contexts
                report_text = kwargs.get("report")
                preserved_contexts = kwargs.get("preserved_contexts", {})
                
                if not report_text:
                    return {"success": False, "error": "No report provided"}
                
                # Create new API instance for selective analysis
                from tn_staging_api import TNStagingAPI
                api = TNStagingAPI(backend=backend)
                
                # Use the new selective preservation method
                result = api.analyze_with_selective_preservation_sync(report_text, preserved_contexts)
                
                # Store API instance for potential continuation
                if result.get("success") and result.get("session_id"):
                    session_id = result["session_id"]
                    st.session_state.api_instances[session_id] = api
                
                return result
            
            else:
                return {"success": False, "error": f"Unknown command: {command}"}
                
        except Exception as e:
            return {
                "success": False,
                "error": f"API call failed: {str(e)}",
                "command": command
            }

def initialize_session_state():
    """Initialize session state variables."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "backend" not in st.session_state:
        st.session_state.backend = "ollama"
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    if "pending_analysis" not in st.session_state:
        st.session_state.pending_analysis = None
    if "pending_query_response" not in st.session_state:
        st.session_state.pending_query_response = None

def add_chat_message(role: str, content: str, metadata: Dict[str, Any] = None):
    """Add a message to chat history.
    
    Args:
        role: Message role ("user", "assistant", "system")
        content: Message content
        metadata: Optional metadata
    """
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "metadata": metadata or {}
    }
    st.session_state.chat_history.append(message)

def display_chat_history():
    """Display the chat history."""
    for msg in st.session_state.chat_history:
        role = msg["role"]
        content = msg["content"]
        timestamp = msg["timestamp"]
        
        if role == "user":
            with st.chat_message("user"):
                st.markdown(f"**Report** · {timestamp}")
                if msg["metadata"].get("type") == "query_response":
                    st.markdown("**Response to question:**")
                    st.markdown(content)
                else:
                    with st.expander("Show full report", expanded=False):
                        st.text(content)
                    
        elif role == "assistant":
            with st.chat_message("assistant"):
                st.markdown(f"**Analysis** · {timestamp}")
                if isinstance(content, dict):
                    if content.get("success"):
                        # Check if this is a query response
                        if content.get("query_needed"):
                            st.warning("**Additional Information Needed**")
                            st.markdown("**Preliminary Results:**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("T Stage", content.get("t_stage", "Unknown"))
                            with col2:
                                st.metric("N Stage", content.get("n_stage", "Unknown"))
                            
                            st.markdown("**Question:**")
                            st.info(content.get("query_question", "No question available"))
                            
                            st.info("💡 **Please use the input area on the right to respond**")
                                
                        else:
                            # Normal success response
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("T Stage", content.get("t_stage", "Unknown"))
                                t_conf = content.get("t_confidence")
                                if t_conf is not None:
                                    st.metric("T Confidence", f"{t_conf:.1%}")
                            with col2:
                                st.metric("N Stage", content.get("n_stage", "Unknown"))
                                n_conf = content.get("n_confidence")
                                if n_conf is not None:
                                    st.metric("N Confidence", f"{n_conf:.1%}")
                            
                            st.markdown(f"**Combined Stage**: {content.get('tn_stage', 'Unknown')}")
                            
                            # Show final report if available
                            if content.get('final_report'):
                                with st.expander("📄 Complete Staging Report", expanded=False):
                                    st.text(content['final_report'])
                            
                            # Show rationale
                            if content.get('t_rationale'):
                                with st.expander("T Staging Rationale"):
                                    st.markdown(content['t_rationale'])
                            if content.get('n_rationale'):
                                with st.expander("N Staging Rationale"):
                                    st.markdown(content['n_rationale'])
                                    
                            # Show optimization info if available
                            if 'workflow_optimization' in content.get('metadata', {}):
                                with st.expander("🚀 Workflow Optimization"):
                                    opt_info = content['metadata']['workflow_optimization']
                                    st.json(opt_info)
                            
                            # Show context transfer info if available
                            optimization_types = ['selective_preservation', 'partial_preservation', 'full_reanalysis', 'basic_session_transfer']
                            if content.get('metadata', {}).get('optimization_used') in optimization_types:
                                with st.expander("🔄 Context Transfer Details"):
                                    transfer_info = {
                                        "approach": content['metadata'].get('approach'),
                                        "original_session_id": content['metadata'].get('original_session_id'),
                                        "preservation_decisions": content['metadata'].get('preservation_decisions', {}),
                                        "previous_context": content['metadata'].get('previous_context', {}),
                                        "limitations": content['metadata'].get('context_limitation')
                                    }
                                    st.json(transfer_info)
                                    
                            # Show metadata
                            with st.expander("Analysis Details"):
                                details = {
                                    "Backend": content.get("backend"),
                                    "Duration": f"{content.get('duration', 0):.2f}s",
                                    "Session ID": content.get("session_id")
                                }
                                st.json(details)
                                
                    else:
                        # Error response
                        st.error(f"Analysis failed: {content.get('error', 'Unknown error')}")
                        if content.get('stdout'):
                            with st.expander("Debug Output"):
                                st.text(content['stdout'])
                else:
                    st.markdown(content)
                    
        elif role == "system":
            with st.chat_message("assistant", avatar="⚙️"):
                st.markdown(content)

def main():
    """Main application."""
    initialize_session_state()
    gui = OptimizedTNStagingGUI()
    
    # Header
    st.title("🩺 TN Staging Analysis System (Optimized)")
    st.markdown("**Guideline-based cancer staging with session transfer optimization**")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Backend selection
        backend = st.selectbox(
            "Analysis Backend",
            ["ollama", "openai", "hybrid"],
            index=0 if st.session_state.backend == "ollama" else (1 if st.session_state.backend == "openai" else 2),
            help="Choose analysis backend"
        )
        st.session_state.backend = backend
        
        # Check backend status
        if st.button("🔄 Check Status"):
            with st.spinner("Checking backend..."):
                status = gui.call_api("status", backend=backend)
                
                if status.get("available"):
                    st.success(status.get("message", "Backend available"))
                else:
                    st.error(status.get("message", "Backend not available"))
                    if status.get("requirements"):
                        st.write("**Requirements:**")
                        for req in status["requirements"]:
                            st.write(f"- {req}")
        
        # System info
        if st.button("ℹ️ System Info"):
            with st.spinner("Getting system info..."):
                info = gui.call_api("info", backend=backend)
                
                if info.get("system_initialized"):
                    st.success("System initialized")
                    st.write(f"**Agents:** {', '.join(info.get('agents', []))}")
                    
                    st.write("**Vector Stores:**")
                    for vs in info.get("vector_stores", []):
                        status_icon = "✅" if vs.get("exists") else "❌"
                        st.write(f"{status_icon} {vs.get('name')}")
                else:
                    st.error("System not initialized")
        
        st.markdown("---")
        st.header("📊 Session Info")
        st.metric("Messages", len(st.session_state.chat_history))
        st.metric("Backend", backend.upper())
        
        # Show session status
        if st.session_state.current_session_id:
            st.metric("Session ID", st.session_state.current_session_id[:8] + "...")
        
        # Show pending operations
        if st.session_state.pending_analysis:
            st.warning("⏳ Analysis in progress...")
        elif st.session_state.pending_query_response:
            st.warning("⏳ Processing response...")
        
        # Check for pending queries - FIXED LOGIC
        has_pending_query = False
        if st.session_state.chat_history:
            for msg in reversed(st.session_state.chat_history):
                if (msg["role"] == "assistant" and 
                    isinstance(msg["content"], dict)):
                    
                    # Check if this message has a query
                    if msg["content"].get("query_needed"):
                        has_pending_query = True
                        break
                    
                    # If this is a successful analysis without query_needed, check if it's final
                    elif (msg["content"].get("success") and 
                          not msg["content"].get("query_needed") and 
                          msg["content"].get("tn_stage")):  # Has final TN stage
                        # This is a completed final analysis, no pending query
                        break
        
        if has_pending_query:
            st.info("💭 Waiting for your response")
        
        # Optimization info
        st.markdown("---")
        st.header("🚀 Optimizations")
        st.info("✅ Session Transfer")
        st.info("✅ Enhanced Reporting")
        st.info("✅ Structured JSON")
        
        # Debug mode toggle
        debug_mode = st.checkbox("🐛 Debug Mode", help="Show API responses and internal states")
        
        if debug_mode and st.session_state.chat_history:
            with st.expander("🔍 Latest API Response"):
                latest_assistant_msg = None
                for msg in reversed(st.session_state.chat_history):
                    if msg["role"] == "assistant":
                        latest_assistant_msg = msg
                        break
                
                if latest_assistant_msg:
                    st.json(latest_assistant_msg["content"])
                else:
                    st.write("No assistant messages yet")
        
        if st.button("🗑️ Clear History"):
            st.session_state.chat_history = []
            st.session_state.current_session_id = None
            st.session_state.pending_analysis = None
            st.session_state.pending_query_response = None
            st.rerun()
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Chat history
        st.subheader("💬 Conversation History")
        
        if st.session_state.chat_history:
            display_chat_history()
        else:
            st.info("No conversations yet. Enter a radiologic report to get started.")
    
    with col2:
        # Input area
        st.subheader("📝 New Analysis")
        
        # Check if we have a pending query - FIXED LOGIC
        has_pending_query = False
        latest_query = None
        
        if st.session_state.chat_history:
            for msg in reversed(st.session_state.chat_history):
                if (msg["role"] == "assistant" and 
                    isinstance(msg["content"], dict)):
                    
                    # Check if this message has a query
                    if msg["content"].get("query_needed"):
                        has_pending_query = True
                        latest_query = msg["content"]
                        break
                    
                    # If this is a successful analysis without query_needed, check if it's final
                    elif (msg["content"].get("success") and 
                          not msg["content"].get("query_needed") and 
                          msg["content"].get("tn_stage")):  # Has final TN stage
                        # This is a completed final analysis, no pending query
                        break
        
        if has_pending_query and latest_query:
            # Show query response interface
            st.info("💭 **Waiting for your response to continue analysis**")
            st.write(f"**Question:** {latest_query.get('query_question', 'No question available')}")
            
            # Show optimization note
            st.success("🚀 **Please add responses about question(s).**")
            
            query_response = st.text_area(
                "Your response:",
                height=150,
                placeholder="Please provide the requested information...",
                key="query_response_input"
            )
            
            can_respond = query_response.strip()
            
            if st.button("📤 Submit Response", type="primary", disabled=not can_respond):
                if query_response.strip():
                    # Store the response for processing using SESSION TRANSFER
                    st.session_state.pending_query_response = {
                        "response": query_response,
                        "session_id": latest_query.get("session_id"),
                        "backend": latest_query.get("backend", st.session_state.backend),
                        "use_transfer": True  # Session transfer approach
                    }
                    add_chat_message("user", query_response, {"type": "query_response"})
                    add_chat_message("system", "🚀 Creating enhanced report with your response...")
                    st.rerun()
            
            st.markdown("---")
            st.write("**Or start a new analysis:**")
        
        # Regular report input
        report_text = st.text_area(
            "Radiologic Report:",
            height=200 if has_pending_query else 300,
            placeholder="Paste your radiologic report here...",
            key="report_input"
        )
        
        # Analysis button
        can_analyze = report_text.strip() and not st.session_state.pending_analysis
        button_text = "🔍 Analyze Report" if not has_pending_query else "🔍 Analyze New Report"
        
        if st.button(button_text, type="primary" if not has_pending_query else "secondary", disabled=not can_analyze):
            if report_text.strip():
                # Store pending analysis
                st.session_state.pending_analysis = {
                    "report": report_text,
                    "backend": backend,
                    "type": "initial"
                }
                
                # Add user message immediately
                add_chat_message("user", report_text, {"type": "report"})
                add_chat_message("system", f"🔄 Starting analysis with {backend} backend...")
                
                # Rerun to show messages and trigger analysis
                st.rerun()
        
        # Check if we need to run initial analysis
        if (st.session_state.pending_analysis and 
            st.session_state.pending_analysis["type"] == "initial"):
            
            analysis_data = st.session_state.pending_analysis
            st.session_state.pending_analysis = None  # Clear pending
            
            # Show progress and run analysis
            with st.spinner("Processing analysis... This may take 1-5 minutes"):
                progress_bar = st.progress(0, "Initializing...")
                
                # Run analysis
                progress_bar.progress(25, "Running analysis...")
                result = gui.call_api("analyze", report=analysis_data["report"], backend=analysis_data["backend"])
                progress_bar.progress(100, "Complete!")
                
                # Clear progress
                progress_bar.empty()
            
            # Store session ID for follow-up
            if result.get("session_id"):
                st.session_state.current_session_id = result["session_id"]
            
            # Add result to chat
            add_chat_message("assistant", result)
            st.rerun()
        
        # Check if we need to process query response with SESSION CONTINUATION
        if st.session_state.pending_query_response:
            query_data = st.session_state.pending_query_response
            st.session_state.pending_query_response = None  # Clear pending
            
            # Show progress and continue analysis using SESSION TRANSFER approach
            with st.spinner("Re-analyzing with enhanced report (session transfer)..."):
                progress_bar = st.progress(0, "Processing response...")
                
                # Always use SESSION TRANSFER approach for reliability
                progress_bar.progress(30, "Extracting all contexts from previous session...")
                
                # Find the original report and previous analysis results from chat history
                original_report = None
                previous_analysis = None
                
                for msg in st.session_state.chat_history:
                    if (msg["role"] == "user" and 
                        msg["metadata"].get("type") == "report"):
                        original_report = msg["content"]
                    elif (msg["role"] == "assistant" and 
                          isinstance(msg["content"], dict) and 
                          msg["content"].get("query_needed")):
                        previous_analysis = msg["content"]
                        break
                
                if original_report and previous_analysis:
                    progress_bar.progress(50, "Creating selective context transfer report...")
                    
                    # Determine which staging results should be preserved vs re-analyzed
                    t_confidence = previous_analysis.get('t_confidence', 0.0)
                    n_confidence = previous_analysis.get('n_confidence', 0.0)
                    t_stage = previous_analysis.get('t_stage', 'TX')
                    n_stage = previous_analysis.get('n_stage', 'NX')
                    
                    # Decision logic for what to preserve
                    # TX/NX stages should NEVER be preserved regardless of confidence
                    preserve_t = t_stage not in ["TX", None] and t_confidence >= 0.7
                    preserve_n = n_stage not in ["NX", None] and n_confidence >= 0.7
                    
                    # Check for ongoing TX/NX scenarios
                    is_tx_scenario = t_stage == "TX"
                    is_nx_scenario = n_stage == "NX"
                    current_round = previous_analysis.get('round_number', 1)
                    
                    # Debug logging for preservation decisions
                    st.write(f"🔍 **Preservation Analysis (Round {current_round + 1}):**")
                    st.write(f"- T Stage: {t_stage} (confidence: {t_confidence:.1%}) → {'✅ Preserve' if preserve_t else ('🔄 Re-analyze (TX)' if is_tx_scenario else '🔄 Re-analyze')}")
                    st.write(f"- N Stage: {n_stage} (confidence: {n_confidence:.1%}) → {'✅ Preserve' if preserve_n else ('🔄 Re-analyze (NX)' if is_nx_scenario else '🔄 Re-analyze')}")
                    
                    if is_tx_scenario or is_nx_scenario:
                        st.warning(f"⚠️ **Ongoing TX/NX Resolution** - This is round {current_round + 1} of iterative staging")
                    
                    # Create selective enhancement guidance
                    staging_guidance = []
                    if preserve_t:
                        staging_guidance.append(f"PRESERVE T STAGING: {t_stage} (confidence: {t_confidence:.1%}) - high confidence result from previous analysis")
                    else:
                        staging_guidance.append(f"RE-ANALYZE T STAGING: Previous result {t_stage} (confidence: {t_confidence:.1%}) needs review with new information")
                    
                    if preserve_n:
                        staging_guidance.append(f"PRESERVE N STAGING: {n_stage} (confidence: {n_confidence:.1%}) - high confidence result from previous analysis")
                    else:
                        staging_guidance.append(f"RE-ANALYZE N STAGING: Previous result {n_stage} (confidence: {n_confidence:.1%}) needs review with new information")
                    
                    # Create a more natural enhanced report
                    enhanced_report = f"""{original_report}

ADDITIONAL CLINICAL INFORMATION PROVIDED:
{query_data["response"]}"""
                    
                    # Decide on analysis approach based on preservation logic
                    if preserve_t and preserve_n:
                        # Both can be preserved - minimal re-analysis needed
                        progress_bar.progress(70, "Preserving high-confidence results, minimal re-analysis...")
                        preserved_contexts = {
                            "body_part": previous_analysis.get('body_part'),
                            "cancer_type": previous_analysis.get('cancer_type'),
                            "t_stage": t_stage,
                            "n_stage": n_stage,
                            "t_confidence": t_confidence,
                            "n_confidence": n_confidence,
                            "t_rationale": previous_analysis.get('t_rationale'),
                            "n_rationale": previous_analysis.get('n_rationale'),
                            # Include guidelines if available from workflow metadata
                            "t_guidelines": previous_analysis.get('workflow_summary', {}).get('t_guidelines'),
                            "n_guidelines": previous_analysis.get('workflow_summary', {}).get('n_guidelines'),
                            # Pass round tracking for multi-round scenarios
                            "round_number": current_round
                        }
                        result = gui.call_api("analyze_selective",
                                            report=enhanced_report,
                                            preserved_contexts=preserved_contexts,
                                            backend=query_data["backend"])
                    else:
                        # Need full or partial re-analysis
                        if preserve_t:
                            progress_bar.progress(70, "Preserving T staging, re-analyzing N staging...")
                        elif preserve_n:
                            progress_bar.progress(70, "Preserving N staging, re-analyzing T staging...")
                        else:
                            progress_bar.progress(70, "Re-analyzing both T and N staging...")
                        
                        # Implement partial preservation - preserve what we can
                        preserved_contexts = {
                            "body_part": previous_analysis.get('body_part'),
                            "cancer_type": previous_analysis.get('cancer_type'),
                            # Include guidelines if available from workflow metadata
                            "t_guidelines": previous_analysis.get('workflow_summary', {}).get('t_guidelines'),
                            "n_guidelines": previous_analysis.get('workflow_summary', {}).get('n_guidelines'),
                            # Pass round tracking for multi-round scenarios
                            "round_number": current_round
                        }
                        
                        # Add T staging if it can be preserved
                        if preserve_t:
                            preserved_contexts.update({
                                "t_stage": t_stage,
                                "t_confidence": t_confidence,
                                "t_rationale": previous_analysis.get('t_rationale')
                            })
                        
                        # Add N staging if it can be preserved
                        if preserve_n:
                            preserved_contexts.update({
                                "n_stage": n_stage,
                                "n_confidence": n_confidence,
                                "n_rationale": previous_analysis.get('n_rationale')
                            })
                        
                        # Use selective preservation for partial scenarios too
                        result = gui.call_api("analyze_selective",
                                            report=enhanced_report,
                                            preserved_contexts=preserved_contexts,
                                            backend=query_data["backend"])
                    
                    # Add session transfer metadata
                    if result.get("success"):
                        result["metadata"] = result.get("metadata", {})
                        
                        if preserve_t and preserve_n:
                            result["metadata"]["optimization_used"] = "selective_preservation"
                            result["metadata"]["approach"] = "both_stages_preserved"
                        elif preserve_t or preserve_n:
                            result["metadata"]["optimization_used"] = "partial_preservation"
                            result["metadata"]["approach"] = f"{'t' if preserve_t else 'n'}_stage_preserved"
                        else:
                            result["metadata"]["optimization_used"] = "full_reanalysis"
                            result["metadata"]["approach"] = "both_stages_reanalyzed"
                        
                        result["metadata"]["user_response_integrated"] = True
                        result["metadata"]["original_session_id"] = query_data.get("session_id")
                        result["metadata"]["preservation_decisions"] = {
                            "t_preserved": preserve_t,
                            "n_preserved": preserve_n,
                            "t_confidence": t_confidence,
                            "n_confidence": n_confidence
                        }
                        result["metadata"]["previous_context"] = {
                            "body_part": previous_analysis.get('body_part'),
                            "cancer_type": previous_analysis.get('cancer_type'),
                            "t_stage": t_stage,
                            "n_stage": n_stage,
                            "query_question": previous_analysis.get('query_question')
                        }
                elif original_report:
                    # Fallback: only original report found, no previous analysis context
                    progress_bar.progress(50, "Creating basic enhanced report...")
                    
                    enhanced_report = f"""{original_report}

ADDITIONAL CLINICAL INFORMATION PROVIDED:
{query_data["response"]}"""
                    
                    progress_bar.progress(70, "Starting fresh analysis with basic context transfer...")
                    
                    result = gui.call_api("analyze", 
                                        report=enhanced_report,
                                        backend=query_data["backend"])
                    
                    # Add basic session transfer metadata
                    if result.get("success"):
                        result["metadata"] = result.get("metadata", {})
                        result["metadata"]["optimization_used"] = "basic_session_transfer"
                        result["metadata"]["approach"] = "fresh_session_with_basic_context"
                        result["metadata"]["user_response_integrated"] = True
                        result["metadata"]["original_session_id"] = query_data.get("session_id")
                        result["metadata"]["context_limitation"] = "previous_analysis_context_not_found"
                        
                else:
                    # Error case - no original report found
                    result = {
                        "success": False,
                        "error": "Could not find original report to enhance. Please start a new analysis.",
                        "backend": query_data["backend"]
                    }
                
                progress_bar.progress(100, "Complete!")
                progress_bar.empty()
            
            # Add result to chat
            add_chat_message("assistant", result)
            st.rerun()
        
        # Help
        st.info("💡 Enter a radiologic report above and click Analyze")
        
        # Example
        with st.expander("📋 Example Report"):
            st.code("""CT scan of the head and neck reveals a 2.3 cm mass in the right oral cavity, involving the lateral tongue. The tumor appears to extend into the floor of mouth but does not involve the mandible. Multiple enlarged lymph nodes are seen in the right cervical chain, with the largest measuring 1.8 cm in the level II region. No distant metastases are identified.""")

if __name__ == "__main__":
    main()