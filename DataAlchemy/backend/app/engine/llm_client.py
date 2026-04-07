"""Thin wrapper around the OpenAI chat completions API with function calling."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.core.settings import OPENAI_API_KEY

# ---------- Shared step schema ----------

_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "step": {"type": "string", "description": "Descriptive snake_case step name."},
        "agent": {"type": "string", "description": "Agent responsible for this step."},
        "config": {
            "type": "object",
            "description": "Optional step-specific parameters (target column, algorithm, metrics, etc.).",
            "additionalProperties": True,
        },
    },
    "required": ["step", "agent"],
}

# ---------- User goal enum ----------

_USER_GOAL_ENUM = [
    "preprocess_only",
    "visualize_data",
    "schema_analysis",
    "train_model",
    "evaluate_model",
    "full_pipeline",
    "preprocess_and_train",
]

# ---------- Function definitions ----------

PROPOSE_PLAN_FUNCTION = {
    "type": "function",
    "function": {
        "name": "propose_plan",
        "description": (
            "Present a draft execution plan for the user to review. "
            "Include a clarification message asking if the plan looks right."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_goal": {
                    "type": "string",
                    "enum": _USER_GOAL_ENUM,
                    "description": "The high-level goal selected from the allowed options.",
                },
                "summary": {
                    "type": "string",
                    "description": "1-2 sentence summary of what the plan will accomplish.",
                },
                "steps": {
                    "type": "array",
                    "items": _STEP_SCHEMA,
                    "minItems": 1,
                    "description": "Ordered list of plan steps.",
                },
                "clarification": {
                    "type": "string",
                    "description": "Message to the user asking if the plan looks right or needs changes.",
                },
            },
            "required": ["user_goal", "summary", "steps", "clarification"],
        },
    },
}

FINALIZE_PLAN_FUNCTION = {
    "type": "function",
    "function": {
        "name": "finalize_plan",
        "description": (
            "Submit the final confirmed execution plan. "
            "Call this only when the user has approved the plan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_goal": {
                    "type": "string",
                    "enum": _USER_GOAL_ENUM,
                    "description": "The high-level goal selected from the allowed options.",
                },
                "summary": {
                    "type": "string",
                    "description": "1-2 sentence summary of what the plan will accomplish.",
                },
                "steps": {
                    "type": "array",
                    "items": _STEP_SCHEMA,
                    "minItems": 1,
                    "description": "Ordered list of plan steps.",
                },
            },
            "required": ["user_goal", "summary", "steps"],
        },
    },
}

TOOLS = [PROPOSE_PLAN_FUNCTION, FINALIZE_PLAN_FUNCTION]


# ---------- Client ----------


def _get_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY)


def call_supervisor_llm(
    *,
    system_prompt: str,
    messages: list[dict[str, Any]],
    model: str = "gpt-4o",
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """
    Call OpenAI with function calling forced.

    Returns dict:
        {"tool": "propose_plan", "input": {...}}
        or
        {"tool": "finalize_plan", "input": {...}}
    """
    client = _get_client()

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    response = client.chat.completions.create(
        model=model,
        messages=full_messages,
        tools=TOOLS,
        tool_choice="required",
        max_tokens=max_tokens,
        temperature=temperature,
    )

    message = response.choices[0].message

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        return {
            "tool": tool_call.function.name,
            "input": json.loads(tool_call.function.arguments),
        }

    raise RuntimeError("LLM response contained no tool calls")
