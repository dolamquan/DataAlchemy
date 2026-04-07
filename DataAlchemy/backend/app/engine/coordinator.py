"""Coordinator layer that executes finalized plans step-by-step."""

from __future__ import annotations

from typing import Any

from app.engine.agent_runtime import run_agent
from app.engine.schemas import PlanStep, ProjectPlanResponse


class Coordinator:
    """Execute a finalized project plan in-order using worker agents.

    This class intentionally runs sequentially today. It is structured so retry
    and parallel execution strategies can be added later with minimal changes.
    """

    async def execute_plan(self, *, plan: ProjectPlanResponse, dataset_id: str) -> dict[str, Any]:
        completed_steps: list[str] = []
        results: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        dashboard_updates: list[dict[str, Any]] = []

        for step in plan.plan:
            step_name = step.step
            payload = self._build_step_payload(dataset_id=dataset_id, step=step)

            try:
                step_result = await run_agent(step.agent, payload)
            except Exception as exc:
                return {
                    "status": "failed",
                    "completed_steps": completed_steps,
                    "failed_step": step_name,
                    "results": results,
                    "artifacts": artifacts,
                    "dashboard_updates": dashboard_updates
                    + [
                        {
                            "step": step_name,
                            "agent": step.agent,
                            "status": "failed",
                            "message": f"Agent execution raised an exception: {str(exc)}",
                        }
                    ],
                }

            if step_result.get("status") != "success":
                return {
                    "status": "failed",
                    "completed_steps": completed_steps,
                    "failed_step": step_name,
                    "results": results,
                    "artifacts": artifacts,
                    "dashboard_updates": dashboard_updates + (step_result.get("dashboard_updates") or []),
                }

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

        return {
            "status": "success",
            "completed_steps": completed_steps,
            "failed_step": None,
            "results": results,
            "artifacts": artifacts,
            "dashboard_updates": dashboard_updates,
        }

    @staticmethod
    def _build_step_payload(*, dataset_id: str, step: PlanStep) -> dict[str, Any]:
        return {
            "dataset_id": dataset_id,
            "step": step.step,
            "agent": step.agent,
            "config": step.config or {},
        }
