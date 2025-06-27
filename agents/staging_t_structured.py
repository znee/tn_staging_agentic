"""T staging agent with structured JSON output support."""

import re
from typing import Dict, Tuple, Optional, List, Any
from .base import BaseAgent, AgentContext, AgentMessage, AgentStatus
from config.llm_providers_structured import TStagingResponse

class StructuredTStagingAgent(BaseAgent):
    """Agent that determines T staging using structured outputs."""
    
    def __init__(self, llm_provider):
        """Initialize T staging agent with structured output support.
        
        Args:
            llm_provider: Structured LLM provider instance
        """
        super().__init__("t_staging_agent", llm_provider)
        
    def validate_input(self, context: AgentContext) -> bool:
        """Validate required inputs are present.
        
        Args:
            context: Current agent context
            
        Returns:
            True if all required inputs are present
        """
        return (
            context.context_R is not None and
            context.context_B is not None and
            context.context_GT is not None
        )
    
    async def process(self, context: AgentContext) -> AgentMessage:
        """Determine T staging from radiologic report.
        
        Args:
            context: Current agent context
            
        Returns:
            AgentMessage with T staging results
        """
        report = context.context_R
        guidelines = context.context_GT
        body_part = context.context_B["body_part"]
        cancer_type = context.context_B["cancer_type"]
        
        # Use structured output for T staging
        result = await self._determine_t_stage_structured(
            report, guidelines, body_part, cancer_type
        )
        
        return AgentMessage(
            agent_id=self.agent_id,
            status=AgentStatus.SUCCESS,
            data={
                "context_T": result["t_stage"],
                "context_CT": result["confidence"],
                "context_RationaleT": result["rationale"]
            },
            metadata={
                "tumor_info": result["extracted_info"],
                "body_part": body_part,
                "cancer_type": cancer_type
            }
        )
    
    async def _determine_t_stage_structured(
        self,
        report: str,
        guidelines: str,
        body_part: str,
        cancer_type: str
    ) -> Dict[str, Any]:
        """Determine T stage using structured output.
        
        Args:
            report: Full radiologic report
            guidelines: T staging guidelines
            body_part: Body part/organ
            cancer_type: Cancer type
            
        Returns:
            Dictionary with staging results
        """
        prompt = f"""You are a medical staging expert analyzing a radiologic report.

AJCC GUIDELINES:
{guidelines}

CASE INFORMATION:
- Body part: {body_part}
- Cancer type: {cancer_type}

RADIOLOGIC REPORT:
{report}

Analyze the report against AJCC guidelines and determine the T stage classification.

REQUIREMENTS:
- Use TX only when tumor information is truly insufficient
- Reference specific AJCC criteria in your rationale
- Extract all relevant tumor measurements and invasion details
- Be conservative in your assessment"""

        try:
            # Use structured generation if available
            if hasattr(self.llm_provider, 'generate_structured'):
                result = await self.llm_provider.generate_structured(
                    prompt,
                    TStagingResponse,
                    temperature=0.1
                )
                return result
            else:
                # Fallback to standard generation
                self.logger.warning("Structured generation not available, using standard method")
                return await self._fallback_standard_generation(prompt)
                
        except Exception as e:
            self.logger.error(f"Failed to determine T stage: {str(e)}")
            return self._fallback_t_staging()
    
    async def _fallback_standard_generation(self, prompt: str) -> Dict[str, Any]:
        """Fallback to standard generation when structured output unavailable.
        
        Args:
            prompt: Generation prompt
            
        Returns:
            Dictionary with staging results
        """
        # Add explicit JSON format request to prompt
        json_prompt = prompt + """

Respond with a JSON object in this exact format:
{
    "t_stage": "T1",
    "confidence": 0.85,
    "rationale": "Based on AJCC guidelines: [specific criteria and findings]",
    "extracted_info": {
        "tumor_size": "dimension from report",
        "largest_dimension": 5.4,
        "invasions": ["anatomical structures"],
        "extensions": ["specific locations"],
        "multiple_tumors": false,
        "key_findings": ["relevant findings"]
    }
}"""
        
        response = await self.llm_provider.generate(json_prompt)
        
        # Parse JSON from response
        import json
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            # Validate with Pydantic model
            validated = TStagingResponse(**data)
            return validated.model_dump()
        else:
            raise ValueError("Could not extract valid JSON from response")
    
    def _fallback_t_staging(self) -> Dict[str, Any]:
        """Conservative fallback T staging.
        
        Returns:
            Dictionary with TX staging
        """
        return {
            "t_stage": "TX",
            "confidence": 0.3,
            "rationale": "Unable to determine T stage from available information",
            "extracted_info": {
                "tumor_size": None,
                "largest_dimension": None,
                "invasions": [],
                "extensions": [],
                "multiple_tumors": False,
                "key_findings": []
            }
        }