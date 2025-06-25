"""Context manager for handling agent contexts and workflow state."""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import asyncio

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agents.base import AgentContext, AgentMessage, AgentStatus

class ContextManager:
    """Manages context flow between agents and persists state."""
    
    def __init__(self, session_id: Optional[str] = None):
        """Initialize context manager.
        
        Args:
            session_id: Unique session identifier
        """
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.context = AgentContext()
        self.message_history: List[AgentMessage] = []
        self.logger = logging.getLogger("context_manager")
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up logging for context manager."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] [ContextManager] %(levelname)s: %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def update_context(self, message: AgentMessage) -> None:
        """Update context from agent message.
        
        Args:
            message: Agent message with updates
        """
        self.message_history.append(message)
        self.context.update_from_message(message)
        self.logger.info(f"Context updated by agent: {message.agent_id}")
    
    def get_context(self) -> AgentContext:
        """Get current context.
        
        Returns:
            Current agent context
        """
        return self.context
    
    def set_initial_report(self, report: str) -> None:
        """Set the initial radiologic report.
        
        Args:
            report: Radiologic report text
        """
        self.context.context_R = report
        self.context.metadata["session_id"] = self.session_id
        self.context.metadata["start_time"] = datetime.now().isoformat()
    
    def get_message_history(self) -> List[AgentMessage]:
        """Get message history.
        
        Returns:
            List of all agent messages
        """
        return self.message_history
    
    def get_last_error(self) -> Optional[str]:
        """Get the last error from message history.
        
        Returns:
            Last error message if any
        """
        for message in reversed(self.message_history):
            if message.status == AgentStatus.FAILED:
                return message.error
        return None
    
    def needs_query(self) -> bool:
        """Check if system needs to query user for more information.
        
        Returns:
            True if query is needed
        """
        # Need query if T or N staging has low confidence or resulted in TX/NX
        t_needs_query = (
            self.context.context_T in ["TX", None] or 
            (self.context.context_CT is not None and self.context.context_CT < 0.7)
        )
        n_needs_query = (
            self.context.context_N in ["NX", None] or 
            (self.context.context_CN is not None and self.context.context_CN < 0.7)
        )
        return t_needs_query or n_needs_query
    
    def add_user_response(self, response: str) -> None:
        """Add user response to query.
        
        Args:
            response: User's response to query
        """
        self.context.context_RR = response
        self.context.metadata["user_response_time"] = datetime.now().isoformat()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current context state.
        
        Returns:
            Dictionary with context summary
        """
        return {
            "session_id": self.session_id,
            "body_part": self.context.context_B.get("body_part") if self.context.context_B else None,
            "cancer_type": self.context.context_B.get("cancer_type") if self.context.context_B else None,
            "t_stage": self.context.context_T,
            "n_stage": self.context.context_N,
            "t_confidence": self.context.context_CT,
            "n_confidence": self.context.context_CN,
            "final_report": self.context.final_report,
            "messages_processed": len(self.message_history),
            "has_errors": any(m.status == AgentStatus.FAILED for m in self.message_history),
            "needs_query": self.needs_query()
        }
    
    def save_session(self, filepath: Optional[Path] = None) -> Path:
        """Save session to file.
        
        Args:
            filepath: Path to save file (optional)
            
        Returns:
            Path where session was saved
        """
        if filepath is None:
            filepath = Path(f"sessions/{self.session_id}.json")
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        session_data = {
            "session_id": self.session_id,
            "context": self.context.to_dict(),
            "message_history": [
                {
                    "agent_id": m.agent_id,
                    "timestamp": m.timestamp.isoformat(),
                    "status": m.status.value,
                    "data": m.data,
                    "error": m.error,
                    "metadata": m.metadata
                }
                for m in self.message_history
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        self.logger.info(f"Session saved to: {filepath}")
        return filepath
    
    @classmethod
    def load_session(cls, filepath: Path) -> "ContextManager":
        """Load session from file.
        
        Args:
            filepath: Path to session file
            
        Returns:
            ContextManager instance with loaded session
        """
        with open(filepath, 'r') as f:
            session_data = json.load(f)
        
        manager = cls(session_id=session_data["session_id"])
        
        # Restore context
        context_data = session_data["context"]
        manager.context = AgentContext(**context_data)
        
        # Restore message history
        for msg_data in session_data["message_history"]:
            message = AgentMessage(
                agent_id=msg_data["agent_id"],
                timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                status=AgentStatus(msg_data["status"]),
                data=msg_data["data"],
                error=msg_data["error"],
                metadata=msg_data["metadata"]
            )
            manager.message_history.append(message)
        
        return manager

class WorkflowOrchestrator:
    """Orchestrates the workflow of agents."""
    
    def __init__(self, agents: Dict[str, Any], context_manager: ContextManager):
        """Initialize workflow orchestrator.
        
        Args:
            agents: Dictionary of agent instances
            context_manager: Context manager instance
        """
        self.agents = agents
        self.context_manager = context_manager
        self.logger = logging.getLogger("workflow_orchestrator")
    
    async def run_workflow(self, report: str) -> Dict[str, Any]:
        """Run the complete workflow.
        
        Args:
            report: Initial radiologic report
            
        Returns:
            Final results dictionary
        """
        self.context_manager.set_initial_report(report)
        
        # Step 1: Detect body part and cancer type
        await self._run_agent("detect")
        
        # Step 2: Retrieve guidelines
        await self._run_agent("retrieve_guideline")
        
        # Step 3: Run T and N staging in parallel
        await asyncio.gather(
            self._run_agent("staging_t"),
            self._run_agent("staging_n")
        )
        
        # Step 4: Check if query is needed
        if self.context_manager.needs_query():
            await self._run_agent("query")
            # Return here to pause workflow for user input
            # The GUI/API should detect this state and prompt user
            # Workflow resumes when user provides response
            if self.context_manager.context.context_Q and not self.context_manager.context.context_RR:
                # Query generated but no user response yet - pause workflow
                summary = self.context_manager.get_summary()
                summary["workflow_status"] = "awaiting_user_response"
                summary["query_question"] = self.context_manager.context.context_Q
                return summary
        
        # Step 5: Generate report (only if no query pending)
        await self._run_agent("report")
        
        return self.context_manager.get_summary()
    
    async def continue_workflow_with_response(self, user_response: str) -> Dict[str, Any]:
        """Continue workflow after user provides response to query.
        
        Args:
            user_response: User's response to the query
            
        Returns:
            Final results dictionary
        """
        # Add user response to context
        self.context_manager.add_user_response(user_response)
        
        # Re-run staging agents with additional information
        await asyncio.gather(
            self._run_agent("staging_t"),
            self._run_agent("staging_n")
        )
        
        # Generate final report
        await self._run_agent("report")
        
        return self.context_manager.get_summary()
    
    async def _run_agent(self, agent_name: str) -> None:
        """Run a specific agent.
        
        Args:
            agent_name: Name of the agent to run
        """
        if agent_name not in self.agents:
            self.logger.error(f"Agent not found: {agent_name}")
            return
        
        agent = self.agents[agent_name]
        context_before = self.context_manager.get_context()
        
        self.logger.info(f"Running agent: {agent_name}")
        
        # Capture context before execution
        context_dict_before = context_before.to_dict() if hasattr(context_before, 'to_dict') else {}
        
        # Time the execution
        import time
        start_time = time.time()
        
        try:
            message = await agent.execute(context_before)
            duration = time.time() - start_time
            
            # Capture context after execution
            self.context_manager.update_context(message)
            context_after = self.context_manager.get_context()
            context_dict_after = context_after.to_dict() if hasattr(context_after, 'to_dict') else {}
            
            # Log detailed execution info if session logger is available
            if hasattr(self.context_manager, 'session_logger') and self.context_manager.session_logger:
                self.context_manager.session_logger.log_agent_execution(
                    agent_name=agent_name,
                    status=message.status.value,
                    duration=duration,
                    input_data=message.metadata if hasattr(message, 'metadata') else None,
                    output_data=message.data if hasattr(message, 'data') else None,
                    error=message.error if hasattr(message, 'error') else None,
                    context_before=context_dict_before,
                    context_after=context_dict_after
                )
            
            if message.status == AgentStatus.FAILED:
                self.logger.error(f"Agent {agent_name} failed: {message.error}")
            else:
                self.logger.info(f"Agent {agent_name} completed successfully in {duration:.2f}s")
                
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Agent {agent_name} execution failed: {str(e)}")
            
            # Log the error
            if hasattr(self.context_manager, 'session_logger') and self.context_manager.session_logger:
                self.context_manager.session_logger.log_agent_execution(
                    agent_name=agent_name,
                    status="error",
                    duration=duration,
                    error=str(e),
                    context_before=context_dict_before
                )
            raise