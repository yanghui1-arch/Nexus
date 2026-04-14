"""Plan-Act-Observe-Reflect execution loop for Agent.

This module implements an improved execution flow that supports:
1. Parallel tool execution for independent operations
2. Error handling and retry mechanism
3. Plan refinement based on execution results
4. Structured error feedback with suggestions
"""

import asyncio
import json
from typing import Any, Dict, List, Callable, Coroutine, Optional
from dataclasses import dataclass, field
from enum import Enum

from src.logger import logger
from src.exception import (
    ToolExecutionError,
    ToolRetryableError,
)


class ToolExecutionStatus(Enum):
    """Status of a tool execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ToolExecutionResult:
    """Result of a single tool execution."""
    tool_name: str
    tool_args: Dict[str, Any]
    status: ToolExecutionStatus
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    retry_count: int = 0


@dataclass
class ExecutionPlan:
    """A plan consisting of multiple tool calls to be executed."""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    """Each step is a dict with 'tool_name', 'args', and optional 'depends_on'"""
    
    def add_step(self, tool_name: str, args: Dict[str, Any], depends_on: Optional[List[int]] = None):
        """Add a step to the plan."""
        self.steps.append({
            "tool_name": tool_name,
            "args": args,
            "depends_on": depends_on or [],
            "index": len(self.steps),
        })
    
    def get_independent_steps(self) -> List[Dict[str, Any]]:
        """Get steps that have no dependencies."""
        return [s for s in self.steps if not s["depends_on"]]
    
    def get_steps_ready_to_run(self, completed_indices: List[int]) -> List[Dict[str, Any]]:
        """Get steps whose dependencies are all completed."""
        ready = []
        for step in self.steps:
            if step["index"] not in completed_indices and step["index"] not in [s["index"] for s in ready]:
                if all(dep in completed_indices for dep in step["depends_on"]):
                    ready.append(step)
        return ready


class PlanExecutor:
    """Executes a plan with parallel tool execution and error handling."""
    
    def __init__(
        self,
        tool_kits: Dict[str, Callable],
        max_retries: int = 2,
        retry_delay_ms: float = 1000.0,
    ):
        self.tool_kits = tool_kits
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
    
    async def execute_plan(
        self,
        plan: ExecutionPlan,
        on_step_complete: Optional[Callable[[ToolExecutionResult], None]] = None,
    ) -> List[ToolExecutionResult]:
        """Execute a plan with parallel execution of independent steps.
        
        Args:
            plan: The execution plan
            on_step_complete: Callback for each completed step
            
        Returns:
            List of execution results in the order of plan steps
        """
        results: Dict[int, ToolExecutionResult] = {}
        completed_indices: List[int] = []
        
        # Execute steps in waves (all independent steps in parallel)
        while len(completed_indices) < len(plan.steps):
            ready_steps = plan.get_steps_ready_to_run(completed_indices)
            
            if not ready_steps:
                # No progress possible - likely a dependency issue
                remaining = [s["index"] for s in plan.steps if s["index"] not in completed_indices]
                logger.error(f"Cannot execute remaining steps due to unresolved dependencies: {remaining}")
                break
            
            # Execute ready steps in parallel
            tasks = [self._execute_step_with_retry(step) for step in ready_steps]
            step_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for step, result in zip(ready_steps, step_results):
                idx = step["index"]
                
                if isinstance(result, Exception):
                    execution_result = ToolExecutionResult(
                        tool_name=step["tool_name"],
                        tool_args=step["args"],
                        status=ToolExecutionStatus.FAILED,
                        error=str(result),
                    )
                else:
                    execution_result = result
                
                results[idx] = execution_result
                completed_indices.append(idx)
                
                if on_step_complete:
                    on_step_complete(execution_result)
        
        # Return results in order
        return [results[i] for i in range(len(plan.steps))]
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is potentially transient and worth retrying."""
        retryable_patterns = [
            "timeout",
            "connection",
            "temporary",
            "unavailable",
            "rate limit",
            "too many requests",
        ]
        error_str = str(error).lower()
        return any(pattern in error_str for pattern in retryable_patterns)
    
    def _format_structured_error(self, error: ToolExecutionError) -> str:
        """Format structured error with suggestions for LLM consumption."""
        error_dict = error.to_dict()
        lines = [
            f"Error Type: {error_dict['error_type']}",
            f"Message: {error_dict['error']}",
        ]
        if error_dict.get('suggestion'):
            lines.append(f"Suggestion: {error_dict['suggestion']}")
        return "\n".join(lines)
    
    async def _execute_step_with_retry(
        self,
        step: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a single step with retry logic and structured error handling."""
        tool_name = step["tool_name"]
        args = step["args"]
        
        for attempt in range(self.max_retries + 1):
            start_time = asyncio.get_event_loop().time()
            
            try:
                if tool_name not in self.tool_kits:
                    raise KeyError(f"Tool '{tool_name}' not found in tool kits")
                
                tool_callable = self.tool_kits[tool_name]
                
                # Execute the tool
                if asyncio.iscoroutinefunction(tool_callable):
                    result = await tool_callable(**args)
                else:
                    result = await asyncio.to_thread(tool_callable, **args)
                
                execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                return ToolExecutionResult(
                    tool_name=tool_name,
                    tool_args=args,
                    status=ToolExecutionStatus.SUCCESS,
                    result=result,
                    execution_time_ms=execution_time,
                    retry_count=attempt,
                )
                
            except ToolExecutionError as e:
                # Structured error from tool layer
                execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                # Check if this is a retryable error
                should_retry = (
                    attempt < self.max_retries and 
                    (isinstance(e, ToolRetryableError) or self._is_retryable_error(e))
                )
                
                if should_retry:
                    logger.warning(
                        f"Tool '{tool_name}' failed with {e.error_type} "
                        f"(attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {self.retry_delay_ms}ms..."
                    )
                    await asyncio.sleep(self.retry_delay_ms / 1000.0)
                else:
                    logger.error(
                        f"Tool '{tool_name}' failed after {self.max_retries + 1} attempts: {e}"
                    )
                    return ToolExecutionResult(
                        tool_name=tool_name,
                        tool_args=args,
                        status=ToolExecutionStatus.FAILED,
                        error=self._format_structured_error(e),
                        execution_time_ms=execution_time,
                        retry_count=attempt,
                    )
                    
            except Exception as e:
                execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                if attempt < self.max_retries and self._is_retryable_error(e):
                    logger.warning(
                        f"Tool '{tool_name}' failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {self.retry_delay_ms}ms..."
                    )
                    await asyncio.sleep(self.retry_delay_ms / 1000.0)
                else:
                    logger.error(f"Tool '{tool_name}' failed after {self.max_retries + 1} attempts: {e}")
                    return ToolExecutionResult(
                        tool_name=tool_name,
                        tool_args=args,
                        status=ToolExecutionStatus.FAILED,
                        error=str(e),
                        execution_time_ms=execution_time,
                        retry_count=attempt,
                    )
        
        # Should never reach here
        return ToolExecutionResult(
            tool_name=tool_name,
            tool_args=args,
            status=ToolExecutionStatus.FAILED,
            error="Unexpected execution path",
        )
    
    async def execute_batch(
        self,
        tool_calls: List[Dict[str, Any]],
        return_exceptions: bool = True,
    ) -> List[ToolExecutionResult]:
        """Execute a batch of tool calls in parallel.
        
        Args:
            tool_calls: List of dicts with 'tool_name' and 'args'
            return_exceptions: If True, exceptions are returned as failed results;
                              if False, exceptions are raised
                              
        Returns:
            List of execution results
        """
        tasks = []
        for call in tool_calls:
            step = {
                "tool_name": call["tool_name"],
                "args": call["args"],
                "index": 0,  # Not used in batch mode
                "depends_on": [],
            }
            tasks.append(self._execute_step_with_retry(step))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        if not return_exceptions:
            for result in results:
                if isinstance(result, Exception):
                    raise result
        
        # Convert exceptions to failed results
        processed_results = []
        for call, result in zip(tool_calls, results):
            if isinstance(result, Exception):
                processed_results.append(ToolExecutionResult(
                    tool_name=call["tool_name"],
                    tool_args=call["args"],
                    status=ToolExecutionStatus.FAILED,
                    error=str(result),
                ))
            else:
                processed_results.append(result)
        
        return processed_results


def format_execution_results(results: List[ToolExecutionResult]) -> str:
    """Format execution results for LLM consumption with structured feedback."""
    lines = []
    success_count = sum(1 for r in results if r.status == ToolExecutionStatus.SUCCESS)
    failed_count = len(results) - success_count
    
    # Summary header
    lines.append(f"Execution Summary: {success_count}/{len(results)} successful")
    if failed_count > 0:
        lines.append(f"⚠️  {failed_count} tool(s) failed - see details below")
    lines.append("")
    
    for i, result in enumerate(results, 1):
        status_icon = "✓" if result.status == ToolExecutionStatus.SUCCESS else "✗"
        lines.append(f"{status_icon} Step {i}: {result.tool_name}")
        
        if result.status == ToolExecutionStatus.SUCCESS:
            if isinstance(result.result, dict):
                result_str = json.dumps(result.result, indent=2, ensure_ascii=False)
            else:
                result_str = str(result.result)
            # Truncate long results
            if len(result_str) > 1000:
                result_str = result_str[:1000] + "... [truncated]"
            lines.append(f"  Result: {result_str}")
        else:
            lines.append(f"  Error: {result.error}")
            lines.append(f"  Action needed: Review the error and decide whether to retry, modify the approach, or terminate.")
        
        if result.retry_count > 0:
            lines.append(f"  (Retried {result.retry_count} time(s))")
        
        lines.append("")  # Empty line between steps
    
    return "\n".join(lines)
