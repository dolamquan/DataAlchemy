"""Thin wrapper around the OpenAI chat completions API with function calling."""

from __future__ import annotations

import json
from typing import Any

from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI

from app.core.settings import OPENAI_API_KEY

# ---------- Shared step schema ----------

_AGENT_ENUM = [
    "supervisor",
    "data_preprocessing_agent",
    "data_quality_agent",
    "visualization_agent",
    "model_training_agent",
    "evaluation_agent",
    "report_agent",
]

_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "step": {"type": "string", "description": "Descriptive snake_case step name."},
        "agent": {
            "type": "string",
            "enum": _AGENT_ENUM,
            "description": "Agent responsible for this step. Use supervisor only for profile_dataset.",
        },
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


class LLMClientError(RuntimeError):
    """Raised when the supervisor LLM cannot be reached or configured."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _get_client() -> OpenAI:
    api_key = OPENAI_API_KEY.strip()
    if not api_key:
        raise LLMClientError("OPENAI_API_KEY is not configured", status_code=503)
    if any(char.isspace() for char in api_key):
        raise LLMClientError(
            "OPENAI_API_KEY contains whitespace; check your environment configuration",
            status_code=503,
        )

    return OpenAI(api_key=api_key)


def _llm_error_from_openai(exc: Exception) -> LLMClientError:
    if isinstance(exc, AuthenticationError):
        return LLMClientError(
            "OpenAI authentication failed. Check that OPENAI_API_KEY is valid and active.",
            status_code=503,
        )
    if isinstance(exc, APIConnectionError):
        return LLMClientError("Could not connect to OpenAI. Check your network connection.", status_code=503)
    if isinstance(exc, APIStatusError):
        detail = _openai_error_detail(exc)
        message = f"OpenAI request failed with status {exc.status_code}"
        if detail:
            message += f": {detail}"
        return LLMClientError(f"{message}.", status_code=502)

    return LLMClientError("OpenAI request failed.", status_code=502)


def _openai_error_detail(exc: APIStatusError) -> str:
    try:
        payload = exc.response.json()
    except ValueError:
        return ""

    error = payload.get("error")
    if not isinstance(error, dict):
        return ""

    message = error.get("message")
    if not isinstance(message, str):
        return ""

    return message[:300]


def _uses_gpt5_chat_params(model: str) -> bool:
    return model.startswith("gpt-5")


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
    request_kwargs: dict[str, Any] = {
        "model": model,
        "messages": full_messages,
        "tools": TOOLS,
        "tool_choice": "required",
        "max_completion_tokens": max_tokens,
    }

    if not _uses_gpt5_chat_params(model):
        request_kwargs["temperature"] = temperature

    try:
        response = client.chat.completions.create(**request_kwargs)
    except (AuthenticationError, APIConnectionError, APIStatusError) as exc:
        raise _llm_error_from_openai(exc) from exc

    message = response.choices[0].message

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        return {
            "tool": tool_call.function.name,
            "input": json.loads(tool_call.function.arguments),
        }

    raise RuntimeError("LLM response contained no tool calls")
