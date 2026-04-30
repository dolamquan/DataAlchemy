"""Conversational supervisor agent with in-memory session state."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.db.models import (
    cancel_execution_run,
    create_execution_run,
    get_execution_run_by_session_id,
    get_upload_record_by_file_id,
    get_upload_schema_by_file_id,
    list_execution_stage_events,
    user_can_access_execution_run,
)
from app.core.settings import UPLOAD_DIR
from app.engine.agent_events import clear_agent_event_history, publish_agent_event
from app.engine.coordinator import Coordinator
from app.engine.llm_client import call_supervisor_llm
from app.engine.registry import get_agent_config
from app.engine.schemas import PlanExecutionEstimate, PlanStep, ProjectPlanResponse, SupervisorResponse
from app.services.runtime_interrupt import clear_interrupt, request_interrupt

_WEEK_COLUMN_RE = re.compile(r"^week_(\d+)$", re.IGNORECASE)
_TARGET_NAMES = {
    "target",
    "label",
    "y",
    "class",
    "churn",
    "exited",
    "fraud",
    "price",
    "outcome",
    "survived",
    "default",
    "result",
    "score",
    "final_score",
}


# ========== Session Store ==========

_sessions: dict[str, dict[str, Any]] = {}
_execution_tasks: dict[str, asyncio.Task[Any]] = {}
# Key: session_id
# Value: {
#     "dataset_id": str,
#     "system_prompt": str,          # base prompt + schema context (built at session start)
#     "messages": list[dict],        # OpenAI messages format
#     "plan": ProjectPlanResponse | None,
#     "execution": dict | None,
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


def _supervisor_base_prompt(agent_config: dict[str, Any]) -> str:
    base_prompt = agent_config.get("instruction") or agent_config.get("system_prompt")
    if not isinstance(base_prompt, str) or not base_prompt.strip():
        raise KeyError("Supervisor agent config is missing 'instruction' or 'system_prompt'.")
    return base_prompt


def _supervisor_model(agent_config: dict[str, Any]) -> str:
    model = agent_config.get("model", "gpt-5.1")
    if not isinstance(model, str) or not model.strip():
        return "gpt-5.1"
    return model


def _supervisor_max_tokens(agent_config: dict[str, Any]) -> int:
    max_tokens = agent_config.get("max_tokens", 4096)
    if isinstance(max_tokens, int) and max_tokens > 0:
        return max_tokens
    return 4096


def _supervisor_temperature(agent_config: dict[str, Any]) -> float:
    temperature = agent_config.get("temperature", 0.2)
    if isinstance(temperature, (int, float)):
        return float(temperature)
    return 0.2


# ========== Core Logic ==========


def user_can_access_session(session_id: str, user_uid: str) -> bool:
    session = _sessions.get(session_id)
    if session is not None:
        return session.get("user_uid") == user_uid
    return user_can_access_execution_run(session_id, owner_uid=user_uid)


async def reset_user_runtime(user_uid: str) -> None:
    owned_session_ids = [session_id for session_id, session in _sessions.items() if session.get("user_uid") == user_uid]

    for session_id in owned_session_ids:
        request_interrupt(session_id)
        task = _execution_tasks.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    for session_id in owned_session_ids:
        cancel_execution_run(
            session_id,
            owner_uid=user_uid,
            reason="Coordinator run was interrupted by user reset.",
        )
        _sessions.pop(session_id, None)
        clear_agent_event_history(session_id)
        clear_interrupt(session_id)


async def start_session(*, dataset_id: str, user_message: str, user_uid: str) -> SupervisorResponse:
    """Create a new session, load schema, send user's request to LLM, return draft plan."""

    # Load agent config from registry
    agent_config = get_agent_config("supervisor")

    # Validate dataset exists
    record = get_upload_record_by_file_id(dataset_id, owner_uid=user_uid)
    if record is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Load schema profile
    schema_profile = get_upload_schema_by_file_id(dataset_id, owner_uid=user_uid)
    if schema_profile is None:
        raise HTTPException(status_code=404, detail="Schema profile not found for dataset")

    # Build full system prompt: base from agents.yaml + schema context
    base_prompt = _supervisor_base_prompt(agent_config)
    schema_text = format_schema_for_llm(schema_profile)
    full_system = _build_full_system_prompt(base_prompt, schema_text)

    session_id = _new_session_id()
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

    result = call_supervisor_llm(
        system_prompt=full_system,
        messages=messages,
        model=_supervisor_model(agent_config),
        max_tokens=_supervisor_max_tokens(agent_config),
        temperature=_supervisor_temperature(agent_config),
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

    _sessions[session_id] = {
        "user_uid": user_uid,
        "dataset_id": dataset_id,
        "system_prompt": full_system,
        "messages": messages,
        "plan": None,
        "execution": None,
        "finished": False,
        "agent_config": agent_config,
    }

    response = await _process_result(session_id, dataset_id, user_uid, result)

    _sessions[session_id]["plan"] = response.plan
    _sessions[session_id]["execution"] = response.execution
    _sessions[session_id]["finished"] = response.type == "final"

    return response


async def send_message(
    *,
    session_id: str,
    user_message: str,
    user_uid: str,
    dataset_id: str | None = None,
) -> SupervisorResponse:
    """Send a user message in an existing session, get back revised plan or final plan."""

    session = _sessions.get(session_id)
    if session is None:
        if dataset_id:
            return await start_session(dataset_id=dataset_id, user_message=user_message, user_uid=user_uid)
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("user_uid") != user_uid:
        raise HTTPException(status_code=403, detail="You do not have access to this session")
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
        model=_supervisor_model(agent_config),
        max_tokens=_supervisor_max_tokens(agent_config),
        temperature=_supervisor_temperature(agent_config),
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
    response = await _process_result(session_id, dataset_id, user_uid, result)

    session["plan"] = response.plan
    session["execution"] = response.execution
    if response.type == "final":
        session["finished"] = True

    return response


async def _process_result(
    session_id: str,
    dataset_id: str,
    user_uid: str,
    result: dict[str, Any],
) -> SupervisorResponse:
    """Convert an LLM tool call result into a SupervisorResponse."""

    if result["tool"] == "propose_plan":
        plan = _build_plan_response(dataset_id, user_uid, result["input"])
        return SupervisorResponse(
            session_id=session_id,
            type="proposal",
            message=result["input"].get("clarification"),
            plan=plan,
            execution=None,
        )

    if result["tool"] == "finalize_plan":
        plan = _build_plan_response(dataset_id, user_uid, result["input"])
        create_execution_run(
            owner_uid=user_uid,
            dataset_id=dataset_id,
            session_id=session_id,
            plan=plan.model_dump(),
            total_steps=len(plan.plan),
        )
        task = asyncio.create_task(_run_plan_execution(session_id=session_id, dataset_id=dataset_id, plan=plan))
        _execution_tasks[session_id] = task
        estimate_summary = plan.execution_estimate.summary if plan.execution_estimate else None
        return SupervisorResponse(
            session_id=session_id,
            type="final",
            message=(
                f"Plan confirmed. Live execution is starting now. {estimate_summary}"
                if estimate_summary
                else "Plan confirmed. Live execution is starting now."
            ),
            plan=plan,
            execution=None,
        )

    raise RuntimeError(f"Unexpected tool: {result['tool']}")


def _build_plan_response(
    dataset_id: str,
    user_uid: str,
    tool_input: dict[str, Any],
) -> ProjectPlanResponse:
    """Validate and convert the LLM's function output into a ProjectPlanResponse."""
    target_column = _infer_plan_target_column(dataset_id, tool_input["user_goal"], user_uid)
    steps = [
        PlanStep(
            step=s["step"],
            agent=_normalize_step_agent(s["step"], s.get("agent"), tool_input["user_goal"]),
            status="pending",
            config=_normalize_step_config(
                s.get("config"),
                _normalize_step_agent(s["step"], s.get("agent"), tool_input["user_goal"]),
                tool_input["user_goal"],
                target_column,
            ),
        )
        for s in tool_input["steps"]
    ]

    plan = ProjectPlanResponse(
        dataset_id=dataset_id,
        user_goal=tool_input["user_goal"],
        summary=tool_input["summary"],
        plan=steps,
        execution_estimate=_estimate_plan_execution(
            dataset_id=dataset_id,
            user_uid=user_uid,
            user_goal=tool_input["user_goal"],
            steps=steps,
        ),
    )
    return plan


def _estimate_plan_execution(
    *,
    dataset_id: str,
    user_uid: str,
    user_goal: str,
    steps: list[PlanStep],
) -> PlanExecutionEstimate | None:
    if not steps:
        return None

    schema_profile = get_upload_schema_by_file_id(dataset_id, owner_uid=user_uid) or {}
    columns = schema_profile.get("columns", [])
    n_features = max(len(columns) - 1, 1)
    n_rows = _estimate_dataset_rows(dataset_id, user_uid, schema_profile)

    preprocess_seconds = 0
    training_seconds_low: int | None = None
    training_seconds_high: int | None = None
    evaluation_seconds = 0
    report_seconds = 0

    if any(step.agent == "data_preprocessing_agent" for step in steps):
        preprocess_seconds = max(5, min(45, int(n_rows / 250)))

    if any(step.agent == "model_training_agent" for step in steps):
        training_seconds_low, training_seconds_high = _estimate_training_runtime_range(
            user_goal=user_goal,
            n_rows=n_rows,
            n_features=n_features,
        )

    if any(step.agent == "evaluation_agent" for step in steps):
        evaluation_seconds = max(5, min(30, int(n_rows / 500)))

    if any(step.agent == "report_agent" for step in steps):
        report_seconds = 10

    total_low = preprocess_seconds + (training_seconds_low or 0) + evaluation_seconds + report_seconds
    total_high = preprocess_seconds + (training_seconds_high or 0) + evaluation_seconds + report_seconds

    if total_low <= 0 and total_high <= 0:
        total_low = 5
        total_high = 15

    summary_parts = [f"Expected runtime: {_format_runtime_range(total_low, total_high)}."]
    if training_seconds_low is not None and training_seconds_high is not None:
        summary_parts.append(
            f"Model training should take about {_format_runtime_range(training_seconds_low, training_seconds_high)}."
        )
    summary_parts.append(
        f"Estimate based on roughly {n_rows:,} row(s), {n_features} feature column(s), and the planned agents."
    )

    return PlanExecutionEstimate(
        total_seconds_low=total_low,
        total_seconds_high=total_high,
        training_seconds_low=training_seconds_low,
        training_seconds_high=training_seconds_high,
        summary=" ".join(summary_parts),
    )


def _estimate_dataset_rows(
    dataset_id: str,
    user_uid: str,
    schema_profile: dict[str, Any] | None,
) -> int:
    record = get_upload_record_by_file_id(dataset_id, owner_uid=user_uid)
    stored_path = record.get("stored_path") if record else None
    if isinstance(stored_path, str):
        try:
            csv_path = Path(stored_path)
            if csv_path.exists() and csv_path.is_file():
                line_count = 0
                with csv_path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        line_count += chunk.count(b"\n")
                if line_count > 1:
                    return max(line_count - 1, 1)
        except OSError:
            pass

    sampled = schema_profile.get("rows_sampled") if isinstance(schema_profile, dict) else None
    if isinstance(sampled, int) and sampled > 0:
        return sampled
    return 1_000


def _estimate_training_runtime_range(*, user_goal: str, n_rows: int, n_features: int) -> tuple[int, int]:
    if n_rows < 20:
        n_trials = 5
    elif n_rows < 1_000:
        n_trials = 50
    elif n_rows < 10_000:
        n_trials = 30
    elif n_rows < 100_000:
        n_trials = 15
    else:
        n_trials = 10

    if n_rows < 1_000:
        candidate_seconds = [60, 90]
    elif n_rows < 10_000:
        candidate_seconds = [90, 90, 120]
    else:
        candidate_seconds = [120, 120]

    hpo_seconds = sum(candidate_seconds)
    final_fit_low = max(10, min(45, int((n_rows * max(n_features, 1)) / 50_000)))
    final_fit_high = max(final_fit_low + 15, min(120, final_fit_low * 3))

    if user_goal == "evaluate_model":
        final_fit_low = max(5, final_fit_low // 2)
        final_fit_high = max(15, final_fit_high // 2)

    trial_multiplier_low = 0.75 if n_trials <= 15 else 0.9
    trial_multiplier_high = 1.0 if n_trials <= 15 else 1.2

    low = int(max(45, hpo_seconds * trial_multiplier_low + final_fit_low))
    high = int(max(low + 30, hpo_seconds * trial_multiplier_high + final_fit_high))
    return low, high


def _format_runtime_range(low_seconds: int, high_seconds: int) -> str:
    if low_seconds <= 0 and high_seconds <= 0:
        return "under a minute"

    if abs(high_seconds - low_seconds) <= 15:
        midpoint = round((low_seconds + high_seconds) / 2)
        return _format_duration(midpoint)

    return f"{_format_duration(low_seconds)} to {_format_duration(high_seconds)}"


def _format_duration(total_seconds: int) -> str:
    if total_seconds < 60:
        return f"{total_seconds}s"

    minutes, seconds = divmod(total_seconds, 60)
    if seconds == 0:
        return f"{minutes} min"
    if minutes >= 10:
        return f"{minutes} min"
    return f"{minutes} min {seconds}s"


async def _run_plan_execution(
    *,
    session_id: str,
    dataset_id: str,
    plan: ProjectPlanResponse,
) -> None:
    try:
        clear_interrupt(session_id)
        coordinator = Coordinator()
        execution = await coordinator.execute_plan(plan=plan, dataset_id=dataset_id, session_id=session_id)
        session = _sessions.get(session_id)
        if session is not None:
            session["execution"] = execution
    except asyncio.CancelledError:
        await publish_agent_event(
            session_id,
            {
                "type": "coordinator_failed",
                "agent": "coordinator",
                "status": "failed",
                "message": "Coordinator run was interrupted by user reset.",
            },
        )
        session = _sessions.get(session_id)
        if session is not None:
            session["execution"] = {
                "status": "failed",
                "completed_steps": [],
                "failed_step": None,
                "results": [],
                "artifacts": [],
                "dashboard_updates": [
                    {
                        "step": None,
                        "agent": "coordinator",
                        "status": "failed",
                        "message": "Coordinator run was interrupted by user reset.",
                    }
                ],
            }
        raise
    except Exception as exc:
        await publish_agent_event(
            session_id,
            {
                "type": "coordinator_failed",
                "agent": "coordinator",
                "status": "failed",
                "message": f"Coordinator crashed before completing the plan: {exc}",
            },
        )
        session = _sessions.get(session_id)
        if session is not None:
            session["execution"] = {
                "status": "failed",
                "completed_steps": [],
                "failed_step": None,
                "results": [],
                "artifacts": [],
                "dashboard_updates": [
                    {
                        "step": None,
                        "agent": "coordinator",
                        "status": "failed",
                        "message": f"Coordinator crashed before completing the plan: {exc}",
                    }
                ],
            }
    finally:
        _execution_tasks.pop(session_id, None)
        clear_interrupt(session_id)


def _normalize_step_agent(step_name: str, proposed_agent: Any, user_goal: str) -> str:
    """Keep the supervisor as planner only, then delegate execution steps."""
    normalized_step = step_name.lower()
    proposed = proposed_agent if isinstance(proposed_agent, str) else ""

    if normalized_step == "profile_dataset":
        return "supervisor"

    if proposed and proposed != "supervisor":
        return proposed

    if any(token in normalized_step for token in ("quality", "validate", "validation", "outlier", "duplicate", "null")):
        return "data_quality_agent"

    if any(
        token in normalized_step
        for token in ("preprocess", "prepare", "clean", "impute", "encode", "scale", "feature")
    ):
        return "data_preprocessing_agent"

    if any(token in normalized_step for token in ("evaluate", "metric", "score", "performance", "benchmark")):
        return "evaluation_agent"

    if any(token in normalized_step for token in ("train", "model", "fit", "predict")):
        return "model_training_agent"

    if any(token in normalized_step for token in ("visual", "chart", "plot", "eda", "distribution")):
        return "visualization_agent"

    if any(token in normalized_step for token in ("report", "summary", "explain", "share")):
        return "report_agent"

    if user_goal in {"train_model", "preprocess_and_train", "full_pipeline"}:
        return "data_preprocessing_agent"

    if user_goal == "visualize_data":
        return "visualization_agent"

    if user_goal == "schema_analysis":
        return "data_quality_agent"

    return "data_preprocessing_agent"


def _normalize_step_config(
    proposed_config: Any,
    agent_name: str,
    user_goal: str,
    inferred_target_column: str | None,
) -> dict[str, Any] | None:
    config = dict(proposed_config) if isinstance(proposed_config, dict) else {}
    ml_goal = user_goal in {"train_model", "preprocess_and_train", "full_pipeline", "evaluate_model"}
    target_aware_agents = {
        "data_preprocessing_agent",
        "data_quality_agent",
        "model_training_agent",
        "evaluation_agent",
    }

    if ml_goal and inferred_target_column and agent_name in target_aware_agents:
        config.setdefault("target_column", inferred_target_column)

    return config or None


def _infer_plan_target_column(dataset_id: str, user_goal: str, user_uid: str) -> str | None:
    if user_goal not in {"train_model", "preprocess_and_train", "full_pipeline", "evaluate_model"}:
        return None

    schema_profile = get_upload_schema_by_file_id(dataset_id, owner_uid=user_uid)
    if not schema_profile:
        return _infer_target_from_file_header(dataset_id)

    columns = schema_profile.get("columns", [])
    names = [str(col.get("name", "")) for col in columns if col.get("name")]

    lower_to_name = {name.lower(): name for name in names}
    for target_name in _TARGET_NAMES:
        if target_name in lower_to_name:
            return lower_to_name[target_name]

    week_columns = [
        (int(match.group(1)), name)
        for name in names
        if (match := _WEEK_COLUMN_RE.match(name))
    ]
    if week_columns:
        return max(week_columns)[1]

    for col in columns:
        name = str(col.get("name", ""))
        dtype = str(col.get("inferred_dtype", ""))
        unique = col.get("unique_count", 0)
        if dtype in {"integer", "float"} and unique == 2:
            return name

    for col in columns:
        name = str(col.get("name", ""))
        dtype = str(col.get("inferred_dtype", ""))
        unique = col.get("unique_count", 0)
        non_null = col.get("non_null_count", 0)
        if dtype in {"integer", "categorical", "string"} and 2 <= unique <= 10 and non_null > 0:
            return name

    return None


def _infer_target_from_file_header(dataset_id: str) -> str | None:
    candidates = [
        UPLOAD_DIR / dataset_id,
        UPLOAD_DIR / f"{dataset_id}.csv",
    ]

    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        try:
            first_line = path.read_text(encoding="utf-8-sig").splitlines()[0]
        except (OSError, IndexError, UnicodeDecodeError):
            continue

        names = [name.strip() for name in first_line.split(",") if name.strip()]
        lower_to_name = {name.lower(): name for name in names}
        for target_name in _TARGET_NAMES:
            if target_name in lower_to_name:
                return lower_to_name[target_name]

        week_columns = [
            (int(match.group(1)), name)
            for name in names
            if (match := _WEEK_COLUMN_RE.match(name))
        ]
        if week_columns:
            return max(week_columns)[1]

    return None


def get_session_execution_status(*, session_id: str, user_uid: str) -> dict[str, Any] | None:
    run = get_execution_run_by_session_id(session_id, owner_uid=user_uid)
    if run is None:
        return None

    session = _sessions.get(session_id)
    execution = session.get("execution") if session and session.get("user_uid") == user_uid else None

    return {
        "session_id": run["session_id"],
        "dataset_id": run["dataset_id"],
        "status": run["status"],
        "current_step_index": run["current_step_index"],
        "current_step_name": run["current_step_name"],
        "progress": {
            "completed": run["completed_step_count"],
            "total": run["total_steps"],
        },
        "failed_step": run["failed_step_name"],
        "error_message": run["error_message"],
        "started_at": run["started_at"],
        "ended_at": run["ended_at"],
        "updated_at": run["updated_at"],
        "plan": run["plan"],
        "execution": execution,
    }


def get_session_execution_events(*, session_id: str, user_uid: str, limit: int = 250) -> list[dict[str, Any]]:
    return list_execution_stage_events(session_id, owner_uid=user_uid, limit=limit)
