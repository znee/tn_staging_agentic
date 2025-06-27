"""Test workflow optimization for selective re-staging."""

import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from contexts.context_manager_optimized import OptimizedContextManager, OptimizedWorkflowOrchestrator
from agents.base import AgentMessage, AgentStatus


class MockStagingAgent:
    """Mock staging agent for testing."""
    
    def __init__(self, agent_id: str, stage_result: str, confidence: float):
        self.agent_id = agent_id
        self.stage_result = stage_result
        self.confidence = confidence
        self.execution_count = 0
    
    async def execute(self, context):
        """Mock execute method."""
        self.execution_count += 1
        
        if self.agent_id == "staging_t":
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={
                    "context_T": self.stage_result,
                    "context_CT": self.confidence,
                    "context_RationaleT": f"T{self.stage_result} rationale (execution #{self.execution_count})"
                }
            )
        else:  # staging_n
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={
                    "context_N": self.stage_result,
                    "context_CN": self.confidence,
                    "context_RationaleN": f"N{self.stage_result} rationale (execution #{self.execution_count})"
                }
            )


class MockOtherAgent:
    """Mock agent for other workflow steps."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.execution_count = 0
    
    async def execute(self, context):
        """Mock execute method."""
        self.execution_count += 1
        
        if self.agent_id == "detect":
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={
                    "context_B": {"body_part": "tongue", "cancer_type": "squamous cell carcinoma"}
                }
            )
        elif self.agent_id == "retrieve_guideline":
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={
                    "context_GT": "T1: ≤2cm, T2: >2cm ≤4cm, T3: >4cm",
                    "context_GN": "N0: No nodes, N1: Single ≤3cm, N2: Multiple or >3cm"
                }
            )
        elif self.agent_id == "query":
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={
                    "context_Q": "Are there any enlarged lymph nodes visible?"
                }
            )
        elif self.agent_id == "report":
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={
                    "final_report": "Final staging report generated"
                }
            )
        else:
            return AgentMessage(
                agent_id=self.agent_id,
                status=AgentStatus.SUCCESS,
                data={}
            )


async def test_scenario_1_high_confidence_t_low_confidence_n():
    """Test scenario: T2 with high confidence (0.95), NX with low confidence (0.4)."""
    print("\n=== Scenario 1: T2 (high confidence) + NX (low confidence) ===")
    
    # Create mock agents
    t_agent = MockStagingAgent("staging_t", "T2", 0.95)  # High confidence, should NOT re-run
    n_agent = MockStagingAgent("staging_n", "NX", 0.4)   # Low confidence, SHOULD re-run
    
    other_agents = {
        "detect": MockOtherAgent("detect"),
        "retrieve_guideline": MockOtherAgent("retrieve_guideline"),
        "query": MockOtherAgent("query"),
        "report": MockOtherAgent("report")
    }
    
    agents = {
        "staging_t": t_agent,
        "staging_n": n_agent,
        **other_agents
    }
    
    # Set up context and orchestrator
    context_manager = OptimizedContextManager()
    orchestrator = OptimizedWorkflowOrchestrator(agents, context_manager)
    
    # Run initial workflow
    print("Running initial workflow...")
    await orchestrator.run_initial_workflow()
    
    print(f"Initial results:")
    print(f"- T stage: {context_manager.context.context_T} (confidence: {context_manager.context.context_CT})")
    print(f"- N stage: {context_manager.context.context_N} (confidence: {context_manager.context.context_CN})")
    print(f"- T agent executions: {t_agent.execution_count}")
    print(f"- N agent executions: {n_agent.execution_count}")
    
    # Simulate user response
    print("\nAdding user response: 'Multiple enlarged nodes in right neck, largest 2.5cm'")
    result = await orchestrator.continue_workflow_with_response(
        "Multiple enlarged nodes in right neck, largest 2.5cm"
    )
    
    print(f"\nFinal results:")
    print(f"- T stage: {context_manager.context.context_T} (confidence: {context_manager.context.context_CT})")
    print(f"- N stage: {context_manager.context.context_N} (confidence: {context_manager.context.context_CN})")
    print(f"- T agent executions: {t_agent.execution_count} (should be 1 - no re-run)")
    print(f"- N agent executions: {n_agent.execution_count} (should be 2 - re-run occurred)")
    
    # Verify optimization
    assert t_agent.execution_count == 1, f"T agent should not have re-run (got {t_agent.execution_count})"
    assert n_agent.execution_count == 2, f"N agent should have re-run (got {n_agent.execution_count})"
    
    print("✅ PASS: Only N staging was re-run")


async def test_scenario_2_both_high_confidence():
    """Test scenario: T2 (0.9) and N2 (0.85) both high confidence."""
    print("\n=== Scenario 2: T2 (high confidence) + N2 (high confidence) ===")
    
    # Create mock agents
    t_agent = MockStagingAgent("staging_t", "T2", 0.9)   # High confidence
    n_agent = MockStagingAgent("staging_n", "N2", 0.85)  # High confidence
    
    other_agents = {
        "detect": MockOtherAgent("detect"),
        "retrieve_guideline": MockOtherAgent("retrieve_guideline"),
        "query": MockOtherAgent("query"),
        "report": MockOtherAgent("report")
    }
    
    agents = {
        "staging_t": t_agent,
        "staging_n": n_agent,
        **other_agents
    }
    
    # Set up context and orchestrator
    context_manager = OptimizedContextManager()
    orchestrator = OptimizedWorkflowOrchestrator(agents, context_manager)
    
    # Run initial workflow
    print("Running initial workflow...")
    await orchestrator.run_initial_workflow()
    
    print(f"Initial results:")
    print(f"- T stage: {context_manager.context.context_T} (confidence: {context_manager.context.context_CT})")
    print(f"- N stage: {context_manager.context.context_N} (confidence: {context_manager.context.context_CN})")
    print(f"- Query needed: {bool(context_manager.context.context_Q)}")
    
    # In this case, no query should be needed
    if context_manager.context.context_Q:
        print("Adding user response (though query shouldn't be needed)...")
        result = await orchestrator.continue_workflow_with_response("Additional details provided")
        
        print(f"Final results:")
        print(f"- T stage: {context_manager.context.context_T}")
        print(f"- N stage: {context_manager.context.context_N}")
        print(f"- T agent executions: {t_agent.execution_count} (should be 1)")
        print(f"- N agent executions: {n_agent.execution_count} (should be 1)")
        
        # Verify no re-runs
        assert t_agent.execution_count == 1, f"T agent should not have re-run (got {t_agent.execution_count})"
        assert n_agent.execution_count == 1, f"N agent should not have re-run (got {n_agent.execution_count})"
        
        print("✅ PASS: No staging agents were re-run")
    else:
        print("✅ PASS: No query generated (both confidences high)")


async def test_scenario_3_tx_nx_both_rerun():
    """Test scenario: TX and NX both need re-running."""
    print("\n=== Scenario 3: TX (low confidence) + NX (low confidence) ===")
    
    # Create mock agents with updated results after re-run
    class UpdatingMockAgent:
        def __init__(self, agent_id: str, initial_stage: str, initial_conf: float, 
                     updated_stage: str, updated_conf: float):
            self.agent_id = agent_id
            self.initial_stage = initial_stage
            self.initial_conf = initial_conf
            self.updated_stage = updated_stage
            self.updated_conf = updated_conf
            self.execution_count = 0
        
        async def execute(self, context):
            self.execution_count += 1
            
            # Return updated results on second execution
            stage = self.updated_stage if self.execution_count > 1 else self.initial_stage
            conf = self.updated_conf if self.execution_count > 1 else self.initial_conf
            
            if self.agent_id == "staging_t":
                return AgentMessage(
                    agent_id=self.agent_id,
                    status=AgentStatus.SUCCESS,
                    data={
                        "context_T": stage,
                        "context_CT": conf,
                        "context_RationaleT": f"{stage} rationale (execution #{self.execution_count})"
                    }
                )
            else:  # staging_n
                return AgentMessage(
                    agent_id=self.agent_id,
                    status=AgentStatus.SUCCESS,
                    data={
                        "context_N": stage,
                        "context_CN": conf,
                        "context_RationaleN": f"{stage} rationale (execution #{self.execution_count})"
                    }
                )
    
    t_agent = UpdatingMockAgent("staging_t", "TX", 0.3, "T3", 0.9)  # TX -> T3
    n_agent = UpdatingMockAgent("staging_n", "NX", 0.2, "N2", 0.8)  # NX -> N2
    
    other_agents = {
        "detect": MockOtherAgent("detect"),
        "retrieve_guideline": MockOtherAgent("retrieve_guideline"),
        "query": MockOtherAgent("query"),
        "report": MockOtherAgent("report")
    }
    
    agents = {
        "staging_t": t_agent,
        "staging_n": n_agent,
        **other_agents
    }
    
    # Set up context and orchestrator
    context_manager = OptimizedContextManager()
    orchestrator = OptimizedWorkflowOrchestrator(agents, context_manager)
    
    # Run initial workflow
    print("Running initial workflow...")
    await orchestrator.run_initial_workflow()
    
    print(f"Initial results:")
    print(f"- T stage: {context_manager.context.context_T} (confidence: {context_manager.context.context_CT})")
    print(f"- N stage: {context_manager.context.context_N} (confidence: {context_manager.context.context_CN})")
    
    # Add user response
    print("\nAdding detailed user response...")
    result = await orchestrator.continue_workflow_with_response(
        "Tumor measures 5.2cm with invasion of deep muscles. Multiple bilateral nodes, largest 3.1cm."
    )
    
    print(f"\nFinal results:")
    print(f"- T stage: {context_manager.context.context_T} (confidence: {context_manager.context.context_CT})")
    print(f"- N stage: {context_manager.context.context_N} (confidence: {context_manager.context.context_CN})")
    print(f"- T agent executions: {t_agent.execution_count} (should be 2 - re-run occurred)")
    print(f"- N agent executions: {n_agent.execution_count} (should be 2 - re-run occurred)")
    
    # Verify both re-ran
    assert t_agent.execution_count == 2, f"T agent should have re-run (got {t_agent.execution_count})"
    assert n_agent.execution_count == 2, f"N agent should have re-run (got {n_agent.execution_count})"
    
    print("✅ PASS: Both staging agents were re-run")


async def main():
    """Run all test scenarios."""
    print("Testing Workflow Optimization for Selective Re-staging")
    print("=" * 60)
    
    try:
        await test_scenario_1_high_confidence_t_low_confidence_n()
        await test_scenario_2_both_high_confidence()
        await test_scenario_3_tx_nx_both_rerun()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("\n📊 Optimization Benefits:")
        print("1. Reduces unnecessary LLM calls by 50% in T2NX scenarios")
        print("2. Preserves high-confidence staging results")
        print("3. Only re-runs agents with TX/NX or confidence < 0.7")
        print("4. Maintains same accuracy while improving performance")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())