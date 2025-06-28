"""T staging agent for tumor classification."""

import re
from typing import Dict, Tuple, Optional, List, Any
from .base import BaseAgent, AgentContext, AgentMessage, AgentStatus
from config.llm_providers_structured import TStagingResponse

class TStagingAgent(BaseAgent):
    """Agent that determines T staging based on radiologic findings."""
    
    def __init__(self, llm_provider):
        """Initialize T staging agent.
        
        Args:
            llm_provider: LLM provider instance
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
        
        # Determine T stage directly from report and guidelines
        t_stage, confidence, rationale, extracted_info = await self._determine_t_stage(
            report, guidelines, body_part, cancer_type
        )
        
        return AgentMessage(
            agent_id=self.agent_id,
            status=AgentStatus.SUCCESS,
            data={
                "context_T": t_stage,
                "context_CT": confidence,
                "context_RationaleT": rationale
            },
            metadata={
                "tumor_info": extracted_info,
                "body_part": body_part,
                "cancer_type": cancer_type
            }
        )
    
    
    async def _determine_t_stage(
        self,
        report: str,
        guidelines: str,
        body_part: str,
        cancer_type: str
    ) -> Tuple[str, float, str, Dict]:
        """Determine T stage using structured output when available."""
        # Try structured output first for better performance
        if hasattr(self.llm_provider, 'generate_structured'):
            try:
                result = await self._determine_t_stage_structured(
                    report, guidelines, body_part, cancer_type
                )
                return (
                    result["t_stage"],
                    result["confidence"],
                    result["rationale"],
                    result["extracted_info"]
                )
            except Exception as e:
                self.logger.warning(f"Structured output failed, falling back to manual parsing: {str(e)}")
        
        # Fallback to manual JSON parsing
        return await self._determine_t_stage_manual(report, guidelines, body_part, cancer_type)
    
    async def _determine_t_stage_structured(
        self,
        report: str,
        guidelines: str,
        body_part: str,
        cancer_type: str
    ) -> Dict[str, Any]:
        """Determine T stage using structured JSON output (preferred method)."""
        prompt = f"""You are a medical staging expert analyzing a radiologic report using AJCC guidelines.

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
- Extract all relevant tumor measurements with units (e.g., "3.2 cm")
- Extract invasion details and anatomical extensions
- Be conservative in your assessment"""
        
        result = await self.llm_provider.generate_structured(
            prompt,
            TStagingResponse,
            temperature=0.1
        )
        return result
    
    async def _determine_t_stage_manual(
        self,
        report: str,
        guidelines: str,
        body_part: str,
        cancer_type: str
    ) -> Tuple[str, float, str, Dict]:
        """Determine T stage using manual JSON parsing (fallback method).
        
        Args:
            report: Full radiologic report
            guidelines: T staging guidelines
            body_part: Body part/organ
            cancer_type: Cancer type
            
        Returns:
            Tuple of (t_stage, confidence, rationale, extracted_info)
        """
        prompt = f"""INSTRUCTIONS: You are a medical staging expert. Your task is to output ONLY a JSON object with T staging analysis. NO THINKING, NO EXPLANATIONS, NO ADDITIONAL TEXT.

AJCC GUIDELINES:
{guidelines}

CASE INFORMATION:
- Body part: {body_part}
- Cancer type: {cancer_type}

RADIOLOGIC REPORT:
{report}

TASK: Analyze the report against AJCC guidelines and determine T stage.

CRITICAL OUTPUT REQUIREMENTS:
- RESPOND WITH ONLY THE JSON OBJECT BELOW
- NO <think> TAGS
- NO REASONING OUTSIDE JSON
- NO EXPLANATIONS BEFORE OR AFTER JSON
- NO ADDITIONAL TEXT WHATSOEVER

START YOUR RESPONSE WITH {{ AND END WITH }}

{{
    "t_stage": "T1",
    "confidence": 0.85,
    "rationale": "Based on AJCC guidelines: [specific criteria and findings from report]",
    "extracted_info": {{
        "tumor_size": "dimension from report",
        "largest_dimension": "5.4 cm",
        "invasions": ["anatomical structures"],
        "extensions": ["specific locations"],
        "multiple_tumors": false,
        "key_findings": ["relevant findings"]
    }}
}}

VALIDATION:
- t_stage: T0, T1, T1a, T1b, T2, T2a, T2b, T3, T4, T4a, T4b, or TX
- confidence: 0.0 to 1.0
- rationale: Reference specific AJCC criteria and report findings
- Use TX only when tumor information is truly insufficient

RESPOND WITH JSON ONLY:"""

        try:
            response = await self.llm_provider.generate(prompt)
            
            # Parse JSON response with robust error handling
            import json
            import re
            
            # Clean the response first
            cleaned_response = response.strip()
            
            # Remove <think> tags and their content
            cleaned_response = re.sub(r'<think>.*?</think>', '', cleaned_response, flags=re.DOTALL)
            
            # Remove any other common LLM artifacts
            cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
            cleaned_response = re.sub(r'```\s*$', '', cleaned_response)
            cleaned_response = cleaned_response.strip()
            
            # Find JSON object in the cleaned response
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = cleaned_response
            
            try:
                result = json.loads(json_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract information manually
                self.logger.warning(f"JSON parsing failed. Response: {response[:200]}...")
                result = self._extract_staging_from_text(response)
            
            return (
                result.get("t_stage", "TX"),
                float(result.get("confidence", 0.5)),
                result.get("rationale", "Unable to determine staging rationale"),
                result.get("extracted_info", {})
            )
            
        except Exception as e:
            self.logger.error(f"Failed to determine T stage: {str(e)}")
            
            # Fallback to conservative determination
            return self._fallback_t_staging()
    
    def _extract_staging_from_text(self, response: str) -> Dict[str, Any]:
        """Extract staging information from non-JSON text response.
        
        Args:
            response: Text response from LLM
            
        Returns:
            Dictionary with extracted staging info
        """
        import re
        
        result = {
            "t_stage": "TX",
            "confidence": 0.3,
            "rationale": "Unable to parse LLM response"
        }
        
        # Try multiple patterns for T stage extraction
        t_stage_patterns = [
            r'["\']?t_stage["\']?\s*[:\=]\s*["\']?(T[0-4][a-z]?|TX)["\']?',  # JSON-like
            r'T\s*stage[:\s]+(T[0-4][a-z]?|TX)\b',                           # "T stage: T1"
            r'\b(T[0-4][a-z]?)\b(?!\d)',                                    # Standalone T stage
            r'stage[:\s]+(T[0-4][a-z]?|TX)\b',                              # "stage: T1"
            r'classified\s+as\s+(T[0-4][a-z]?|TX)\b'                        # "classified as T1"
        ]
        
        for pattern in t_stage_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                # Get the last group (the T stage)
                t_stage = match.groups()[-1].upper()
                result["t_stage"] = t_stage
                result["confidence"] = 0.7 if t_stage != "TX" else 0.4
                break
        
        # Look for confidence patterns with multiple formats
        conf_patterns = [
            r'["\']?confidence["\']?\s*[:\=]\s*([0-9]+(?:\.[0-9]+)?)',  # JSON-like
            r'confidence[:\s]+([0-9]+(?:\.[0-9]+)?)(?:%)?',              # "confidence: 0.8" or "confidence: 80%"
            r'([0-9]+(?:\.[0-9]+)?)\s*confidence',                       # "0.8 confidence"
            r'certainty[:\s]+([0-9]+(?:\.[0-9]+)?)(?:%)?'               # "certainty: 80%"
        ]
        
        for pattern in conf_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                try:
                    conf_val = float(match.group(1))
                    if conf_val <= 1.0:
                        result["confidence"] = conf_val
                    elif conf_val <= 100:
                        result["confidence"] = conf_val / 100
                    break
                except ValueError:
                    continue
        
        # Extract rationale from various formats
        rationale_patterns = [
            r'["\']?rationale["\']?\s*[:\=]\s*["\']([^"\'\n]+)["\']?',  # JSON-like
            r'rationale[:\s]+([^\n]+)',                                 # "rationale: explanation"
            r'explanation[:\s]+([^\n]+)',                               # "explanation: ..."
            r'because\s+([^\n.]+)',                                     # "because ..."
            r'since\s+([^\n.]+)'                                       # "since ..."
        ]
        
        for pattern in rationale_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                rationale = match.group(1).strip().strip('"\'')
                if len(rationale) > 10:  # Ensure it's substantial
                    result["rationale"] = rationale
                    break
        
        # If no rationale found, extract first meaningful sentence
        if result["rationale"] == "Unable to parse LLM response":
            sentences = response.split('.')
            for sentence in sentences:
                if any(word in sentence.lower() for word in ['tumor', 'mass', 'size', 'invasion', 'stage', 'cm']):
                    result["rationale"] = sentence.strip()[:100] + "..."
                    break
        
        return result
    
    
    def _fallback_t_staging(self) -> Tuple[str, float, str, Dict]:
        """Conservative fallback T staging when LLM analysis fails.
        
        Returns:
            Tuple of (t_stage, confidence, rationale, extracted_info)
        """
        return (
            "TX", 
            0.2, 
            "Fallback: LLM analysis failed - unable to determine T stage from report and guidelines",
            {}
        )