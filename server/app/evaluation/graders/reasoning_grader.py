"""Reasoning quality grader using LLM-as-Judge."""

from __future__ import annotations

from typing import Any, Optional

from app.evaluation.graders.base import GradingContext, GradeResult, LLMGrader
from app.evaluation.graders.openrouter_client import OpenRouterClient


class ReasoningQualityGrader(LLMGrader):
    """
    Evaluates the quality of an agent's reasoning.

    Assesses:
    - Problem identification accuracy
    - Logical approach to solutions
    - Consideration of alternatives
    - Solution appropriateness
    - Explanation clarity
    """

    name = "reasoning_quality"
    description = "Evaluates reasoning quality using LLM-as-judge"

    SYSTEM_PROMPT = """You are an expert evaluator specializing in assessing AI agent reasoning quality.

Your task is to evaluate how well an AI agent demonstrates sound reasoning when completing tasks.

Evaluate the response on these criteria:
1. **Problem Identification** (0-100): Did the agent correctly understand and identify the problem?
2. **Logical Approach** (0-100): Does the agent follow a logical, step-by-step approach?
3. **Alternatives Considered** (0-100): Did the agent consider multiple approaches before deciding?
4. **Solution Appropriateness** (0-100): Is the chosen solution appropriate for the problem?
5. **Explanation Clarity** (0-100): Is the reasoning clearly explained and easy to follow?

Provide your evaluation as a JSON object:
{
    "score": <weighted average 0-100>,
    "reasoning": "<detailed explanation of your assessment>",
    "criteria_scores": {
        "problem_identification": <score 0-100>,
        "logical_approach": <score 0-100>,
        "alternatives_considered": <score 0-100>,
        "solution_appropriateness": <score 0-100>,
        "explanation_clarity": <score 0-100>
    },
    "passed": <boolean, true if score >= 70>,
    "strengths": ["<list of strengths>"],
    "weaknesses": ["<list of areas for improvement>"]
}"""

    USER_PROMPT_TEMPLATE = """## Task Given to Agent
{task_prompt}

## Agent's Response
{agent_response}

## Expected Outcome (if available)
{expected_outcome}

## Additional Context
{additional_context}

Please evaluate the quality of the agent's reasoning in completing this task.
Focus on HOW the agent approached the problem, not just whether the final answer is correct."""

    def __init__(
        self,
        client: Optional[OpenRouterClient] = None,
        model: Optional[str] = None,
        passing_threshold: float = 70.0,
        weights: Optional[dict[str, float]] = None,
    ) -> None:
        """
        Initialize the reasoning quality grader.

        Args:
            client: OpenRouter client
            model: Model to use
            passing_threshold: Score required to pass
            weights: Custom weights for criteria (defaults to equal weights)
        """
        super().__init__(client, model, passing_threshold)
        self.weights = weights or {
            "problem_identification": 0.25,
            "logical_approach": 0.25,
            "alternatives_considered": 0.15,
            "solution_appropriateness": 0.25,
            "explanation_clarity": 0.10,
        }

    def _build_messages(self, context: GradingContext) -> list[dict[str, str]]:
        """Build messages with additional context."""
        additional = ""
        if context.additional_context:
            additional = "\n".join(
                f"- {k}: {v}" for k, v in context.additional_context.items()
            )
        else:
            additional = "None"

        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            task_prompt=context.task_prompt,
            agent_response=context.agent_response,
            expected_outcome=context.expected_outcome or "Not specified",
            additional_context=additional,
        )

        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]


class TaskCompletionGrader(LLMGrader):
    """
    Evaluates whether an agent successfully completed a task.

    Assesses:
    - Task understanding
    - Completion of all requirements
    - Accuracy of output
    - Handling of edge cases
    """

    name = "task_completion"
    description = "Evaluates task completion quality"

    SYSTEM_PROMPT = """You are an expert evaluator for AI agent task completion.

Your task is to determine how well an AI agent completed an assigned task.

Evaluate the response on these criteria:
1. **Task Understanding** (0-100): Did the agent correctly understand what was being asked?
2. **Requirements Met** (0-100): Were all task requirements addressed?
3. **Output Accuracy** (0-100): Is the output correct and accurate?
4. **Completeness** (0-100): Is the response complete or are parts missing?
5. **Edge Cases** (0-100): Were edge cases and potential issues handled?

Provide your evaluation as a JSON object:
{
    "score": <weighted average 0-100>,
    "reasoning": "<detailed explanation>",
    "criteria_scores": {
        "task_understanding": <score 0-100>,
        "requirements_met": <score 0-100>,
        "output_accuracy": <score 0-100>,
        "completeness": <score 0-100>,
        "edge_cases": <score 0-100>
    },
    "passed": <boolean, true if score >= 70>,
    "missing_requirements": ["<any requirements not addressed>"],
    "issues_found": ["<any issues or errors identified>"]
}"""

    USER_PROMPT_TEMPLATE = """## Task
{task_prompt}

## Expected Outcome
{expected_outcome}

## Agent's Response
{agent_response}

Please evaluate whether the agent successfully completed the task."""


class ToolProficiencyGrader(LLMGrader):
    """
    Evaluates how well an agent uses tools.

    Assesses:
    - Correct tool selection
    - Proper parameter usage
    - Error handling
    - Efficiency of tool use
    """

    name = "tool_proficiency"
    description = "Evaluates tool usage proficiency"

    SYSTEM_PROMPT = """You are an expert evaluator for AI agent tool usage.

Your task is to evaluate how well an AI agent uses tools to complete tasks.

Evaluate the tool usage on these criteria:
1. **Tool Selection** (0-100): Did the agent choose the right tools for the task?
2. **Parameter Accuracy** (0-100): Were tool parameters correct and appropriate?
3. **Error Handling** (0-100): Did the agent handle tool errors appropriately?
4. **Efficiency** (0-100): Were tools used efficiently without unnecessary calls?
5. **Sequencing** (0-100): Were tools called in a logical sequence?

Provide your evaluation as a JSON object:
{
    "score": <weighted average 0-100>,
    "reasoning": "<detailed explanation>",
    "criteria_scores": {
        "tool_selection": <score 0-100>,
        "parameter_accuracy": <score 0-100>,
        "error_handling": <score 0-100>,
        "efficiency": <score 0-100>,
        "sequencing": <score 0-100>
    },
    "passed": <boolean, true if score >= 70>,
    "tool_usage_summary": {
        "tools_used": ["<list of tools used>"],
        "unnecessary_calls": <count>,
        "errors_encountered": <count>,
        "errors_handled": <count>
    }
}"""

    USER_PROMPT_TEMPLATE = """## Task
{task_prompt}

## Agent's Response and Tool Usage
{agent_response}

## Available Tools
{available_tools}

## Tool Call Trace (if available)
{tool_trace}

Please evaluate the agent's proficiency in using tools."""

    def _build_messages(self, context: GradingContext) -> list[dict[str, str]]:
        """Build messages with tool-specific context."""
        available_tools = context.additional_context.get("available_tools", "Not specified")
        tool_trace = ""

        if context.agent_trace and "tool_calls" in context.agent_trace:
            tool_trace = "\n".join(
                f"- {call.get('tool_name')}: {call.get('parameters')}"
                for call in context.agent_trace["tool_calls"]
            )
        else:
            tool_trace = "Not available"

        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            task_prompt=context.task_prompt,
            agent_response=context.agent_response,
            available_tools=available_tools,
            tool_trace=tool_trace,
        )

        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]


class EfficiencyGrader(LLMGrader):
    """
    Evaluates the efficiency of an agent's task execution.

    Assesses:
    - Token usage efficiency
    - Step count efficiency
    - Time efficiency
    - Resource usage
    """

    name = "efficiency"
    description = "Evaluates execution efficiency"

    SYSTEM_PROMPT = """You are an expert evaluator for AI agent efficiency.

Your task is to evaluate how efficiently an AI agent completed a task.

Consider these aspects:
1. **Step Efficiency** (0-100): Did the agent take a minimal number of steps?
2. **Token Efficiency** (0-100): Was the response concise without being incomplete?
3. **Resource Usage** (0-100): Were computational resources used efficiently?
4. **Time to Solution** (0-100): Was the approach direct or roundabout?
5. **Redundancy** (0-100): Was there unnecessary repetition or duplication?

Provide your evaluation as a JSON object:
{
    "score": <weighted average 0-100>,
    "reasoning": "<detailed explanation>",
    "criteria_scores": {
        "step_efficiency": <score 0-100>,
        "token_efficiency": <score 0-100>,
        "resource_usage": <score 0-100>,
        "time_to_solution": <score 0-100>,
        "redundancy": <score 0-100>
    },
    "passed": <boolean, true if score >= 70>,
    "efficiency_metrics": {
        "estimated_steps": <number>,
        "optimal_steps": <number>,
        "redundant_operations": <count>
    }
}"""

    USER_PROMPT_TEMPLATE = """## Task
{task_prompt}

## Agent's Response
{agent_response}

## Execution Metrics (if available)
{execution_metrics}

Please evaluate the efficiency of the agent's task execution."""

    def _build_messages(self, context: GradingContext) -> list[dict[str, str]]:
        """Build messages with execution metrics."""
        metrics = ""
        if context.agent_trace:
            metrics_data = {
                "token_count": context.agent_trace.get("total_tokens"),
                "step_count": context.agent_trace.get("step_count"),
                "tool_call_count": len(context.agent_trace.get("tool_calls", [])),
                "duration_ms": context.agent_trace.get("duration_ms"),
            }
            metrics = "\n".join(f"- {k}: {v}" for k, v in metrics_data.items() if v)
        else:
            metrics = "Not available"

        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            task_prompt=context.task_prompt,
            agent_response=context.agent_response,
            execution_metrics=metrics,
        )

        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
