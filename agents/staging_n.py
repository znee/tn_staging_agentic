"""N staging agent for lymph node classification."""

import re
from typing import Dict, Tuple, Optional, List, Any
from .base import BaseAgent, AgentContext, AgentMessage, AgentStatus

class NStagingAgent(BaseAgent):
    """Agent that determines N staging based on lymph node findings."""
    
    def __init__(self, llm_provider):
        """Initialize N staging agent.
        
        Args:
            llm_provider: LLM provider instance
        """
        super().__init__("n_staging_agent", llm_provider)
        
    
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
            context.context_GN is not None
        )
    
    async def process(self, context: AgentContext) -> AgentMessage:
        """Determine N staging from radiologic report.
        
        Args:
            context: Current agent context
            
        Returns:
            AgentMessage with N staging results
        """
        report = context.context_R
        guidelines = context.context_GN
        body_part = context.context_B["body_part"]
        cancer_type = context.context_B["cancer_type"]
        
        # Determine N stage directly from report and guidelines
        n_stage, confidence, rationale, extracted_info = await self._determine_n_stage(
            report, guidelines, body_part, cancer_type
        )
        
        return AgentMessage(
            agent_id=self.agent_id,
            status=AgentStatus.SUCCESS,
            data={
                "context_N": n_stage,
                "context_CN": confidence,
                "context_RationaleN": rationale
            },
            metadata={
                "node_info": extracted_info,
                "body_part": body_part,
                "cancer_type": cancer_type
            }
        )
    
    
    async def _determine_n_stage(
        self,
        report: str,
        guidelines: str,
        body_part: str,
        cancer_type: str
    ) -> Tuple[str, float, str, Dict]:
        """Determine N stage directly from report and guidelines.
        
        Args:
            report: Full radiologic report
            guidelines: N staging guidelines
            body_part: Body part/organ
            cancer_type: Cancer type
            
        Returns:
            Tuple of (n_stage, confidence, rationale, extracted_info)
        """
        prompt = f"""INSTRUCTIONS: You are a medical staging expert. Your task is to output ONLY a JSON object with N staging analysis. NO THINKING, NO EXPLANATIONS, NO ADDITIONAL TEXT.

AJCC GUIDELINES:
{guidelines}

CASE INFORMATION:
- Body part: {body_part}
- Cancer type: {cancer_type}

RADIOLOGIC REPORT:
{report}

TASK: Analyze the report against AJCC guidelines and determine N stage.

CRITICAL N STAGING RULES:
- N0: Use ONLY when lymph nodes are EXPLICITLY described as negative, non-enlarged, or no metastatic involvement
- NX: Use when lymph node status is NOT mentioned, unclear, or cannot be assessed from the report
- N1-N3: Use when metastatic lymph nodes are described with specific criteria

EXAMPLES:
- "No enlarged lymph nodes" → N0
- "Lymph nodes appear normal" → N0  
- "No metastatic lymphadenopathy" → N0
- Report mentions tumor but NO lymph node description → NX
- "Lymph nodes not well visualized" → NX
- "Multiple enlarged nodes, largest 3cm" → N1/N2/N3 (per guidelines)

CRITICAL OUTPUT REQUIREMENTS:
- RESPOND WITH ONLY THE JSON OBJECT BELOW
- NO <think> TAGS
- NO REASONING OUTSIDE JSON
- NO EXPLANATIONS BEFORE OR AFTER JSON
- NO ADDITIONAL TEXT WHATSOEVER

START YOUR RESPONSE WITH {{ AND END WITH }}

{{
    "n_stage": "NX",
    "confidence": 0.90,
    "rationale": "Based on AJCC guidelines: [specific criteria and findings from report]",
    "extracted_info": {{
        "node_status": "positive/negative/unclear/not_mentioned",
        "node_sizes": ["size from report or 'not mentioned'"],
        "node_count": "number or 'not mentioned'",
        "locations": ["anatomical locations or 'not mentioned'"],
        "laterality": "ipsilateral/contralateral/bilateral/not_mentioned",
        "key_findings": ["relevant lymph node findings or 'no lymph node information in report'"]
    }}
}}

VALIDATION:
- n_stage: N0, N1, N1a, N1b, N2, N2a, N2b, N3, N3a, N3b, or NX
- confidence: 0.0 to 1.0
- rationale: Reference specific AJCC criteria and report findings
- DEFAULT TO NX when lymph node information is absent or unclear
- Use N0 ONLY with explicit negative lymph node description

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
            
            # Validate N0 vs NX decision
            n_stage = result.get("n_stage", "NX")
            confidence = float(result.get("confidence", 0.5))
            
            # Critical validation: Check if N0 is appropriate
            if n_stage == "N0":
                n_stage, confidence = self._validate_n0_staging(report, result, confidence)
            
            return (
                n_stage,
                confidence,
                result.get("rationale", "Unable to determine staging rationale"),
                result.get("extracted_info", {})
            )
            
        except Exception as e:
            self.logger.error(f"Failed to determine N stage: {str(e)}")
            
            # Fallback to conservative determination
            return self._fallback_n_staging()
    
    def _extract_staging_from_text(self, response: str) -> Dict[str, Any]:
        """Extract staging information from non-JSON text response.
        
        Args:
            response: Text response from LLM
            
        Returns:
            Dictionary with extracted staging info
        """
        import re
        
        result = {
            "n_stage": "NX",  # Default to NX (cannot assess) not N0
            "confidence": 0.3,
            "rationale": "Unable to parse LLM response - lymph node status unclear"
        }
        
        # Try multiple patterns for N stage extraction
        n_stage_patterns = [
            r'["\']?n_stage["\']?\s*[:\=]\s*["\']?(N[0-3][a-z]?|NX)["\']?',  # JSON-like
            r'N\s*stage[:\s]+(N[0-3][a-z]?|NX)\b',                           # "N stage: N0"
            r'\b(N[0-3][a-z]?)\b(?!\d)',                                    # Standalone N stage
            r'stage[:\s]+(N[0-3][a-z]?|NX)\b',                              # "stage: N0"
            r'classified\s+as\s+(N[0-3][a-z]?|NX)\b'                        # "classified as N0"
        ]
        
        for pattern in n_stage_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                # Get the last group (the N stage)
                n_stage = match.groups()[-1].upper()
                result["n_stage"] = n_stage
                
                # Adjust confidence based on medical appropriateness
                if n_stage == "NX":
                    result["confidence"] = 0.7  # Conservative approach is appropriate
                elif n_stage == "N0":
                    # Check if there's explicit negative language in response
                    negative_indicators = [
                        "no enlarged", "no metastatic", "nodes appear normal", 
                        "negative", "non-enlarged", "no suspicious"
                    ]
                    has_explicit_negative = any(indicator in response.lower() for indicator in negative_indicators)
                    result["confidence"] = 0.8 if has_explicit_negative else 0.4
                else:
                    result["confidence"] = 0.7  # N1-N3 staging
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
                if any(word in sentence.lower() for word in ['lymph', 'node', 'nodal', 'metastas', 'stage', 'enlarged']):
                    result["rationale"] = sentence.strip()[:100] + "..."
                    break
        
        return result
    
    def _validate_n0_staging(self, report: str, result: Dict[str, Any], confidence: float) -> Tuple[str, float]:
        """Validate if N0 staging is appropriate based on explicit lymph node description.
        
        Args:
            report: Original radiologic report
            result: LLM result dictionary
            confidence: Original confidence score
            
        Returns:
            Tuple of (validated_n_stage, adjusted_confidence)
        """
        # Look for explicit negative lymph node descriptions in the report
        explicit_negative_phrases = [
            "no enlarged lymph nodes",
            "no metastatic lymph nodes", 
            "no metastatic lymphadenopathy",
            "lymph nodes appear normal",
            "lymph nodes are normal",
            "no suspicious lymph nodes",
            "negative for lymphadenopathy",
            "non-enlarged lymph nodes",
            "no evidence of lymph node metastasis",
            "lymph nodes negative",
            "no pathologic lymph nodes"
        ]
        
        # Look for any lymph node mentions at all
        lymph_node_mentions = [
            "lymph node", "lymphadenopathy", "nodal", "cervical level",
            "supraclavicular", "axillary", "mediastinal", "hilar",
            "paratracheal", "subcarinal", "aortopulmonary"
        ]
        
        report_lower = report.lower()
        
        # Check if there's explicit negative description
        has_explicit_negative = any(phrase in report_lower for phrase in explicit_negative_phrases)
        
        # Check if lymph nodes are mentioned at all
        has_lymph_node_mention = any(mention in report_lower for mention in lymph_node_mentions)
        
        # Decision logic
        if has_explicit_negative:
            # Explicit negative description - N0 is appropriate
            return "N0", max(confidence, 0.8)
        elif has_lymph_node_mention:
            # Lymph nodes mentioned but not explicitly negative - depends on context
            # Check extracted info for clarity
            extracted_info = result.get("extracted_info", {})
            node_status = extracted_info.get("node_status", "unclear")
            
            if node_status == "negative":
                return "N0", confidence
            elif node_status in ["unclear", "not_mentioned"]:
                self.logger.info("Lymph nodes mentioned but status unclear - changing N0 to NX")
                return "NX", max(confidence * 0.8, 0.7)
            else:
                return "N0", confidence
        else:
            # No lymph node description at all - should be NX
            self.logger.info("No lymph node information in report - changing N0 to NX")
            return "NX", max(confidence * 0.9, 0.7)
    
    def _fallback_n_staging(self) -> Tuple[str, float, str, Dict]:
        """Conservative fallback N staging when LLM analysis fails.
        
        Returns:
            Tuple of (n_stage, confidence, rationale, extracted_info)
        """
        return (
            "NX", 
            0.2, 
            "Fallback: LLM analysis failed - lymph node status cannot be assessed from available information",
            {"node_status": "unclear", "key_findings": ["analysis failed - insufficient information"]}
        )