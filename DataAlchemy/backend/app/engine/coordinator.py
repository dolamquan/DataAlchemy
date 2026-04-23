"""Coordinator layer that executes finalized plans step-by-step."""

from __future__ import annotations

from typing import Any

from app.engine.agent_events import publish_agent_event
from app.engine.agent_runtime import refresh_agent_after_recovery
from app.engine.agent_runtime import run_agent
from app.engine.schemas import PlanStep, ProjectPlanResponse
from app.services.agent_recovery_policy import get_recovery_policy
from app.services.agent_recovery_service import (
    build_recovery_request,
    run_docker_agent_recovery,
)


class Coordinator:
    """Execute a finalized project plan in-order using worker agents.

    This class intentionally runs sequentially today. It is structured so retry
    and parallel execution strategies can be added later with minimal changes.
    """

    async def execute_plan(
        self,
        *,
        plan: ProjectPlanResponse,
        dataset_id: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        completed_steps: list[str] = []
        results: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        dashboard_updates: list[dict[str, Any]] = []

        await publish_agent_event(
            session_id,
            {
                "type": "coordinator_started",
                "agent": "coordinator",
                "status": "in_progress",
                "message": f"Coordinator accepted {len(plan.plan)} planned step(s).",
                "plan": plan.model_dump(),
            },
        )

        for step in plan.plan:
            step_name = step.step
            payload = self._build_step_payload(dataset_id=dataset_id, step=step, prior_results=results)
            repair_attempts = 0

            while True:
                await publish_agent_event(
                    session_id,
                    {
                        "type": "step_retried" if repair_attempts else "step_started",
                        "step": step_name,
                        "agent": step.agent,
                        "status": "in_progress",
                        "message": (
                            f"Retrying {step_name} after repair attempt {repair_attempts}."
                            if repair_attempts
                            else f"{step.agent} started {step_name}."
                        ),
                    },
                )
                try:
                    step_result = await run_agent(step.agent, payload)
                except Exception as exc:
                    step_result = {
                        "status": "failed",
                        "result": {"error": f"Agent execution raised an exception: {str(exc)}"},
                        "artifacts": [],
                        "dashboard_updates": [
                            {
                                "step": step_name,
                                "agent": step.agent,
                                "status": "failed",
                                "message": f"Agent execution raised an exception: {str(exc)}",
                            }
                        ],
                    }

                if step_result.get("status") == "success":
                    break

                error_message = _event_message_from_step_result(step_result, fallback="Agent reported failure.")
                recovery_policy = get_recovery_policy(step.agent)
                if recovery_policy is None:
                    await publish_agent_event(
                        session_id,
                        {
                            "type": "step_failed",
                            "step": step_name,
                            "agent": step.agent,
                            "status": "failed",
                            "message": error_message,
                            "result": step_result.get("result"),
                            "artifacts": step_result.get("artifacts") or [],
                        },
                    )
                    await publish_agent_event(
                        session_id,
                        {
                            "type": "coordinator_failed",
                            "agent": "coordinator",
                            "status": "failed",
                            "message": f"Coordinator stopped at {step_name}.",
                        },
                    )
                    return {
                        "status": "failed",
                        "completed_steps": completed_steps,
                        "failed_step": step_name,
                        "results": results,
                        "artifacts": artifacts,
                        "dashboard_updates": dashboard_updates + (step_result.get("dashboard_updates") or []),
                    }

                if repair_attempts >= recovery_policy.max_attempts:
                    exhausted_message = (
                        f"{step.agent} failed after {recovery_policy.max_attempts} repair attempt(s): "
                        f"{error_message}"
                    )
                    await publish_agent_event(
                        session_id,
                        {
                            "type": "step_failed",
                            "step": step_name,
                            "agent": step.agent,
                            "status": "failed",
                            "message": exhausted_message,
                            "result": step_result.get("result"),
                            "artifacts": step_result.get("artifacts") or [],
                        },
                    )
                    await publish_agent_event(
                        session_id,
                        {
                            "type": "coordinator_failed",
                            "agent": "coordinator",
                            "status": "failed",
                            "message": f"Coordinator stopped at {step_name}; repair attempts exhausted.",
                        },
                    )
                    return {
                        "status": "failed",
                        "completed_steps": completed_steps,
                        "failed_step": step_name,
                        "results": results,
                        "artifacts": artifacts,
                        "dashboard_updates": dashboard_updates
                        + (step_result.get("dashboard_updates") or [])
                        + [
                            {
                                "step": step_name,
                                "agent": step.agent,
                                "status": "failed",
                                "message": exhausted_message,
                            }
                        ],
                    }

                repair_attempts += 1
                await publish_agent_event(
                    session_id,
                    {
                        "type": "repair_started",
                        "step": step_name,
                        "agent": step.agent,
                        "status": "in_progress",
                        "message": (
                            f"Starting Docker Agent repair attempt {repair_attempts}/"
                            f"{recovery_policy.max_attempts} for {step.agent}."
                        ),
                        "editable_files": list(recovery_policy.editable_files),
                    },
                )

                recovery_request = build_recovery_request(
                    policy=recovery_policy,
                    failed_step=step_name,
                    dataset_id=dataset_id,
                    error_message=error_message,
                    step_config=payload["config"],
                    prior_results=results,
                    attempt=repair_attempts,
                )
                recovery_result = run_docker_agent_recovery(recovery_request)

                if not recovery_result.success:
                    repair_message = recovery_result.error or "Docker Agent repair failed."
                    await publish_agent_event(
                        session_id,
                        {
                            "type": "repair_failed",
                            "step": step_name,
                            "agent": step.agent,
                            "status": "failed",
                            "message": repair_message,
                            "stdout": recovery_result.stdout,
                            "stderr": recovery_result.stderr,
                            "command": _display_command(recovery_result.command),
                        },
                    )
                    await publish_agent_event(
                        session_id,
                        {
                            "type": "coordinator_failed",
                            "agent": "coordinator",
                            "status": "failed",
                            "message": f"Coordinator stopped at {step_name}; repair failed.",
                        },
                    )
                    return {
                        "status": "failed",
                        "completed_steps": completed_steps,
                        "failed_step": step_name,
                        "results": results,
                        "artifacts": artifacts,
                        "dashboard_updates": dashboard_updates
                        + (step_result.get("dashboard_updates") or [])
                        + [
                            {
                                "step": step_name,
                                "agent": step.agent,
                                "status": "failed",
                                "message": repair_message,
                                "recovery": {
                                    "success": recovery_result.success,
                                    "retryable": recovery_result.retryable,
                                    "stdout": recovery_result.stdout,
                                    "stderr": recovery_result.stderr,
                                    "command": _display_command(recovery_result.command),
                                    "returncode": recovery_result.returncode,
                                },
                            }
                        ],
                    }

                try:
                    refresh_agent_after_recovery(step.agent)
                except Exception as exc:
                    await publish_agent_event(
                        session_id,
                        {
                            "type": "repair_failed",
                            "step": step_name,
                            "agent": step.agent,
                            "status": "failed",
                            "message": f"Repair completed, but agent reload failed: {exc}",
                            "stdout": recovery_result.stdout,
                            "stderr": recovery_result.stderr,
                            "command": _display_command(recovery_result.command),
                        },
                    )
                    return {
                        "status": "failed",
                        "completed_steps": completed_steps,
                        "failed_step": step_name,
                        "results": results,
                        "artifacts": artifacts,
                        "dashboard_updates": dashboard_updates
                        + (step_result.get("dashboard_updates") or [])
                        + [
                            {
                                "step": step_name,
                                "agent": step.agent,
                                "status": "failed",
                                "message": f"Repair completed, but agent reload failed: {exc}",
                            }
                        ],
                    }

                await publish_agent_event(
                    session_id,
                    {
                        "type": "repair_succeeded",
                        "step": step_name,
                        "agent": step.agent,
                        "status": "completed",
                        "message": (
                            f"Docker Agent repair attempt {repair_attempts}/"
                            f"{recovery_policy.max_attempts} completed; retrying step."
                        ),
                        "stdout": recovery_result.stdout,
                        "stderr": recovery_result.stderr,
                        "command": _display_command(recovery_result.command),
                    },
                )

            completed_steps.append(step_name)
            results.append(
                {
                    "step": step_name,
                    "agent": step.agent,
                    "result": step_result.get("result"),
                }
            )
            artifacts.extend(step_result.get("artifacts") or [])
            dashboard_updates.extend(step_result.get("dashboard_updates") or [])
            await publish_agent_event(
                session_id,
                {
                    "type": "step_completed",
                    "step": step_name,
                    "agent": step.agent,
                    "status": "completed",
                    "message": _event_message_from_step_result(step_result, fallback=f"{step_name} completed."),
                    "result": step_result.get("result"),
                    "artifacts": step_result.get("artifacts") or [],
                    "dashboard_updates": step_result.get("dashboard_updates") or [],
                },
            )

        await publish_agent_event(
            session_id,
            {
                "type": "coordinator_completed",
                "agent": "coordinator",
                "status": "completed",
                "message": "Coordinator completed the plan.",
                "completed_steps": completed_steps,
                "artifacts": artifacts,
            },
        )
        return {
            "status": "success",
            "completed_steps": completed_steps,
            "failed_step": None,
            "results": results,
            "artifacts": artifacts,
            "dashboard_updates": dashboard_updates,
        }

    @staticmethod
    def _build_step_payload(*, dataset_id: str, step: PlanStep, prior_results: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "dataset_id": dataset_id,
            "step": step.step,
            "agent": step.agent,
            "config": step.config or {},
            "prior_results": prior_results,
        }


def _event_message_from_step_result(step_result: dict[str, Any], *, fallback: str) -> str:
    updates = step_result.get("dashboard_updates") or []
    if updates and isinstance(updates[0], dict) and updates[0].get("message"):
        return str(updates[0]["message"])

    result = step_result.get("result")
    if isinstance(result, dict):
        if result.get("message"):
            return str(result["message"])
        if result.get("error"):
            return str(result["error"])
        if result.get("chosen_model"):
            return f"Trained {result['chosen_model']}."
        if result.get("quality_score") is not None:
            return f"Quality score: {result['quality_score']}."

    return fallback


def _display_command(command: list[str]) -> list[str]:
    if not command:
        return []
    if len(command) <= 6:
        return command
    return command[:-1] + ["<repair-prompt>"]
