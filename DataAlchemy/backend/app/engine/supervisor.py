"""Conversational supervisor agent with in-memory session state."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import HTTPException

from app.db.models import get_upload_record_by_file_id, get_upload_schema_by_file_id
from app.engine.llm_client import call_supervisor_llm
from app.engine.registry import get_agent_config
from app.engine.schemas import PlanStep, ProjectPlanResponse, SupervisorResponse


# ========== Session Store ==========

_sessions: dict[str, dict[str, Any]] = {}
# Key: session_id
# Value: {
#     "dataset_id": str,
#     "system_prompt": str,          # base prompt + schema context (built at session start)
#     "messages": list[dict],        # OpenAI messages format
#     "plan": ProjectPlanResponse | None,
#     "finished": bool,
#     "agent_config": dict,          # supervisor config from agents.yaml
# }


def _new_session_id() -> str:
    return uuid.uuid4().hex[:16]


# ========== Schema Formatting ==========


def format_schema_for_llm(schema_profile: dict[str, Any]) -> str:
    """
    Convert raw schema profile JSON into a concise text block for the LLM.
    Includes column names, types, null ratios, key stats, and top categorical values.
    Omits raw distribution bins to save tokens.
    """
    lines: list[str] = []

    file_name = schema_profile.get("file_name", "unknown")
    rows = schema_profile.get("rows_sampled", "?")
    total_cols = schema_profile.get("total_columns", "?")

    lines.append(f"Dataset: {file_name}")
    lines.append(f"Rows sampled: {rows} | Columns: {total_cols}")
    lines.append("")
    lines.append("Columns:")

    for col in schema_profile.get("columns", []):
        name = col.get("name", "?")
        dtype = col.get("inferred_dtype", "?")
        null_ratio = col.get("null_ratio", 0.0)
        unique = col.get("unique_count", "?")

        line = f"  - {name} ({dtype}, {null_ratio:.0%} null, {unique} unique)"

        stats = col.get("numeric_stats")
        if stats:
            line += (
                f" [min={stats['min']}, max={stats['max']}, "
                f"mean={stats['mean']:.2f}, median={stats['median']:.2f}]"
            )

        cat_vals = col.get("categorical_top_values", [])
        if cat_vals:
            top = cat_vals[:5]
            vals_str = ", ".join(f"{v['value']}({v['count']})" for v in top)
            line += f" [top: {vals_str}]"

        if dtype == "string":
            samples = col.get("sample_values", [])[:3]
            if samples:
                line += f" [samples: {', '.join(str(s) for s in samples)}]"

        lines.append(line)

    return "\n".join(lines)


def _build_full_system_prompt(base_prompt: str, schema_text: str) -> str:
    """Append the dataset schema profile to the base system prompt."""
    return base_prompt.rstrip() + "\n\n## Dataset Schema Profile:\n" + schema_text


# ========== Core Logic ==========


def start_session(*, dataset_id: str, user_message: str) -> SupervisorResponse:
    """Create a new session, load schema, send user's request to LLM, return draft plan."""

    # Load agent config from registry
    agent_config = get_agent_config("supervisor")

    # Validate dataset exists
    record = get_upload_record_by_file_id(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Load schema profile
    schema_profile = get_upload_schema_by_file_id(dataset_id)
    if schema_profile is None:
        raise HTTPException(status_code=404, detail="Schema profile not found for dataset")

    # Build full system prompt: base from agents.yaml + schema context
    base_prompt = agent_config["system_prompt"]
    schema_text = format_schema_for_llm(schema_profile)
    full_system = _build_full_system_prompt(base_prompt, schema_text)

    session_id = _new_session_id()
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

    result = call_supervisor_llm(
        system_prompt=full_system,
        messages=messages,
        model=agent_config["model"],
        max_tokens=agent_config["max_tokens"],
        temperature=agent_config.get("temperature", 0.2),
    )

    # Append assistant tool_call to history
    messages.append({
        "role": "assistant",
        "tool_calls": [{
            "id": "call_" + uuid.uuid4().hex[:8],
            "type": "function",
            "function": {
                "name": result["tool"],
                "arguments": json.dumps(result["input"]),
            },
        }],
    })

    response = _process_result(session_id, dataset_id, result)

    _sessions[session_id] = {
        "dataset_id": dataset_id,
        "system_prompt": full_system,
        "messages": messages,
        "plan": response.plan,
        "finished": response.type == "final",
        "agent_config": agent_config,
    }

    return response


def send_message(*, session_id: str, user_message: str) -> SupervisorResponse:
    """Send a user message in an existing session, get back revised plan or final plan."""

    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["finished"]:
        raise HTTPException(status_code=400, detail="Session already has a finalized plan")

    agent_config = session["agent_config"]

    # OpenAI requires a tool_result message after an assistant tool_call
    # before accepting the next user message
    last_msg = session["messages"][-1]
    if last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
        tool_call_id = last_msg["tool_calls"][0]["id"]
        session["messages"].append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": "Displayed to user. Awaiting their response.",
        })

    session["messages"].append({"role": "user", "content": user_message})

    result = call_supervisor_llm(
        system_prompt=session["system_prompt"],
        messages=session["messages"],
        model=agent_config["model"],
        max_tokens=agent_config["max_tokens"],
        temperature=agent_config.get("temperature", 0.2),
    )

    # Append assistant tool_call to history
    session["messages"].append({
        "role": "assistant",
        "tool_calls": [{
            "id": "call_" + uuid.uuid4().hex[:8],
            "type": "function",
            "function": {
                "name": result["tool"],
                "arguments": json.dumps(result["input"]),
            },
        }],
    })

    dataset_id = session["dataset_id"]
    response = _process_result(session_id, dataset_id, result)

    session["plan"] = response.plan
    if response.type == "final":
        session["finished"] = True

    return response


def _process_result(
    session_id: str,
    dataset_id: str,
    result: dict[str, Any],
) -> SupervisorResponse:
    """Convert an LLM tool call result into a SupervisorResponse."""

    if result["tool"] == "propose_plan":
        plan = _build_plan_response(dataset_id, result["input"])
        return SupervisorResponse(
            session_id=session_id,
            type="proposal",
            message=result["input"].get("clarification"),
            plan=plan,
        )

    if result["tool"] == "finalize_plan":
        plan = _build_plan_response(dataset_id, result["input"])
        return SupervisorResponse(
            session_id=session_id,
            type="final",
            message=None,
            plan=plan,
        )

    raise RuntimeError(f"Unexpected tool: {result['tool']}")


def _build_plan_response(
    dataset_id: str,
    tool_input: dict[str, Any],
) -> ProjectPlanResponse:
    """Validate and convert the LLM's function output into a ProjectPlanResponse."""
    steps = [
        PlanStep(
            step=s["step"],
            agent=s["agent"],
            status="pending",
            config=s.get("config"),
        )
        for s in tool_input["steps"]
    ]

    return ProjectPlanResponse(
        dataset_id=dataset_id,
        user_goal=tool_input["user_goal"],
        summary=tool_input["summary"],
        plan=steps,
    )
