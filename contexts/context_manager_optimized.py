"""Optimized context manager with selective re-staging based on confidence."""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from agents.base import AgentStatus, AgentMessage


@dataclass
class AgentContext:
    """Container for all agent context variables."""
    # Original report
    context_R: Optional[str] = None
    
    # Body part and cancer detection
    context_B: Optional[Dict[str, str]] = None
    
    # Guidelines
    context_GT: Optional[str] = None  # T staging guidelines
    context_GN: Optional[str] = None  # N staging guidelines
    
    # T staging results
    context_T: Optional[str] = None
    context_CT: Optional[float] = None  # Confidence
    context_RationaleT: Optional[str] = None
    
    # N staging results  
    context_N: Optional[str] = None
    context_CN: Optional[float] = None  # Confidence
    context_RationaleN: Optional[str] = None
    
    # Query and response
    context_Q: Optional[str] = None  # Query for user
    context_RR: Optional[str] = None  # User response
    
    # Final report
    final_report: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return asdict(self)


class OptimizedContextManager:
    """Manages context state across agent interactions."""
    
    def __init__(self, session_id: Optional[str] = None):
        """Initialize context manager.
        
        Args:
            session_id: Optional session ID for compatibility
        """
        self.context = AgentContext()
        self.logger = logging.getLogger("context_manager")
        self.session_logger = None
        self.session_id = session_id
        
        # Add session ID to context metadata
        if session_id:
            self.context.metadata["session_id"] = session_id
        
    def get_context(self) -> AgentContext:
        """Get current context state.
        
        Returns:
            Current agent context
        """
        return self.context
    
    def update_context(self, message: AgentMessage) -> None:
        """Update context from agent message.
        
        Args:
            message: Agent message with updates
        """
        if message.status == AgentStatus.SUCCESS and message.data:
            for key, value in message.data.items():
                if hasattr(self.context, key):
                    setattr(self.context, key, value)
                    
            # Store metadata if provided
            if message.metadata:
                self.context.metadata.update(message.metadata)
    
    def add_user_response(self, response: str) -> None:
        """Add user response to context.
        
        Args:
            response: User's response to query
        """
        self.context.context_RR = response
        self.logger.info(f"Added user response: {len(response)} characters")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of context state.
        
        Returns:
            Summary dictionary
        """
        summary = {
            "body_part": self.context.context_B.get("body_part") if self.context.context_B else None,
            "cancer_type": self.context.context_B.get("cancer_type") if self.context.context_B else None,
            "t_stage": self.context.context_T,
            "n_stage": self.context.context_N,
            "t_confidence": self.context.context_CT,
            "n_confidence": self.context.context_CN,
            "t_rationale": self.context.context_RationaleT,
            "n_rationale": self.context.context_RationaleN,
            "query_pending": self.context.context_Q is not None and self.context.context_RR is None,
            "query_question": self.context.context_Q,
            "user_response": self.context.context_RR,
            "final_report": self.context.final_report,
            "metadata": self.context.metadata
        }
        
        return summary
    
    def needs_query(self) -> bool:
        """Check if a query is currently pending.
        
        Returns:
            True if query is pending
        """
        return self.context.context_Q is not None and self.context.context_RR is None
    
    def save_session(self, filepath: Optional[str] = None) -> str:
        """Save the current session to disk.
        
        Args:
            filepath: Optional path to save to
            
        Returns:
            Path where session was saved
        """
        import json
        from datetime import datetime
        
        if filepath is None:
            # Create default filename with session ID and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"session_{self.session_id}_{timestamp}.json"
            filepath = f"sessions/{filename}"
        
        # Ensure sessions directory exists
        sessions_dir = Path("sessions")
        sessions_dir.mkdir(exist_ok=True)
        
        # Prepare session data
        session_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "context": self.context.to_dict(),
            "summary": self.get_summary()
        }
        
        # Save to file
        session_path = Path(filepath)
        with open(session_path, 'w') as f:
            json.dump(session_data, f, indent=2, default=str)
        
        self.logger.info(f"Session saved to {session_path}")
        return str(session_path)
    
    @classmethod
    def load_session(cls, filepath: str, session_id: Optional[str] = None) -> "OptimizedContextManager":
        """Load a session from disk.
        
        Args:
            filepath: Path to session file
            session_id: Optional session ID override
            
        Returns:
            OptimizedContextManager instance with loaded session
        """
        import json
        
        session_path = Path(filepath)
        if not session_path.exists():
            raise FileNotFoundError(f"Session file not found: {filepath}")
        
        # Load session data
        with open(session_path) as f:
            session_data = json.load(f)
        
        # Create context manager
        loaded_session_id = session_id or session_data.get("session_id")
        context_manager = cls(session_id=loaded_session_id)
        
        # Restore context
        context_dict = session_data.get("context", {})
        for key, value in context_dict.items():
            if hasattr(context_manager.context, key):
                setattr(context_manager.context, key, value)
        
        context_manager.logger.info(f"Session loaded from {session_path}")
        return context_manager
    
    def needs_t_restaging(self) -> bool:
        """Check if T staging needs to be re-run.
        
        Returns:
            True if T staging should be re-run
        """
        # Re-run if T staging is missing (None), TX, or confidence below threshold
        return (
            self.context.context_T is None or
            self.context.context_T == "TX" or 
            (self.context.context_CT is not None and self.context.context_CT < 0.7)
        )
    
    def needs_n_restaging(self) -> bool:
        """Check if N staging needs to be re-run.
        
        Returns:
            True if N staging should be re-run
        """
        # Re-run if N staging is missing (None), NX, or confidence below threshold
        return (
            self.context.context_N is None or
            self.context.context_N == "NX" or 
            (self.context.context_CN is not None and self.context.context_CN < 0.7)
        )


class OptimizedWorkflowOrchestrator:
    """Orchestrates the agent workflow with selective re-staging."""
    
    def __init__(self, agents: Dict[str, Any], context_manager: OptimizedContextManager):
        """Initialize workflow orchestrator.
        
        Args:
            agents: Dictionary of agent instances
            context_manager: Context manager instance
        """
        self.agents = agents
        self.context_manager = context_manager
        self.logger = logging.getLogger("workflow_orchestrator")
    
    async def run_initial_workflow(self) -> Dict[str, Any]:
        """Run the initial analysis workflow.
        
        Returns:
            Results dictionary
        """
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
        context = self.context_manager.get_context()
        
        # Query needed if low confidence or TX/NX results
        if self._needs_query(context):
            await self._run_agent("query")
            
            # Return partial results with query
            summary = self.context_manager.get_summary()
            if context.context_Q:
                summary["query_needed"] = True
                summary["query_question"] = context.context_Q
                summary["workflow_status"] = "awaiting_user_response"  # For compatibility
                return summary
        
        # Step 5: Generate report (only if no query pending)
        await self._run_agent("report")
        
        return self.context_manager.get_summary()
    
    async def continue_workflow_with_response(self, user_response: str) -> Dict[str, Any]:
        """Continue workflow after user provides response to query.
        
        This is the OPTIMIZED version that only re-runs staging agents with low confidence.
        
        Args:
            user_response: User's response to the query
            
        Returns:
            Final results dictionary
        """
        # Add user response to context
        self.context_manager.add_user_response(user_response)
        
        # Determine which staging agents need to be re-run
        tasks = []
        agents_to_rerun = []
        
        if self.context_manager.needs_t_restaging():
            tasks.append(self._run_agent("staging_t"))
            agents_to_rerun.append("T")
            self.logger.info(f"Re-running T staging (current: {self.context_manager.context.context_T}, confidence: {self.context_manager.context.context_CT})")
        else:
            self.logger.info(f"Skipping T staging re-run (current: {self.context_manager.context.context_T}, confidence: {self.context_manager.context.context_CT})")
        
        if self.context_manager.needs_n_restaging():
            tasks.append(self._run_agent("staging_n"))
            agents_to_rerun.append("N")
            self.logger.info(f"Re-running N staging (current: {self.context_manager.context.context_N}, confidence: {self.context_manager.context.context_CN})")
        else:
            self.logger.info(f"Skipping N staging re-run (current: {self.context_manager.context.context_N}, confidence: {self.context_manager.context.context_CN})")
        
        # Log optimization info
        if hasattr(self.context_manager, 'session_logger') and self.context_manager.session_logger:
            self.context_manager.session_logger.log_event("workflow_optimization", {
                "agents_rerun": agents_to_rerun,
                "t_skipped": "T" not in agents_to_rerun,
                "n_skipped": "N" not in agents_to_rerun,
                "t_confidence": self.context_manager.context.context_CT,
                "n_confidence": self.context_manager.context.context_CN,
                "t_stage": self.context_manager.context.context_T,
                "n_stage": self.context_manager.context.context_N
            })
        
        # Re-run only necessary staging agents
        if tasks:
            await asyncio.gather(*tasks)
        else:
            self.logger.info("No staging agents need to be re-run")
        
        # Check if another query is needed after re-staging
        context = self.context_manager.get_context()
        current_round = context.metadata.get("round_number", 1)
        max_rounds = 3  # Limit to prevent infinite loops
        
        if self._needs_query(context) and current_round < max_rounds:
            await self._run_agent("query")
            
            # Update round counter in context metadata
            context.metadata["round_number"] = current_round + 1
            
            # Return partial results with new query (for multiple rounds)
            summary = self.context_manager.get_summary()
            summary["query_needed"] = True
            summary["query_question"] = context.context_Q
            summary["workflow_status"] = "awaiting_user_response"
            summary["round_number"] = current_round + 1
            
            self.logger.info(f"Generated additional query (round {current_round + 1}/{max_rounds}) - staging still incomplete")
            return summary
        elif self._needs_query(context) and current_round >= max_rounds:
            self.logger.warning(f"Maximum query rounds ({max_rounds}) reached - proceeding with partial staging")
            # Continue to report generation even with TX/NX
        
        # Generate final report (no more queries needed)
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
    
    def _needs_query(self, context: AgentContext) -> bool:
        """Check if query generation is needed based on staging results.
        
        Args:
            context: Current agent context
            
        Returns:
            True if query is needed
        """
        # Check T staging confidence
        t_needs_query = (
            context.context_T == "TX" or 
            (context.context_CT is not None and context.context_CT < 0.7)
        )
        
        # Check N staging confidence
        n_needs_query = (
            context.context_N == "NX" or 
            (context.context_CN is not None and context.context_CN < 0.7)
        )
        
        return t_needs_query or n_needs_query