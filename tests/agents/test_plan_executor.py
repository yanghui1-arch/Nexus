"""Tests for the PlanExecutor and parallel tool execution functionality."""

import asyncio
import sys
import os

# Add the project root to the path to import src directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.base.plan_executor import (
    PlanExecutor,
    ExecutionPlan,
    ToolExecutionStatus,
    ToolExecutionResult,
    format_execution_results,
)


class TestToolExecutionResult:
    """Test ToolExecutionResult dataclass."""
    
    def test_creation(self):
        result = ToolExecutionResult(
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
            status=ToolExecutionStatus.SUCCESS,
            result={"data": "test"},
            execution_time_ms=100.0,
        )
        assert result.tool_name == "test_tool"
        assert result.status == ToolExecutionStatus.SUCCESS
        assert result.result == {"data": "test"}


class TestExecutionPlan:
    """Test ExecutionPlan functionality."""
    
    def test_add_step(self):
        plan = ExecutionPlan()
        plan.add_step("tool1", {"arg": 1})
        plan.add_step("tool2", {"arg": 2}, depends_on=[0])
        
        assert len(plan.steps) == 2
        assert plan.steps[0]["tool_name"] == "tool1"
        assert plan.steps[1]["depends_on"] == [0]
    
    def test_get_independent_steps(self):
        plan = ExecutionPlan()
        plan.add_step("tool1", {})
        plan.add_step("tool2", {}, depends_on=[0])
        plan.add_step("tool3", {})
        
        independent = plan.get_independent_steps()
        assert len(independent) == 2
        assert independent[0]["tool_name"] == "tool1"
        assert independent[1]["tool_name"] == "tool3"
    
    def test_get_steps_ready_to_run(self):
        plan = ExecutionPlan()
        plan.add_step("tool1", {})
        plan.add_step("tool2", {}, depends_on=[0])
        plan.add_step("tool3", {}, depends_on=[1])
        
        ready = plan.get_steps_ready_to_run([0])  # tool1 is done
        assert len(ready) == 1
        assert ready[0]["tool_name"] == "tool2"
        
        ready = plan.get_steps_ready_to_run([0, 1])  # tool1 and tool2 done
        assert len(ready) == 1
        assert ready[0]["tool_name"] == "tool3"


class TestPlanExecutor:
    """Test PlanExecutor functionality."""
    
    @pytest.fixture
    def mock_tool_kits(self):
        """Create mock tool kits for testing."""
        async def success_tool(**kwargs):
            return {"success": True, "data": kwargs}
        
        async def fail_tool(**kwargs):
            raise ValueError("Intentional failure")
        
        async def retry_then_succeed(**kwargs):
            # This simulates a tool that fails once then succeeds
            if not hasattr(retry_then_succeed, "call_count"):
                retry_then_succeed.call_count = 0
            retry_then_succeed.call_count += 1
            
            if retry_then_succeed.call_count < 2:
                raise ConnectionError("Temporary failure")
            return {"success": True}
        
        return {
            "success_tool": success_tool,
            "fail_tool": fail_tool,
            "retry_tool": retry_then_succeed,
        }
    
    @pytest.mark.asyncio
    async def test_execute_single_success(self, mock_tool_kits):
        executor = PlanExecutor(tool_kits=mock_tool_kits)
        plan = ExecutionPlan()
        plan.add_step("success_tool", {"test": "data"})
        
        results = await executor.execute_plan(plan)
        
        assert len(results) == 1
        assert results[0].status == ToolExecutionStatus.SUCCESS
        assert results[0].result["success"] is True
    
    @pytest.mark.asyncio
    async def test_execute_parallel_steps(self, mock_tool_kits):
        executor = PlanExecutor(tool_kits=mock_tool_kits)
        plan = ExecutionPlan()
        
        # Add independent steps
        plan.add_step("success_tool", {"id": 1})
        plan.add_step("success_tool", {"id": 2})
        plan.add_step("success_tool", {"id": 3})
        
        results = await executor.execute_plan(plan)
        
        assert len(results) == 3
        for result in results:
            assert result.status == ToolExecutionStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_execute_with_dependencies(self, mock_tool_kits):
        """Test that steps with dependencies execute in correct order."""
        execution_order = []
        
        async def tracking_tool(id, **kwargs):
            execution_order.append(id)
            return {"id": id}
        
        tool_kits = {"tracking_tool": tracking_tool}
        executor = PlanExecutor(tool_kits=tool_kits)
        plan = ExecutionPlan()
        
        # Step 1: no dependencies
        plan.add_step("tracking_tool", {"id": 1})
        # Step 2: depends on step 1
        plan.add_step("tracking_tool", {"id": 2}, depends_on=[0])
        # Step 3: depends on step 2
        plan.add_step("tracking_tool", {"id": 3}, depends_on=[1])
        
        results = await executor.execute_plan(plan)
        
        assert len(results) == 3
        assert execution_order == [1, 2, 3]  # Should execute in order
    
    @pytest.mark.asyncio
    async def test_execute_with_failure(self, mock_tool_kits):
        executor = PlanExecutor(tool_kits=mock_tool_kits, max_retries=0)
        plan = ExecutionPlan()
        plan.add_step("fail_tool", {})
        
        results = await executor.execute_plan(plan)
        
        assert len(results) == 1
        assert results[0].status == ToolExecutionStatus.FAILED
        assert "Intentional failure" in results[0].error
    
    @pytest.mark.asyncio
    async def test_execute_batch(self, mock_tool_kits):
        executor = PlanExecutor(tool_kits=mock_tool_kits)
        
        batch_calls = [
            {"tool_name": "success_tool", "args": {"id": 1}},
            {"tool_name": "success_tool", "args": {"id": 2}},
        ]
        
        results = await executor.execute_batch(batch_calls)
        
        assert len(results) == 2
        for result in results:
            assert result.status == ToolExecutionStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """Test that retries work correctly."""
        call_count = 0
        
        async def flaky_tool(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"Failure {call_count}")
            return {"success": True}
        
        tool_kits = {"flaky_tool": flaky_tool}
        executor = PlanExecutor(tool_kits=tool_kits, max_retries=3, retry_delay_ms=10)
        
        plan = ExecutionPlan()
        plan.add_step("flaky_tool", {})
        
        results = await executor.execute_plan(plan)
        
        assert len(results) == 1
        assert results[0].status == ToolExecutionStatus.SUCCESS
        assert results[0].retry_count == 2  # Failed twice, succeeded on 3rd try
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        executor = PlanExecutor(tool_kits={})
        plan = ExecutionPlan()
        plan.add_step("nonexistent_tool", {})
        
        results = await executor.execute_plan(plan)
        
        assert len(results) == 1
        assert results[0].status == ToolExecutionStatus.FAILED
        assert "not found" in results[0].error.lower()


class TestFormatExecutionResults:
    """Test result formatting functions."""
    
    def test_format_success_results(self):
        results = [
            ToolExecutionResult(
                tool_name="tool1",
                tool_args={},
                status=ToolExecutionStatus.SUCCESS,
                result={"data": "value"},
            ),
            ToolExecutionResult(
                tool_name="tool2",
                tool_args={},
                status=ToolExecutionStatus.FAILED,
                error="Something went wrong",
            ),
        ]
        
        formatted = format_execution_results(results)
        
        assert "✓ Step 1: tool1" in formatted
        assert "✗ Step 2: tool2" in formatted
        assert "data" in formatted
        assert "Something went wrong" in formatted
    
    def test_format_with_truncation(self):
        long_result = "x" * 2000
        results = [
            ToolExecutionResult(
                tool_name="tool1",
                tool_args={},
                status=ToolExecutionStatus.SUCCESS,
                result=long_result,
            ),
        ]
        
        formatted = format_execution_results(results)
        
        assert "truncated" in formatted
        assert len(formatted) < len(long_result) + 500


class TestIntegration:
    """Integration tests for the complete execution flow."""
    
    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self):
        """Test execution with some successful and some failed tools."""
        async def success_tool(**kwargs):
            return {"status": "ok"}
        
        async def fail_tool(**kwargs):
            raise RuntimeError("Failed!")
        
        tool_kits = {
            "success_tool": success_tool,
            "fail_tool": fail_tool,
        }
        
        executor = PlanExecutor(tool_kits=tool_kits, max_retries=0)
        plan = ExecutionPlan()
        
        plan.add_step("success_tool", {})
        plan.add_step("fail_tool", {})
        plan.add_step("success_tool", {})
        
        results = await executor.execute_plan(plan)
        
        assert len(results) == 3
        assert results[0].status == ToolExecutionStatus.SUCCESS
        assert results[1].status == ToolExecutionStatus.FAILED
        assert results[2].status == ToolExecutionStatus.SUCCESS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
