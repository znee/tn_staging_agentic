"""Context management module."""

from .context_manager_optimized import OptimizedContextManager, OptimizedWorkflowOrchestrator

# For backward compatibility (if needed)
ContextManager = OptimizedContextManager
WorkflowOrchestrator = OptimizedWorkflowOrchestrator

__all__ = ["OptimizedContextManager", "OptimizedWorkflowOrchestrator", "ContextManager", "WorkflowOrchestrator"]