"""Base agent class for the TN staging system."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field
import logging
from datetime import datetime
import traceback

class AgentStatus(Enum):
    """Agent execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

class AgentMessage(BaseModel):
    """Message format for inter-agent communication."""
    agent_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    status: AgentStatus
    data: Dict[str, Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentContext(BaseModel):
    """Context passed between agents."""
    # Original inputs
    context_R: Optional[str] = None  # Radiologic report
    
    # Detection outputs
    context_B: Optional[Dict[str, str]] = None  # Body part and cancer type
    
    # Guideline outputs
    context_GT: Optional[str] = None  # T staging guidelines
    context_GN: Optional[str] = None  # N staging guidelines
    
    # Staging outputs
    context_T: Optional[str] = None  # T staging result
    context_N: Optional[str] = None  # N staging result
    context_CT: Optional[float] = None  # T staging confidence
    context_CN: Optional[float] = None  # N staging confidence
    context_RationaleT: Optional[str] = None  # T staging rationale
    context_RationaleN: Optional[str] = None  # N staging rationale
    
    # Query and response
    context_Q: Optional[str] = None  # Query for additional info
    context_RR: Optional[str] = None  # User response to query
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return self.model_dump(exclude_none=True)
    
    def update_from_message(self, message: AgentMessage) -> None:
        """Update context from agent message."""
        if message.status == AgentStatus.SUCCESS:
            for key, value in message.data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.metadata.update(message.metadata)

class BaseAgent(ABC):
    """Base class for all agents in the TN staging system."""
    
    def __init__(self, agent_id: str, llm_provider: Optional[Any] = None):
        """Initialize the agent.
        
        Args:
            agent_id: Unique identifier for the agent
            llm_provider: LLM provider instance (OpenAI/Ollama)
        """
        self.agent_id = agent_id
        self.llm_provider = llm_provider
        self.logger = logging.getLogger(f"agent.{agent_id}")
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up agent-specific logging."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            f'[%(asctime)s] [{self.agent_id}] %(levelname)s: %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    @abstractmethod
    async def process(self, context: AgentContext) -> AgentMessage:
        """Process the input and return a message.
        
        Args:
            context: Current agent context
            
        Returns:
            AgentMessage with results or error
        """
        pass
    
    @abstractmethod
    def validate_input(self, context: AgentContext) -> bool:
        """Validate that the agent has required inputs.
        
        Args:
            context: Current agent context
            
        Returns:
            True if inputs are valid, False otherwise
        """
        pass
    
    async def execute(self, context: AgentContext) -> AgentMessage:
        """Execute the agent with error handling.
        
        Args:
            context: Current agent context
            
        Returns:
            AgentMessage with results or error
        """
        try:
            self.logger.info(f"Starting execution")
            
            # Validate inputs
            if not self.validate_input(context):
                return AgentMessage(
                    agent_id=self.agent_id,
                    status=AgentStatus.FAILED,
                    data={},
                    error="Invalid input for agent"
                )
            
            # Process
            message = await self.process(context)
            
            self.logger.info(f"Completed execution with status: {message.status}")
            return message
            
        except Exception as e:
            self.logger.error(f"Error during execution: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.FAILED,
                data={},
                error=str(e),
                metadata={"traceback": traceback.format_exc()}
            )
    
    def get_status_message(self, action: str) -> str:
        """Get a natural language status message.
        
        Args:
            action: Current action being performed
            
        Returns:
            Natural language status message
        """
        status_templates = {
            "detect": "Analyzing the radiologic report to identify body part and cancer type...",
            "retrieve": "Retrieving relevant staging guidelines...",
            "stage_t": "Evaluating tumor characteristics for T staging...",
            "stage_n": "Assessing lymph node involvement for N staging...",
            "query": "Preparing questions to gather additional information...",
            "report": "Generating comprehensive staging report..."
        }
        return status_templates.get(action, f"Processing {action}...")

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    async def embed(self, text: str) -> list:
        """Generate embeddings for text."""
        pass