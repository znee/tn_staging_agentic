"""Detection agent for identifying body part and cancer type from radiologic reports."""

import re
from typing import Dict, Optional
from .base import BaseAgent, AgentContext, AgentMessage, AgentStatus
from config.llm_providers import DetectionResponse

class DetectionAgent(BaseAgent):
    """Agent that detects body part and cancer type from radiologic reports."""
    
    def __init__(self, llm_provider):
        """Initialize detection agent.
        
        Args:
            llm_provider: LLM provider instance
        """
        super().__init__("detection_agent", llm_provider)
        self.cancer_keywords = {
            "lung": ["lung", "pulmonary", "bronchogenic", "nsclc", "sclc", "adenocarcinoma"],
            "breast": ["breast", "mammary", "ductal", "lobular", "her2", "triple negative"],
            "colon": ["colon", "colorectal", "rectal", "sigmoid", "cecal"],
            "prostate": ["prostate", "prostatic", "psa"],
            "liver": ["liver", "hepatic", "hepatocellular", "hcc", "cholangiocarcinoma"],
            "pancreas": ["pancreas", "pancreatic", "whipple"],
            "kidney": ["kidney", "renal", "rcc", "nephro"],
            "bladder": ["bladder", "urothelial", "transitional cell"],
            "stomach": ["stomach", "gastric", "gastrointestinal"],
            "esophagus": ["esophagus", "esophageal", "gastroesophageal"],
            "thyroid": ["thyroid", "papillary", "follicular", "medullary"],
            "brain": ["brain", "glioma", "glioblastoma", "meningioma", "cerebral"]
        }
    
    def validate_input(self, context: AgentContext) -> bool:
        """Validate that radiologic report is present.
        
        Args:
            context: Current agent context
            
        Returns:
            True if report is present
        """
        return context.context_R is not None and len(context.context_R.strip()) > 0
    
    async def process(self, context: AgentContext) -> AgentMessage:
        """Process radiologic report to extract body part and cancer type.
        
        Args:
            context: Current agent context
            
        Returns:
            AgentMessage with detection results
        """
        report = context.context_R.lower()
        
        # First try pattern matching for common patterns
        detected = self._pattern_detection(report)
        
        # If pattern matching fails or needs confirmation, use LLM
        if not detected or detected.get("confidence", 0) < 0.8:
            detected = await self._llm_detection(context.context_R)
        
        if detected and detected.get("body_part") and detected.get("cancer_type"):
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={
                    "context_B": {
                        "body_part": detected["body_part"],
                        "cancer_type": detected["cancer_type"]
                    }
                },
                metadata={
                    "detection_method": detected.get("method", "unknown"),
                    "confidence": detected.get("confidence", 0.5)
                }
            )
        else:
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.FAILED,
                data={},
                error="Could not detect body part or cancer type from report"
            )
    
    def _pattern_detection(self, report: str) -> Optional[Dict[str, str]]:
        """Detect using pattern matching.
        
        Args:
            report: Lowercase report text
            
        Returns:
            Detection results or None
        """
        detected_parts = []
        
        for body_part, keywords in self.cancer_keywords.items():
            for keyword in keywords:
                if keyword in report:
                    detected_parts.append(body_part)
                    break
        
        if detected_parts:
            # Use the most frequently mentioned body part
            body_part = max(set(detected_parts), key=detected_parts.count)
            
            # Try to extract cancer type
            cancer_type = self._extract_cancer_type(report, body_part)
            
            if cancer_type:
                return {
                    "body_part": body_part,
                    "cancer_type": cancer_type,
                    "method": "pattern",
                    "confidence": 0.9 if len(detected_parts) == 1 else 0.7
                }
        
        return None
    
    def _extract_cancer_type(self, report: str, body_part: str) -> Optional[str]:
        """Extract specific cancer type based on body part.
        
        Args:
            report: Lowercase report text
            body_part: Detected body part
            
        Returns:
            Cancer type or None
        """
        cancer_patterns = {
            "lung": {
                "adenocarcinoma": r"adenocarcinoma",
                "squamous cell carcinoma": r"squamous\s+cell",
                "small cell lung cancer": r"small\s+cell|sclc",
                "non-small cell lung cancer": r"non[\s-]?small\s+cell|nsclc"
            },
            "breast": {
                "invasive ductal carcinoma": r"invasive\s+ductal|idc",
                "invasive lobular carcinoma": r"invasive\s+lobular|ilc",
                "ductal carcinoma in situ": r"dcis|ductal\s+carcinoma\s+in\s+situ",
                "triple negative breast cancer": r"triple\s+negative|tnbc"
            },
            "colon": {
                "adenocarcinoma": r"adenocarcinoma",
                "mucinous adenocarcinoma": r"mucinous",
                "signet ring cell carcinoma": r"signet\s+ring"
            },
            "prostate": {
                "adenocarcinoma": r"adenocarcinoma",
                "small cell carcinoma": r"small\s+cell",
                "transitional cell carcinoma": r"transitional\s+cell|urothelial"
            }
        }
        
        if body_part in cancer_patterns:
            for cancer_type, pattern in cancer_patterns[body_part].items():
                if re.search(pattern, report):
                    return cancer_type
        
        # Default to generic carcinoma if no specific type found
        return f"{body_part} carcinoma"
    
    async def _llm_detection(self, report: str) -> Dict[str, str]:
        """Use LLM for detection when pattern matching fails.
        
        Args:
            report: Original report text
            
        Returns:
            Detection results
        """
        # Try structured output first for better reliability
        if hasattr(self.llm_provider, 'generate_structured'):
            try:
                result = await self._llm_detection_structured(report)
                return {
                    "body_part": result["body_part"].lower(),
                    "cancer_type": result["cancer_type"],
                    "method": "llm_structured",
                    "confidence": result["confidence"]
                }
            except Exception as e:
                self.logger.warning(f"Structured detection failed, falling back to manual parsing: {str(e)}")
        
        # Fallback to manual JSON parsing
        return await self._llm_detection_manual(report)
    
    async def _llm_detection_structured(self, report: str) -> Dict[str, any]:
        """Use structured output for detection (preferred method)."""
        prompt = f"""Analyze this radiologic report and identify the primary body part/organ being examined and the specific type of cancer mentioned.

Report:
{report}

Extract the body part and cancer type with your confidence level."""

        result = await self.llm_provider.generate_structured(
            prompt,
            DetectionResponse,
            temperature=0.1
        )
        return result
    
    async def _llm_detection_manual(self, report: str) -> Dict[str, str]:
        """Fallback manual detection with JSON parsing."""
        prompt = f"""Analyze the following radiologic report and identify:
1. The primary body part/organ being examined
2. The specific type of cancer mentioned

Report:
{report}

Respond in the following JSON format:
{{
    "body_part": "detected body part",
    "cancer_type": "specific cancer type",
    "confidence": 0.0-1.0
}}

If you cannot determine either with confidence, use null for that field."""

        try:
            response = await self.llm_provider.generate(prompt)
            
            # Parse JSON response - be more robust about parsing
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
            
            # Try to extract JSON from cleaned response
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = cleaned_response
            
            result = json.loads(json_text)
            
            if result.get("body_part") and result.get("cancer_type"):
                return {
                    "body_part": result["body_part"].lower(),
                    "cancer_type": result["cancer_type"],
                    "method": "llm_manual",
                    "confidence": result.get("confidence", 0.7)
                }
        except Exception as e:
            self.logger.error(f"Manual detection failed: {str(e)}")
            self.logger.error(f"Response was: {response[:200]}...")
        
        return None