"""Enhanced logging configuration for TN staging system."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import json

class SessionLogger:
    """Session-based logger that creates separate log files per session."""
    
    def __init__(self, session_id: str, log_level: int = logging.INFO):
        """Initialize session logger.
        
        Args:
            session_id: Unique session identifier
            log_level: Logging level
        """
        self.session_id = session_id
        self.log_level = log_level
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Create session-specific log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"session_{session_id}_{timestamp}.log"
        self.json_log_file = self.log_dir / f"session_{session_id}_{timestamp}.jsonl"
        
        # Set up loggers
        self._setup_loggers()
        
        # Session metadata
        self.session_metadata = {
            "session_id": session_id,
            "start_time": datetime.now().isoformat(),
            "log_file": str(self.log_file),
            "json_log_file": str(self.json_log_file)
        }
        
        # Log session start
        self.log_event("session_start", self.session_metadata)
    
    def _setup_loggers(self):
        """Set up session-specific loggers."""
        # Create formatters
        detailed_formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] %(levelname)s: %(message)s'
        )
        
        console_formatter = logging.Formatter(
            '[%(levelname)s] %(name)s: %(message)s'
        )
        
        # File handler for detailed logs
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler for important messages
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(console_formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        
        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        root_logger.setLevel(self.log_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Set up specific loggers for our components
        self._setup_component_loggers()
    
    def _setup_component_loggers(self):
        """Set up loggers for specific components."""
        components = [
            "tn_staging_system",
            "workflow_orchestrator", 
            "context_manager",
            "detection_agent",
            "guideline_retrieval_agent",
            "t_staging_agent",
            "n_staging_agent",
            "query_agent",
            "report_agent",
            "openai_provider",
            "ollama_provider",
            "hybrid_provider"
        ]
        
        for component in components:
            logger = logging.getLogger(component)
            logger.setLevel(self.log_level)
    
    def log_event(self, event_type: str, data: Dict[str, Any], level: str = "info"):
        """Log a structured event to both text and JSON logs.
        
        Args:
            event_type: Type of event (e.g., 'analysis_start', 'agent_response')
            data: Event data
            level: Log level
        """
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "level": level,
            "data": data
        }
        
        # Write to JSON log
        with open(self.json_log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        # Log to text file via standard logger
        logger = logging.getLogger("session_events")
        log_message = f"[{event_type}] {json.dumps(data, separators=(',', ':'))}"
        
        if level == "debug":
            logger.debug(log_message)
        elif level == "info":
            logger.info(log_message)
        elif level == "warning":
            logger.warning(log_message)
        elif level == "error":
            logger.error(log_message)
    
    def log_analysis_start(self, report_text: str, backend: str, initial_context: Optional[Dict] = None):
        """Log analysis start event."""
        event_data = {
            "backend": backend,
            "report_length": len(report_text),
            "report_preview": report_text[:200] + "..." if len(report_text) > 200 else report_text
        }
        
        if initial_context:
            event_data["initial_context"] = self._summarize_context(initial_context)
            
        self.log_event("analysis_start", event_data)
    
    def log_agent_execution(self, agent_name: str, status: str, duration: float, 
                          input_data: Optional[Dict] = None, output_data: Optional[Dict] = None,
                          error: Optional[str] = None, context_before: Optional[Dict] = None,
                          context_after: Optional[Dict] = None):
        """Log agent execution details with context."""
        event_data = {
            "agent": agent_name,
            "status": status,
            "duration_seconds": round(duration, 3),
            "input_summary": self._summarize_data(input_data) if input_data else None,
            "output_summary": self._summarize_data(output_data) if output_data else None,
            "error": error
        }
        
        # Add context information if provided
        if context_before:
            event_data["context_before"] = self._summarize_context(context_before)
        if context_after:
            event_data["context_after"] = self._summarize_context(context_after)
            
        self.log_event("agent_execution", event_data, level="error" if error else "info")
    
    def log_user_interaction(self, interaction_type: str, data: Dict[str, Any]):
        """Log user interactions (GUI or CLI)."""
        self.log_event("user_interaction", {
            "type": interaction_type,
            **data
        })
    
    def log_analysis_complete(self, results: Dict[str, Any], duration: float):
        """Log analysis completion."""
        self.log_event("analysis_complete", {
            "success": results.get("success", False),
            "tn_stage": results.get("tn_stage", "unknown"),
            "t_confidence": results.get("t_confidence"),
            "n_confidence": results.get("n_confidence"),
            "duration_seconds": round(duration, 3),
            "backend": results.get("backend"),
            "needs_query": results.get("query_generated") is not None
        })
    
    def log_error(self, error_type: str, error_message: str, context: Optional[Dict] = None):
        """Log errors with context."""
        self.log_event("error", {
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {}
        }, level="error")
    
    def _summarize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize data for logging (avoid huge logs)."""
        if not data:
            return {}
        
        summary = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 100:
                summary[key] = value[:100] + "..."
            elif isinstance(value, dict):
                summary[key] = {k: f"<{type(v).__name__}>" for k, v in value.items()}
            elif isinstance(value, list):
                summary[key] = f"<list of {len(value)} items>"
            else:
                summary[key] = value
        
        return summary
    
    def _summarize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize agent context for logging."""
        if not context:
            return {}
            
        summary = {}
        
        # Key context fields to track
        key_fields = [
            "context_R", "context_B", "context_GT", "context_GN", 
            "context_T", "context_N", "context_CT", "context_CN",
            "context_RationaleT", "context_RationaleN", "context_Q", "context_RR"
        ]
        
        for field in key_fields:
            if field in context:
                value = context[field]
                if isinstance(value, str):
                    if len(value) > 200:
                        summary[field] = value[:200] + "..."
                    else:
                        summary[field] = value
                elif isinstance(value, dict):
                    summary[field] = {k: str(v)[:50] + "..." if len(str(v)) > 50 else v 
                                    for k, v in value.items()}
                else:
                    summary[field] = value
                    
        # Add metadata if present
        if "metadata" in context:
            summary["metadata"] = self._summarize_data(context["metadata"])
            
        return summary
    
    def finalize_session(self, summary: Optional[Dict[str, Any]] = None):
        """Finalize session logging."""
        end_time = datetime.now()
        
        # Update session metadata
        self.session_metadata.update({
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - datetime.fromisoformat(self.session_metadata["start_time"])).total_seconds()
        })
        
        if summary:
            self.session_metadata["session_summary"] = summary
        
        self.log_event("session_end", self.session_metadata)
        
        # Write session summary to separate file
        summary_file = self.log_dir / f"session_{self.session_id}_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(self.session_metadata, f, indent=2)
    
    def get_session_logs(self) -> Dict[str, Any]:
        """Get session logs for display."""
        logs = []
        
        if self.json_log_file.exists():
            with open(self.json_log_file, 'r') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        continue
        
        return {
            "session_id": self.session_id,
            "log_file": str(self.log_file),
            "json_log_file": str(self.json_log_file),
            "logs": logs,
            "metadata": self.session_metadata
        }

def setup_logging(session_id: str, debug: bool = False) -> SessionLogger:
    """Set up logging for a session.
    
    Args:
        session_id: Session identifier
        debug: Enable debug logging
        
    Returns:
        SessionLogger instance
    """
    log_level = logging.DEBUG if debug else logging.INFO
    return SessionLogger(session_id, log_level)

def get_available_sessions() -> List[Dict[str, Any]]:
    """Get list of available log sessions.
    
    Returns:
        List of session summaries
    """
    log_dir = Path("logs")
    if not log_dir.exists():
        return []
    
    sessions = []
    for summary_file in log_dir.glob("session_*_summary.json"):
        try:
            with open(summary_file, 'r') as f:
                session_data = json.load(f)
                sessions.append(session_data)
        except (json.JSONDecodeError, FileNotFoundError):
            continue
    
    # Sort by start time (newest first)
    sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    return sessions

def cleanup_old_logs(days: int = 30):
    """Clean up log files older than specified days.
    
    Args:
        days: Number of days to keep logs
    """
    log_dir = Path("logs")
    if not log_dir.exists():
        return
    
    import time
    cutoff_time = time.time() - (days * 24 * 60 * 60)
    
    for log_file in log_dir.glob("session_*"):
        if log_file.stat().st_mtime < cutoff_time:
            log_file.unlink()
            print(f"Deleted old log file: {log_file}")