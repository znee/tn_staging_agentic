"""Report generation agent for creating structured TN staging reports."""

from typing import Dict, Optional
from datetime import datetime
from .base import BaseAgent, AgentContext, AgentMessage, AgentStatus
from config.llm_providers import ReportResponse

class ReportAgent(BaseAgent):
    """Agent that generates formal TN staging reports."""
    
    def __init__(self, llm_provider):
        """Initialize report agent.
        
        Args:
            llm_provider: LLM provider instance
        """
        super().__init__("report_agent", llm_provider)
    
    def validate_input(self, context: AgentContext) -> bool:
        """Validate that we have minimum required information for report.
        
        Args:
            context: Current agent context
            
        Returns:
            True if we can generate a report
        """
        # Log current context state for debugging
        self.logger.debug(f"Report validation - R: {context.context_R is not None}, "
                         f"B: {context.context_B is not None}, "
                         f"T: {context.context_T}, N: {context.context_N}")
        
        # Check for required contexts - allow reports even with partial staging
        has_basic_required = (
            context.context_R is not None and
            context.context_B is not None
        )
        
        has_staging = (
            context.context_T is not None or
            context.context_N is not None
        )
        
        if not has_basic_required:
            self.logger.error(f"Report agent validation failed - missing basic contexts: "
                            f"R={context.context_R is not None}, "
                            f"B={context.context_B is not None}")
            return False
        
        if not has_staging:
            self.logger.error(f"Report agent validation failed - no staging results: "
                            f"T={context.context_T}, N={context.context_N}")
            return False
        
        # Warn about partial staging but allow report generation
        if context.context_T is None:
            self.logger.warning(f"T staging missing, will use TX fallback")
        if context.context_N is None:
            self.logger.warning(f"N staging missing, will use NX fallback")
        
        return True
    
    async def process(self, context: AgentContext) -> AgentMessage:
        """Generate comprehensive TN staging report.
        
        Args:
            context: Current agent context
            
        Returns:
            AgentMessage with generated report
        """
        report_data = self._prepare_report_data(context)
        
        # Generate different report sections
        summary = await self._generate_summary(report_data)
        staging_details = self._generate_staging_details(report_data)
        recommendations = await self._generate_recommendations(context, report_data)
        
        # Combine into full report
        full_report = self._combine_report_sections(
            summary, staging_details, recommendations, report_data
        )
        
        return AgentMessage(
            agent_id=self.agent_id,
            status=AgentStatus.SUCCESS,
            data={
                "final_report": full_report,
                "tn_stage": f"{report_data['t_stage']}{report_data['n_stage']}",
                "confidence_score": self._calculate_overall_confidence(report_data)
            },
            metadata={
                "report_sections": {
                    "summary": len(summary.split()),
                    "findings": len(findings.split()),
                    "staging_details": len(staging_details.split()),
                    "recommendations": len(recommendations.split())
                },
                "generation_time": datetime.now().isoformat()
            }
        )
    
    def _prepare_report_data(self, context: AgentContext) -> Dict[str, any]:
        """Prepare all data needed for report generation.
        
        Args:
            context: Current agent context
            
        Returns:
            Dictionary with report data
        """
        return {
            "original_report": context.context_R,
            "body_part": context.context_B["body_part"],
            "cancer_type": context.context_B["cancer_type"],
            "t_stage": context.context_T or "TX",  # Fallback for missing T staging
            "n_stage": context.context_N or "NX",  # Fallback for missing N staging
            "t_confidence": context.context_CT or 0.2,  # Low confidence for missing data
            "n_confidence": context.context_CN or 0.2,  # Low confidence for missing data
            "t_rationale": context.context_RationaleT or "T staging could not be determined",
            "n_rationale": context.context_RationaleN or "N staging could not be determined",
            "user_response": context.context_RR,
            "session_id": context.metadata.get("session_id", "unknown"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    async def _generate_summary(self, data: Dict[str, any]) -> str:
        """Generate executive summary section.
        
        Args:
            data: Report data dictionary
            
        Returns:
            Summary section text
        """
        tn_stage = f"{data['t_stage']}{data['n_stage']}"
        confidence = self._calculate_overall_confidence(data)
        
        summary = f"""EXECUTIVE SUMMARY

Primary Site: {data['body_part'].title()}
Histology: {data['cancer_type']}
TNM Stage: {tn_stage}
Overall Confidence: {confidence:.1%}

STAGING SUMMARY:
• T Stage: {data['t_stage']} (Confidence: {data['t_confidence']:.1%})
• N Stage: {data['n_stage']} (Confidence: {data['n_confidence']:.1%})
• M Stage: Not assessed (requires additional imaging/clinical correlation)

CLINICAL SIGNIFICANCE:
{await self._get_clinical_significance(data['t_stage'], data['n_stage'], data['body_part'], data['cancer_type'])}"""
        
        return summary
    
    def _generate_staging_details(self, data: Dict[str, any]) -> str:
        """Generate detailed staging analysis section.
        
        Args:
            data: Report data dictionary
            
        Returns:
            Staging details section text
        """
        details = f"""DETAILED STAGING ANALYSIS

T STAGE ANALYSIS - {data['t_stage']}:
{data['t_rationale']}

N STAGE ANALYSIS - {data['n_stage']}:
{data['n_rationale']}

QUALITY ASSESSMENT:
• T Stage Confidence: {data['t_confidence']:.1%}
  {self._get_confidence_explanation(data['t_confidence'])}

• N Stage Confidence: {data['n_confidence']:.1%}
  {self._get_confidence_explanation(data['n_confidence'])}

LIMITATIONS:
{self._identify_limitations(data)}"""
        
        return details
    
    async def _generate_recommendations(
        self,
        context: AgentContext,
        data: Dict[str, any]
    ) -> str:
        """Generate recommendations section using LLM.
        
        Args:
            context: Current agent context
            data: Report data dictionary
            
        Returns:
            Recommendations section text
        """
        # Enhanced prompt for radiologic staging report - LLM-first approach
        prompt = f"""You are generating recommendations for a radiologic TN staging report. This report will be reviewed by a radiologist.

Patient staging:
- Cancer Type: {data['cancer_type']}
- Primary Site: {data['body_part']}
- T Stage: {data['t_stage']} (Confidence: {data['t_confidence']:.1%})
- N Stage: {data['n_stage']} (Confidence: {data['n_confidence']:.1%})

Provide professional recommendations appropriate for a radiologic staging report that will be reviewed by a radiologist. Focus on:

1. Imaging recommendations for complete staging assessment
2. Correlation with clinical findings and pathology
3. Multidisciplinary team communication
4. Follow-up imaging strategies
5. Quality assurance for staging accuracy

Avoid specific treatment protocols - focus on radiologic staging completeness and accuracy.
Use professional medical language appropriate for radiologist review.
Be specific about imaging modalities, techniques, and timing.

Base recommendations on current imaging guidelines and staging protocols."""

        # Try structured output first for better reliability
        if hasattr(self.llm_provider, 'generate_structured'):
            try:
                result = await self._generate_recommendations_structured(prompt, data)
                return f"""RECOMMENDATIONS

{result["recommendations"]}

NEXT STEPS:
{chr(10).join(f"• {step}" for step in result["next_steps"])}"""
            except Exception as e:
                self.logger.warning(f"Structured recommendations generation failed, falling back to manual generation: {str(e)}")

        # Fallback to manual generation - LLM-first approach
        try:
            recommendations_text = await self.llm_provider.generate(prompt, temperature=0.3)
            
            # Generate next steps using LLM for radiologic context
            next_steps_prompt = f"""Generate specific next steps for radiologic staging completion of {data['cancer_type']} staged as {data['t_stage']}{data['n_stage']}.
            
Focus on imaging, staging accuracy, and radiologist workflow. Provide 4-6 actionable steps.
Confidence levels: T={data['t_confidence']:.1%}, N={data['n_confidence']:.1%}"""
            
            next_steps_text = await self.llm_provider.generate(next_steps_prompt, temperature=0.3)
            
            return f"""RECOMMENDATIONS

{recommendations_text}

NEXT STEPS:
{next_steps_text}"""
            
        except Exception as e:
            self.logger.error(f"Failed to generate recommendations: {str(e)}")
            
            # Fallback recommendations - radiologic staging focus
            return f"""RECOMMENDATIONS

RADIOLOGIC STAGING ASSESSMENT for {data['t_stage']}{data['n_stage']} {data['cancer_type']}:

IMAGING COMPLETION:
• Complete staging requires dedicated imaging protocol
• Consider contrast-enhanced imaging for optimal tissue characterization
• Evaluate for distant metastatic disease with appropriate imaging
• Correlate findings with clinical examination and pathology results

STAGING ACCURACY:
• Review AJCC staging criteria for {data['cancer_type']}
• Consider multidisciplinary team review for staging confirmation
• Document confidence levels and limitations in staging assessment
• Recommend additional imaging if staging uncertainty exists

FOLLOW-UP IMAGING:
• Establish baseline imaging for treatment response monitoring
• Plan surveillance imaging protocol per institutional guidelines
• Consider advanced imaging techniques for complex cases
• Ensure appropriate imaging follow-up intervals

NEXT STEPS:
• Multidisciplinary team staging conference review
• Correlation with pathology and clinical findings
• Complete staging imaging protocol if not already performed
• Document staging rationale and confidence assessment
• Establish baseline for treatment response monitoring
• Consider additional imaging consultation if staging uncertain"""

    async def _generate_recommendations_structured(self, prompt: str, data: Dict[str, any]) -> Dict[str, any]:
        """Generate recommendations using structured output."""
        result = await self.llm_provider.generate_structured(
            prompt,
            ReportResponse,
            temperature=0.1
        )
        
        # Ensure we have meaningful next steps - LLM generated
        if not result["next_steps"]:
            try:
                next_steps_prompt = f"""Generate 4-6 specific next steps for radiologic staging of {data['cancer_type']} staged as {data['t_stage']}{data['n_stage']}. Focus on imaging, staging accuracy, and radiologist workflow."""
                next_steps_text = await self.llm_provider.generate(next_steps_prompt, temperature=0.3)
                # Parse LLM response into list format
                result["next_steps"] = [line.strip().lstrip('•').strip() for line in next_steps_text.split('\n') if line.strip() and ('•' in line or line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.')))]
            except:
                result["next_steps"] = [
                    "Multidisciplinary team staging conference review",
                    "Correlation with pathology and clinical findings", 
                    "Complete staging imaging protocol assessment",
                    "Document staging rationale and confidence levels"
                ]
        
        return result
    
    def _combine_report_sections(
        self,
        summary: str,
        staging_details: str,
        recommendations: str,
        data: Dict[str, any]
    ) -> str:
        """Combine all sections into final report.
        
        Args:
            summary: Summary section
            staging_details: Staging details section
            recommendations: Recommendations section
            data: Report data dictionary
            
        Returns:
            Complete formatted report
        """
        header = f"""
==============================================================================
RADIOLOGIC CANCER STAGING ASSESSMENT
==============================================================================

Report Date: {data['timestamp']}
Session ID: {data['session_id']}
Reporting System: AI-Assisted Radiologic Staging v2.3

"""
        
        footer = f"""

==============================================================================
TECHNICAL NOTES

Analysis Method: AI-assisted staging with AJCC guidelines
Original Report Length: {len(data['original_report'].split())} words
Processing Confidence: {self._calculate_overall_confidence(data):.1%}

DISCLAIMER:
This analysis is intended to assist in clinical decision-making and should not
replace clinical judgment. All staging should be confirmed by qualified
healthcare professionals and correlated with additional clinical information.

==============================================================================
"""
        
        return header + summary + "\n\n" + staging_details + "\n\n" + recommendations + footer
    
    def _calculate_overall_confidence(self, data: Dict[str, any]) -> float:
        """Calculate overall confidence score.
        
        Args:
            data: Report data dictionary
            
        Returns:
            Overall confidence score (0-1)
        """
        t_conf = data.get('t_confidence', 0.5)
        n_conf = data.get('n_confidence', 0.5)
        
        # Weighted average with penalty for TX/NX
        if data['t_stage'] == 'TX':
            t_conf *= 0.3
        if data['n_stage'] == 'NX':
            n_conf *= 0.3
            
        return (t_conf + n_conf) / 2
    
    async def _get_clinical_significance(self, t_stage: str, n_stage: str, body_part: str, cancer_type: str) -> str:
        """Get clinical significance text for staging combination using LLM.
        
        Args:
            t_stage: T stage
            n_stage: N stage
            body_part: Body part
            cancer_type: Cancer type
            
        Returns:
            Clinical significance explanation
        """
        prompt = f"""Provide a brief clinical significance statement for {cancer_type} of {body_part} staged as {t_stage}{n_stage}.

Focus on radiologic staging implications and general prognostic context appropriate for a radiologist's report.
Keep it concise (1-2 sentences) and professional.
Avoid specific treatment recommendations - focus on staging significance.

If staging is incomplete (TX/NX), mention the need for additional information."""
        
        try:
            significance = await self.llm_provider.generate(prompt, temperature=0.3)
            return significance.strip()
        except Exception as e:
            self.logger.warning(f"Failed to generate clinical significance via LLM: {str(e)}")
            # Simple fallback without hardcoded medical logic
            if t_stage == "TX" or n_stage == "NX":
                return "Staging assessment incomplete - additional clinical correlation recommended."
            else:
                return "Staging results documented - clinical correlation recommended for treatment planning."
    
    async def _determine_stage_group(self, t_stage: str, n_stage: str) -> str:
        """Determine overall stage group using LLM.
        
        Args:
            t_stage: T stage
            n_stage: N stage
            
        Returns:
            Stage group (I, II, III, IVA, IVB, IVC)
        """
        prompt = f"""Determine the overall AJCC stage group for {t_stage}{n_stage} (assuming M0).

Provide only the stage group (e.g., I, II, III, IVA, IVB, IVC) based on current AJCC staging guidelines.
If staging is incomplete (TX/NX), respond with "Cannot be determined - incomplete staging"."""
        
        try:
            stage_group = await self.llm_provider.generate(prompt, temperature=0.1)
            return stage_group.strip()
        except Exception as e:
            self.logger.warning(f"Failed to determine stage group via LLM: {str(e)}")
            if t_stage == "TX" or n_stage == "NX":
                return "Cannot be determined - incomplete staging"
            else:
                return "Requires clinical correlation for stage grouping"
    
    def _get_confidence_explanation(self, confidence: float) -> str:
        """Get explanation for confidence level.
        
        Args:
            confidence: Confidence score (0-1)
            
        Returns:
            Confidence explanation
        """
        if confidence >= 0.9:
            return "High confidence - clear evidence in report"
        elif confidence >= 0.7:
            return "Good confidence - adequate information available"
        elif confidence >= 0.5:
            return "Moderate confidence - some uncertainty remains"
        else:
            return "Low confidence - limited information available"
    
    def _identify_limitations(self, data: Dict[str, any]) -> str:
        """Identify limitations in the staging analysis.
        
        Args:
            data: Report data dictionary
            
        Returns:
            Limitations text
        """
        limitations = []
        
        if data['t_stage'] == 'TX':
            limitations.append("• T stage could not be determined - insufficient tumor information")
        elif data['t_confidence'] < 0.7:
            limitations.append("• T stage has moderate uncertainty - consider additional imaging")
        
        if data['n_stage'] == 'NX':
            limitations.append("• N stage could not be determined - lymph node status unclear")
        elif data['n_confidence'] < 0.7:
            limitations.append("• N stage has moderate uncertainty - consider dedicated nodal imaging")
        
        if not data.get('user_response'):
            limitations.append("• Analysis based solely on original report - no additional clinical input")
        
        limitations.append("• M stage not assessed - requires dedicated metastatic workup")
        limitations.append("• Histologic confirmation assumed but not verified")
        
        return "\n".join(limitations) if limitations else "• No significant limitations identified"