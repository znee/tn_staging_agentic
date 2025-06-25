#!/usr/bin/env python3
"""TN Staging GUI - Fixed Threading Issues"""

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

class TNStagingGUI:
    """Streamlit GUI that uses the core API via subprocess."""
    
    def __init__(self):
        self.api_script = Path(__file__).parent / "tn_staging_api.py"
        self.python_exe = sys.executable
    
    def call_api(self, command: str, **kwargs) -> Dict[str, Any]:
        """Call the core API via subprocess.
        
        Args:
            command: API command to run
            **kwargs: Additional arguments
            
        Returns:
            API response as dictionary
        """
        try:
            cmd = [self.python_exe, str(self.api_script), "--json"]
            
            # Add backend
            if "backend" in kwargs:
                cmd.extend(["--backend", kwargs["backend"]])
            
            # Add debug
            if kwargs.get("debug"):
                cmd.append("--debug")
            
            # Add command-specific args
            if command == "status":
                cmd.append("--status")
            elif command == "info":
                cmd.append("--info")
            elif command == "analyze":
                if "report" in kwargs:
                    # Ensure report text is properly passed
                    report_text = kwargs["report"]
                    if report_text:
                        cmd.extend(["--report", report_text])
            elif command == "continue":
                if "session_id" in kwargs and "user_response" in kwargs:
                    cmd.extend([
                        "--continue-session", kwargs["session_id"],
                        "--user-response", kwargs["user_response"]
                    ])
            
            # Run command
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=180  # 3 minute timeout
            )
            
            if result.returncode == 0:
                # Parse JSON output (skip any progress messages)
                stdout = result.stdout.strip()
                
                # Try to find JSON block in output
                json_response = None
                
                # Method 1: Look for complete JSON block from the end
                lines = stdout.split('\n')
                json_lines = []
                in_json = False
                brace_count = 0
                
                for line in reversed(lines):
                    line = line.strip()
                    if line.endswith('}') and not in_json:
                        # Start of JSON block (reading backwards)
                        in_json = True
                        json_lines.insert(0, line)
                        brace_count = line.count('}') - line.count('{')
                    elif in_json:
                        json_lines.insert(0, line)
                        brace_count += line.count('}') - line.count('{')
                        if brace_count == 0 and line.startswith('{'):
                            # Complete JSON block found
                            json_response = '\n'.join(json_lines)
                            break
                
                # Method 2: Try parsing each line that looks like JSON
                if not json_response:
                    for line in reversed(lines):
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            try:
                                json.loads(line)
                                json_response = line
                                break
                            except json.JSONDecodeError:
                                continue
                
                # Method 3: Look for JSON after "Starting analysis..." marker
                if not json_response:
                    start_marker = "Starting analysis..."
                    if start_marker in stdout:
                        after_marker = stdout.split(start_marker, 1)[1].strip()
                        try:
                            json_response = after_marker
                            json.loads(json_response)  # Validate
                        except json.JSONDecodeError:
                            pass
                
                if json_response:
                    try:
                        return json.loads(json_response)
                    except json.JSONDecodeError as e:
                        return {
                            "success": False, 
                            "error": f"JSON parsing failed: {e}", 
                            "stdout": stdout,
                            "attempted_json": json_response[:500]
                        }
                else:
                    return {"success": False, "error": "No JSON response found", "stdout": stdout}
            else:
                return {
                    "success": False, 
                    "error": result.stderr or "Command failed",
                    "stdout": result.stdout,
                    "returncode": result.returncode
                }
                
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Analysis timed out (3 minutes)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

def initialize_session_state():
    """Initialize session state variables."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "backend" not in st.session_state:
        st.session_state.backend = os.getenv("TN_STAGING_BACKEND", "ollama")
    if "pending_analysis" not in st.session_state:
        st.session_state.pending_analysis = None
    if "pending_query_response" not in st.session_state:
        st.session_state.pending_query_response = None
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None

def add_chat_message(role: str, content: str, metadata: Optional[Dict] = None):
    """Add a message to the chat history."""
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "metadata": metadata or {}
    }
    st.session_state.chat_history.append(message)

def display_chat_history():
    """Display the chat history."""
    for i, message in enumerate(st.session_state.chat_history):
        role = message["role"]
        content = message["content"]
        timestamp = message["timestamp"]
        metadata = message.get("metadata", {})
        
        if role == "user":
            with st.chat_message("user"):
                st.markdown(f"**User** · {timestamp}")
                if metadata.get("type") == "report":
                    with st.expander("📄 Radiologic Report", expanded=False):
                        st.text_area("Report Content", content, height=150, disabled=True, key=f"report_{i}")
                else:
                    st.markdown(content)
                    
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
                                if "t_confidence" in content:
                                    st.metric("T Confidence", f"{content['t_confidence']:.1%}")
                            with col2:
                                st.metric("N Stage", content.get("n_stage", "Unknown"))
                                if "n_confidence" in content:
                                    st.metric("N Confidence", f"{content['n_confidence']:.1%}")
                            
                            st.markdown(f"**Combined Stage**: {content.get('tn_stage', 'Unknown')}")
                            
                            # Show rationale
                            if content.get('t_rationale'):
                                with st.expander("T Staging Rationale"):
                                    st.markdown(content['t_rationale'])
                            if content.get('n_rationale'):
                                with st.expander("N Staging Rationale"):
                                    st.markdown(content['n_rationale'])
                                    
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
    gui = TNStagingGUI()
    
    # Header
    st.title("🩺 TN Staging Analysis System")
    st.markdown("**Guideline-based cancer staging with conversation history**")
    
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
        
        # Check for pending queries
        has_pending_query = False
        if st.session_state.chat_history:
            for msg in reversed(st.session_state.chat_history):
                if (msg["role"] == "assistant" and 
                    isinstance(msg["content"], dict) and 
                    msg["content"].get("query_needed")):
                    has_pending_query = True
                    break
                elif (msg["role"] == "assistant" and 
                      isinstance(msg["content"], dict) and 
                      not msg["content"].get("query_needed")):
                    break
        
        if has_pending_query:
            st.info("💭 Waiting for your response")
        
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
        
        # Check if we have a pending query
        has_pending_query = False
        latest_query = None
        
        if st.session_state.chat_history:
            for msg in reversed(st.session_state.chat_history):
                if (msg["role"] == "assistant" and 
                    isinstance(msg["content"], dict) and 
                    msg["content"].get("query_needed")):
                    has_pending_query = True
                    latest_query = msg["content"]
                    break
                elif (msg["role"] == "assistant" and 
                      isinstance(msg["content"], dict) and 
                      not msg["content"].get("query_needed")):
                    # Found a completed analysis, no pending query
                    break
        
        if has_pending_query and latest_query:
            # Show query response interface
            st.info("💭 **Waiting for your response to continue analysis**")
            st.write(f"**Question:** {latest_query.get('query_question', 'No question available')}")
            
            query_response = st.text_area(
                "Your response:",
                height=150,
                placeholder="Please provide the requested information...",
                key="query_response_input"
            )
            
            can_respond = query_response.strip()
            
            if st.button("📤 Submit Response", type="primary", disabled=not can_respond):
                if query_response.strip():
                    # Store the response for processing
                    st.session_state.pending_query_response = {
                        "response": query_response,
                        "session_id": latest_query.get("session_id"),
                        "backend": latest_query.get("backend", st.session_state.backend)
                    }
                    add_chat_message("user", query_response, {"type": "query_response"})
                    add_chat_message("system", "🔄 Continuing analysis with your response...")
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
            with st.spinner("Processing analysis... This may take 1-3 minutes"):
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
        
        # Check if we need to process query response
        if st.session_state.pending_query_response:
            query_data = st.session_state.pending_query_response
            st.session_state.pending_query_response = None  # Clear pending
            
            # Show progress and continue analysis
            with st.spinner("Re-analyzing with additional information..."):
                progress_bar = st.progress(0, "Processing response...")
                
                # Find the original report from chat history
                original_report = None
                for msg in st.session_state.chat_history:
                    if (msg["role"] == "user" and 
                        msg["metadata"].get("type") == "report"):
                        original_report = msg["content"]
                        break
                
                if original_report:
                    # Create enhanced report with user response
                    enhanced_report = f"""{original_report}

ADDITIONAL INFORMATION PROVIDED BY USER:
{query_data["response"]}"""
                    
                    progress_bar.progress(50, "Re-analyzing with enhanced report...")
                    
                    # Run new analysis with enhanced report
                    result = gui.call_api("analyze", 
                                        report=enhanced_report,
                                        backend=query_data["backend"])
                else:
                    # Fallback if original report not found
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