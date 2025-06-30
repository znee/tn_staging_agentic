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
        summary = self._generate_summary(report_data)
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
    
    def _generate_summary(self, data: Dict[str, any]) -> str:
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
{self._get_clinical_significance(data['t_stage'], data['n_stage'], data['body_part'])}"""
        
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
        prompt = f"""Generate clinical recommendations for a patient with {data['cancer_type']} of {data['body_part']} staged as {data['t_stage']}{data['n_stage']}.

Consider:
- T Stage: {data['t_stage']} (Confidence: {data['t_confidence']:.1%})
- N Stage: {data['n_stage']} (Confidence: {data['n_confidence']:.1%})
- Any limitations in staging

Provide evidence-based recommendations appropriate for the staging results."""

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

        # Fallback to manual generation
        try:
            recommendations_text = await self.llm_provider.generate(prompt + """

Provide recommendations for:
1. Additional imaging or procedures if needed
2. Multidisciplinary team consultation
3. Treatment planning considerations  
4. Follow-up recommendations""")
            
            return f"""RECOMMENDATIONS

{recommendations_text}

NEXT STEPS:
• Multidisciplinary team review recommended
• Consider additional imaging if staging confidence is low
• Confirm histologic diagnosis if not already obtained
• Assess performance status and comorbidities for treatment planning"""
            
        except Exception as e:
            self.logger.error(f"Failed to generate recommendations: {str(e)}")
            
            # Fallback recommendations
            return f"""RECOMMENDATIONS

ADDITIONAL WORKUP:
• Complete staging with M evaluation (chest/abdomen/pelvis CT or PET-CT)
• Pathologic confirmation if not already obtained
• Consider molecular/genetic testing as appropriate

MULTIDISCIPLINARY CONSULTATION:
• Oncology consultation for treatment planning
• Surgical consultation if resectable disease
• Radiation oncology consultation as indicated

FOLLOW-UP:
• Regular imaging surveillance per NCCN guidelines
• Monitor for disease progression or treatment response
• Address quality of life and supportive care needs"""

    async def _generate_recommendations_structured(self, prompt: str, data: Dict[str, any]) -> Dict[str, any]:
        """Generate recommendations using structured output."""
        result = await self.llm_provider.generate_structured(
            prompt,
            ReportResponse,
            temperature=0.1
        )
        
        # Ensure we have meaningful next steps
        if not result["next_steps"]:
            result["next_steps"] = [
                "Multidisciplinary team review recommended",
                "Consider additional imaging if staging confidence is low",
                "Confirm histologic diagnosis if not already obtained",
                "Assess performance status and comorbidities for treatment planning"
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
TN STAGING ANALYSIS REPORT
==============================================================================

Report Date: {data['timestamp']}
Session ID: {data['session_id']}
Analysis System: Radiologic TN Staging v2.0

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
    
    def _get_clinical_significance(self, t_stage: str, n_stage: str, body_part: str) -> str:
        """Get clinical significance text for staging combination.
        
        Args:
            t_stage: T stage
            n_stage: N stage
            body_part: Body part
            
        Returns:
            Clinical significance explanation
        """
        if t_stage == "TX" or n_stage == "NX":
            return "Staging incomplete - additional information needed for accurate prognosis and treatment planning."
        
        stage_map = {
            ("T1", "N0"): "Early-stage disease with excellent prognosis if properly treated.",
            ("T2", "N0"): "Localized disease with good prognosis and multiple treatment options.",
            ("T3", "N0"): "Locally advanced disease requiring multimodal treatment approach.",
            ("T4", "N0"): "Advanced local disease with significant treatment challenges.",
        }
        
        # Check for nodal involvement
        if "N1" in n_stage or "N2" in n_stage or "N3" in n_stage:
            return "Nodal involvement present - requires systemic therapy consideration and affects prognosis."
        
        return stage_map.get((t_stage, n_stage), "Staging results require clinical correlation for optimal treatment planning.")
    
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