"""Query agent for generating questions when additional information is needed."""

from typing import List, Dict, Optional
from .base import BaseAgent, AgentContext, AgentMessage, AgentStatus
from config.llm_providers import QueryResponse

class QueryAgent(BaseAgent):
    """Agent that generates targeted questions to obtain missing information."""
    
    def __init__(self, llm_provider):
        """Initialize query agent.
        
        Args:
            llm_provider: LLM provider instance
        """
        super().__init__("query_agent", llm_provider)
    
    def validate_input(self, context: AgentContext) -> bool:
        """Validate that we have staging results to analyze.
        
        Args:
            context: Current agent context
            
        Returns:
            True if we have staging results
        """
        # Need at least the report and some staging attempt
        return (
            context.context_R is not None and
            context.context_B is not None and
            (context.context_T is not None or context.context_N is not None)
        )
    
    async def process(self, context: AgentContext) -> AgentMessage:
        """Generate questions based on missing or uncertain information.
        
        Args:
            context: Current agent context
            
        Returns:
            AgentMessage with query questions
        """
        # Analyze what information is missing or uncertain
        missing_info = self._analyze_missing_info(context)
        
        if not missing_info["needs_query"]:
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SKIPPED,
                data={},
                metadata={"reason": "No additional information needed"}
            )
        
        # Generate targeted questions
        questions = await self._generate_questions(context, missing_info)
        
        return AgentMessage(
            agent_id=self.agent_id,
            status=AgentStatus.SUCCESS,
            data={
                "context_Q": self._format_questions(questions)
            },
            metadata={
                "missing_info": missing_info,
                "question_count": len(questions)
            }
        )
    
    def _analyze_missing_info(self, context: AgentContext) -> Dict[str, any]:
        """Analyze what information is missing or uncertain.
        
        Args:
            context: Current agent context
            
        Returns:
            Dictionary describing missing information
        """
        missing = {
            "needs_query": False,
            "t_issues": [],
            "n_issues": [],
            "general_issues": []
        }
        
        # Check T staging
        if context.context_T == "TX":
            missing["needs_query"] = True
            missing["t_issues"].append("tumor_size_missing")
            missing["t_issues"].append("tumor_characteristics_unclear")
        elif context.context_CT and context.context_CT < 0.7:
            missing["needs_query"] = True
            missing["t_issues"].append("low_confidence_t_staging")
            if "size not specified" in context.context_RationaleT.lower():
                missing["t_issues"].append("tumor_size_missing")
        
        # Check N staging
        if context.context_N == "NX":
            missing["needs_query"] = True
            missing["n_issues"].append("lymph_node_status_unclear")
        elif context.context_CN and context.context_CN < 0.7:
            missing["needs_query"] = True
            missing["n_issues"].append("low_confidence_n_staging")
            if "not specified" in context.context_RationaleN.lower():
                missing["n_issues"].append("lymph_node_details_missing")
        
        # Check for general issues
        if context.context_B:
            body_part = context.context_B.get("body_part", "").lower()
            
            # Organ-specific checks
            if body_part == "lung" and "lobe" not in context.context_R.lower():
                missing["general_issues"].append("lung_lobe_not_specified")
            elif body_part == "breast" and "quadrant" not in context.context_R.lower():
                missing["general_issues"].append("breast_quadrant_not_specified")
        
        return missing
    
    async def _generate_questions(
        self,
        context: AgentContext,
        missing_info: Dict
    ) -> List[Dict[str, str]]:
        """Generate specific questions based on missing information.
        
        Args:
            context: Current agent context
            missing_info: Analysis of missing information
            
        Returns:
            List of questions with metadata
        """
        questions = []
        
        # Generate questions for T staging issues
        if missing_info["t_issues"]:
            t_questions = await self._generate_t_questions(
                context,
                missing_info["t_issues"]
            )
            questions.extend(t_questions)
        
        # Generate questions for N staging issues
        if missing_info["n_issues"]:
            n_questions = await self._generate_n_questions(
                context,
                missing_info["n_issues"]
            )
            questions.extend(n_questions)
        
        # Generate general questions if needed
        if missing_info["general_issues"]:
            general_questions = await self._generate_general_questions(
                context,
                missing_info["general_issues"]
            )
            questions.extend(general_questions)
        
        # Limit to most important questions
        return self._prioritize_questions(questions)[:3]
    
    async def _generate_t_questions(
        self,
        context: AgentContext,
        issues: List[str]
    ) -> List[Dict[str, str]]:
        """Generate questions for T staging issues.
        
        Args:
            context: Current agent context
            issues: List of T staging issues
            
        Returns:
            List of question dictionaries
        """
        body_part = context.context_B["body_part"]
        cancer_type = context.context_B["cancer_type"]
        
        prompt = f"""Generate specific questions to clarify T staging for {cancer_type} of {body_part}.

CRITICAL LANGUAGE REQUIREMENT: 
- OUTPUT MUST BE IN ENGLISH ONLY
- NO Chinese, Korean, Japanese, or other non-English characters
- NO mixed language output
- Use only standard English medical terminology

Issues identified:
{chr(10).join(f"- {issue}" for issue in issues)}

Current T staging result: {context.context_T}
Rationale: {context.context_RationaleT}

Generate ONE specific, clinically relevant question that would help determine the T stage.
Focus on:
- Tumor size (if missing)
- Depth of invasion
- Extension to adjacent structures
- Specific anatomical landmarks

Use standard English anatomical terms only."""

        # Try structured output first for better reliability
        if hasattr(self.llm_provider, 'generate_structured'):
            try:
                result = await self._generate_t_questions_structured(prompt)
                return [result]
            except Exception as e:
                self.logger.warning(f"Structured T question generation failed, falling back to manual parsing: {str(e)}")

        # Fallback to manual JSON parsing
        try:
            response = await self.llm_provider.generate(prompt + """

Return in JSON format:
[
    {{
        "question": "specific question text",
        "purpose": "what this helps determine",
        "priority": "high/medium/low"
    }}
]""")
            import json
            import re
            
            # Clean the response
            cleaned_response = response.strip()
            cleaned_response = re.sub(r'<think>.*?</think>', '', cleaned_response, flags=re.DOTALL)
            cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
            cleaned_response = re.sub(r'```\s*$', '', cleaned_response)
            cleaned_response = cleaned_response.strip()
            
            # Try to find JSON array
            json_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = cleaned_response
            
            try:
                parsed_questions = json.loads(json_text)
                
                # Validate English-only output  
                validated_questions = self._validate_english_output(parsed_questions)
                return validated_questions
                
            except json.JSONDecodeError:
                self.logger.warning(f"JSON parsing failed for T questions. Response: {response[:200]}...")
                # Try to extract questions from text fallback
                return self._extract_questions_from_text(response, "tumor")
                
        except Exception as e:
            self.logger.error(f"Failed to generate T questions: {str(e)}")
            
            # Fallback questions
            return [
                {
                    "question": f"What is the largest dimension of the primary tumor in centimeters?",
                    "purpose": "tumor_size_for_t_staging",
                    "priority": "high"
                }
            ]

    async def _generate_t_questions_structured(self, prompt: str) -> Dict[str, str]:
        """Generate T staging questions using structured output."""
        result = await self.llm_provider.generate_structured(
            prompt,
            QueryResponse,
            temperature=0.1
        )
        
        # Convert to legacy format for compatibility
        return {
            "question": result["question"],
            "purpose": "tumor_staging_clarification", 
            "priority": result["priority"]
        }
    
    async def _generate_n_questions(
        self,
        context: AgentContext,
        issues: List[str]
    ) -> List[Dict[str, str]]:
        """Generate questions for N staging issues.
        
        Args:
            context: Current agent context
            issues: List of N staging issues
            
        Returns:
            List of question dictionaries
        """
        body_part = context.context_B["body_part"]
        cancer_type = context.context_B["cancer_type"]
        
        prompt = f"""Generate specific questions to clarify N staging for {cancer_type} of {body_part}.

CRITICAL LANGUAGE REQUIREMENT: 
- OUTPUT MUST BE IN ENGLISH ONLY
- NO Chinese, Korean, Japanese, or other non-English characters
- NO mixed language output
- Use only standard English medical terminology

IMPORTANT CONTEXT: We are analyzing RADIOLOGIC REPORTS (CT, MRI, PET scans), not pathology specimens.

Issues identified:
{chr(10).join(f"- {issue}" for issue in issues)}

Current N staging result: {context.context_N}
Rationale: {context.context_RationaleN}

Generate ONE specific question about lymph node involvement from RADIOLOGIC IMAGING.
Focus on:
- Presence/absence of enlarged or suspicious lymph nodes on imaging
- Number of enlarged nodes visible on imaging
- Size of largest enlarged node (in cm)
- Anatomical location and laterality on imaging (use terms like "cervical", "supraclavicular", "level I/II/III/IV")

Use radiologic terminology and ask about imaging findings, not pathology.
Use standard English anatomical terms: "cervical lymph nodes", "internal jugular chain", "upper neck nodes"."""

        # Try structured output first for better reliability
        if hasattr(self.llm_provider, 'generate_structured'):
            try:
                result = await self._generate_n_questions_structured(prompt)
                return [result]
            except Exception as e:
                self.logger.warning(f"Structured N question generation failed, falling back to manual parsing: {str(e)}")

        # Fallback to manual JSON parsing
        try:
            response = await self.llm_provider.generate(prompt + """

Return in JSON format:
[
    {{
        "question": "specific question text about imaging findings",
        "purpose": "what this helps determine",
        "priority": "high/medium/low"
    }}
]""")
            import json
            import re
            
            # Clean the response
            cleaned_response = response.strip()
            cleaned_response = re.sub(r'<think>.*?</think>', '', cleaned_response, flags=re.DOTALL)
            cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
            cleaned_response = re.sub(r'```\s*$', '', cleaned_response)
            cleaned_response = cleaned_response.strip()
            
            # Try to find JSON array
            json_match = re.search(r'\[.*\]', cleaned_response, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = cleaned_response
            
            try:
                parsed_questions = json.loads(json_text)
                
                # Validate English-only output
                validated_questions = self._validate_english_output(parsed_questions)
                return validated_questions
                
            except json.JSONDecodeError:
                self.logger.warning(f"JSON parsing failed for N questions. Response: {response[:200]}...")
                # Try to extract questions from text fallback
                return self._extract_questions_from_text(response, "lymph")
                
        except Exception as e:
            self.logger.error(f"Failed to generate N questions: {str(e)}")
            
            # Fallback questions with radiologic context
            return [
                {
                    "question": "Are there any enlarged or suspicious lymph nodes visible on the radiologic imaging? If yes, please specify the number, size (in cm), and anatomical location.",
                    "purpose": "lymph_node_involvement_for_n_staging",
                    "priority": "high"
                }
            ]

    async def _generate_n_questions_structured(self, prompt: str) -> Dict[str, str]:
        """Generate N staging questions using structured output."""
        result = await self.llm_provider.generate_structured(
            prompt,
            QueryResponse,
            temperature=0.1
        )
        
        # Convert to legacy format for compatibility
        return {
            "question": result["question"],
            "purpose": "lymph_node_staging_clarification", 
            "priority": result["priority"]
        }
    
    async def _generate_general_questions(
        self,
        context: AgentContext,
        issues: List[str]
    ) -> List[Dict[str, str]]:
        """Generate general anatomical questions.
        
        Args:
            context: Current agent context
            issues: List of general issues
            
        Returns:
            List of question dictionaries
        """
        questions = []
        
        for issue in issues:
            if issue == "lung_lobe_not_specified":
                questions.append({
                    "question": "Which lobe(s) of the lung is the tumor located in?",
                    "purpose": "anatomical_location_for_staging",
                    "priority": "medium"
                })
            elif issue == "breast_quadrant_not_specified":
                questions.append({
                    "question": "Which quadrant of the breast is the tumor located in?",
                    "purpose": "anatomical_location_for_staging",
                    "priority": "medium"
                })
        
        return questions
    
    def _prioritize_questions(self, questions: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Prioritize questions by importance.
        
        Args:
            questions: List of all questions
            
        Returns:
            Prioritized list of questions
        """
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            questions,
            key=lambda q: priority_order.get(q.get("priority", "medium"), 1)
        )
    
    def _extract_questions_from_text(self, response: str, question_type: str) -> List[Dict[str, str]]:
        """Extract questions from non-JSON text response.
        
        Args:
            response: Text response from LLM
            question_type: Type of questions (tumor/lymph)
            
        Returns:
            List of question dictionaries
        """
        import re
        
        questions = []
        
        # Look for question patterns
        question_patterns = [
            r'(\d+\.\s*[^\n?]+\?)',  # Numbered questions
            r'([A-Z][^.?]*\?)',      # Questions starting with capital letter
            r'(What\s+[^?]+\?)',     # What questions
            r'(How\s+[^?]+\?)',      # How questions
            r'(Are\s+[^?]+\?)',      # Are questions
        ]
        
        found_questions = []
        for pattern in question_patterns:
            matches = re.findall(pattern, response, re.MULTILINE)
            found_questions.extend(matches)
        
        # Convert to structured format
        for i, q in enumerate(found_questions[:3]):  # Limit to 3 questions
            clean_question = re.sub(r'^\d+\.\s*', '', q.strip())
            
            purpose = f"{question_type}_staging_clarification"
            priority = "high" if i == 0 else "medium"
            
            questions.append({
                "question": clean_question,
                "purpose": purpose,
                "priority": priority
            })
        
        # If no questions found, provide fallback
        if not questions:
            if question_type == "tumor":
                questions.append({
                    "question": "What is the size and extent of the primary tumor?",
                    "purpose": "tumor_staging_clarification",
                    "priority": "high"
                })
            else:  # lymph
                questions.append({
                    "question": "What is the status of regional lymph nodes?",
                    "purpose": "lymph_staging_clarification",
                    "priority": "high"
                })
        
        return questions
    
    def _validate_english_output(self, questions: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Validate that all questions are in English only.
        
        Args:
            questions: List of question dictionaries
            
        Returns:
            Validated and cleaned questions
        """
        import re
        
        validated_questions = []
        
        for q in questions:
            question_text = q.get("question", "")
            
            # Check for non-Latin characters (Chinese, Korean, Japanese, etc.)
            has_non_latin = bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7af\u3040-\u309f\u30a0-\u30ff]', question_text))
            
            if has_non_latin:
                self.logger.warning(f"Detected non-English characters in question: {question_text[:50]}...")
                
                # Replace with fallback English question
                fallback_question = {
                    "question": "Are there any enlarged lymph nodes (≥1 cm) or nodes with suspicious features visible on imaging? If yes, please specify number, size, and location using standard anatomical terms.",
                    "purpose": "lymph_node_staging_clarification",
                    "priority": "high"
                }
                validated_questions.append(fallback_question)
            else:
                # Additional cleanup - replace any mixed terms
                clean_question = question_text
                
                # Common Chinese medical terms to replace
                replacements = {
                    "颈内淋巴结": "cervical lymph nodes",
                    "淋巴结": "lymph nodes",
                    "颈部": "neck",
                    "上颈": "upper cervical"
                }
                
                for chinese, english in replacements.items():
                    clean_question = clean_question.replace(chinese, english)
                
                q["question"] = clean_question
                validated_questions.append(q)
        
        # Ensure at least one question exists
        if not validated_questions:
            validated_questions.append({
                "question": "Are there any enlarged or suspicious lymph nodes visible on the radiologic imaging? Please specify number, size (in cm), and anatomical location.",
                "purpose": "lymph_node_staging_fallback",
                "priority": "high"
            })
        
        return validated_questions
    
    def _format_questions(self, questions: List[Dict[str, str]]) -> str:
        """Format questions for presentation to user.
        
        Args:
            questions: List of question dictionaries
            
        Returns:
            Formatted question text
        """
        formatted = ["To provide more accurate staging, please provide the following information:"]
        
        for i, q in enumerate(questions, 1):
            formatted.append(f"\n{i}. {q['question']}")
        
        formatted.append("\nPlease provide as much detail as available from the radiologic imaging reports.")
        
        return "\n".join(formatted)