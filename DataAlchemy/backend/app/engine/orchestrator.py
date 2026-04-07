from __future__ import annotations

from typing import Any, Dict, List


class Coordinator:
    def __init__(self, agent_runtime):
        self.agent_runtime = agent_runtime

    async def execute_plan(
        self,
        plan: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        context = context or {}

        results: List[Dict[str, Any]] = []
        artifacts: List[Any] = []
        dashboard_updates: List[Dict[str, Any]] = []

        steps = plan.get("steps", [])
        if not steps:
            return {
                "status": "error",
                "message": "No steps found in finalized plan.",
                "completed_steps": [],
                "failed_step": None,
                "results": [],
                "artifacts": [],
                "dashboard_updates": [],
            }

        completed_steps = []

        for step in steps:
            step_name = step.get("step")
            agent_name = step.get("agent")
            step_config = step.get("config", {})

            payload = {
                "step": step_name,
                "agent": agent_name,
                "config": step_config,
                "context": context,
                "previous_results": results,
            }

            try:
                agent_result = await self.agent_runtime.run_agent(
                    agent_name=agent_name,
                    payload=payload,
                )

                results.append({
                    "step": step_name,
                    "agent": agent_name,
                    "result": agent_result,
                })
                completed_steps.append(step_name)

                if agent_result.get("artifacts"):
                    artifacts.extend(agent_result["artifacts"])

                if agent_result.get("dashboard_update"):
                    dashboard_updates.append(agent_result["dashboard_update"])

                # carry forward shared context
                context[step_name] = agent_result

                if agent_result.get("status") != "success":
                    return {
                        "status": "failed",
                        "completed_steps": completed_steps[:-1],
                        "failed_step": step_name,
                        "results": results,
                        "artifacts": artifacts,
                        "dashboard_updates": dashboard_updates,
                    }

            except Exception as e:
                return {
                    "status": "failed",
                    "completed_steps": completed_steps,
                    "failed_step": step_name,
                    "error": str(e),
                    "results": results,
                    "artifacts": artifacts,
                    "dashboard_updates": dashboard_updates,
                }

        return {
            "status": "success",
            "completed_steps": completed_steps,
            "failed_step": None,
            "results": results,
            "artifacts": artifacts,
            "dashboard_updates": dashboard_updates,
        }