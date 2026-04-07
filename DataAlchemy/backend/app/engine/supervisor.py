"""Conversational supervisor agent with in-memory session state."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException

from app.db.models import get_upload_record_by_file_id, get_upload_schema_by_file_id
from app.engine.llm_client import call_supervisor_llm
from app.engine.schemas import PlanStep, ProjectPlanResponse, SupervisorResponse


# ========== Session Store ==========

_sessions: dict[str, dict[str, Any]] = {}
# Key: session_id
# Value: {
#     "dataset_id": str,
#     "system_prompt": str,          # base prompt + schema context
#     "messages": list[dict],        # OpenAI messages format
#     "plan": ProjectPlanResponse | None,
#     "finished": bool,
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


# ========== System Prompt ==========

SYSTEM_PROMPT = """\
You are the DataAlchemy Supervisor, an expert data science project planner.

The user will tell you what they want to do with their dataset. Your job is to:
1. Read their request and the dataset schema profile provided below.
2. Immediately draft a concrete execution plan using the propose_plan function.
3. Present the plan with a short clarification asking if it looks right.
4. If the user requests changes, revise the plan and call propose_plan again.
5. If the user confirms the plan ("yes", "looks good", "go ahead", "confirm", etc.), call finalize_plan.

IMPORTANT RULES:
- Always respond with a function call. Never respond with plain text.
- Always draft a plan on the FIRST response. Do not ask questions before showing a plan.
- Keep plans between 3-6 steps.
- Always start with a profile_dataset step (agent: supervisor).
- For ML tasks, always include evaluation after training.
- Use the config field to pass step-specific parameters (target column, algorithm, metrics, drop columns, imputation strategy, etc.).
- Be concise in summaries and clarifications.
- When the user asks for changes, apply them precisely and re-propose.
- When the user confirms, call finalize_plan with the exact same plan.

Available agents for plan steps:
- supervisor: dataset profiling
- data_preprocessing_agent: cleaning, imputation, encoding, scaling, feature engineering
- data_quality_agent: data validation, integrity checks
- visualization_agent: EDA charts, distributions, correlations
- schema_agent: deep schema analysis, type recommendations
- model_training_agent: train ML models (classification, regression, clustering)
- evaluation_agent: metrics, cross-validation, feature importance
- report_agent: summary reports, findings documentation

Plan step naming conventions (use snake_case):
profile_dataset, preprocess_data, validate_data, generate_visualizations,
analyze_schema, prepare_training_data, train_model, evaluate_model,
generate_report, summarize_insights
"""


# ========== Core Logic ==========


def start_session(*, dataset_id: str, user_message: str) -> SupervisorResponse:
    """Create a new session, load schema, send user's request to LLM, return draft plan."""

    record = get_upload_record_by_file_id(dataset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    schema_profile = get_upload_schema_by_file_id(dataset_id)
    if schema_profile is None:
        raise HTTPException(status_code=404, detail="Schema profile not found for dataset")

    schema_text = format_schema_for_llm(schema_profile)
    full_system = SYSTEM_PROMPT + "\n## Dataset Schema Profile:\n" + schema_text

    session_id = _new_session_id()
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

    result = call_supervisor_llm(system_prompt=full_system, messages=messages)

    # Append assistant's response to history
    messages.append({
        "role": "assistant",
        "tool_calls": [{
            "id": "call_" + uuid.uuid4().hex[:8],
            "type": "function",
            "function": {
                "name": result["tool"],
                "arguments": __import__("json").dumps(result["input"]),
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
    }

    return response


def send_message(*, session_id: str, user_message: str) -> SupervisorResponse:
    """Send a user message in an existing session, get back revised plan or final plan."""

    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["finished"]:
        raise HTTPException(status_code=400, detail="Session already has a finalized plan")

    # The last message in history is an assistant tool_call.
    # OpenAI requires a tool result message before the next user message.
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
    )

    # Append assistant response to history
    session["messages"].append({
        "role": "assistant",
        "tool_calls": [{
            "id": "call_" + uuid.uuid4().hex[:8],
            "type": "function",
            "function": {
                "name": result["tool"],
                "arguments": __import__("json").dumps(result["input"]),
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
