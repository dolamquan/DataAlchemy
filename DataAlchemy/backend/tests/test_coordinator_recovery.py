"""Tests for coordinator Docker Agent recovery integration."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

from app.engine.coordinator import Coordinator
from app.engine.schemas import PlanStep, ProjectPlanResponse
from app.services.agent_recovery_service import AgentRecoveryResult


def _plan(agent: str = "model_training_agent") -> ProjectPlanResponse:
    return ProjectPlanResponse(
        dataset_id="dataset-1",
        user_goal="train_model",
        summary="Train a model",
        plan=[
            PlanStep(
                step="train_model",
                agent=agent,
                status="pending",
                config={"target_column": "target"},
            )
        ],
    )


def _failed_result(message: str = "boom") -> dict:
    return {
        "status": "failed",
        "result": {"error": message},
        "artifacts": [],
        "dashboard_updates": [
            {
                "agent": "model_training_agent",
                "step": "train_model",
                "status": "failed",
                "message": message,
            }
        ],
    }


def _success_result() -> dict:
    return {
        "status": "success",
        "result": {"chosen_model": "LogisticRegression"},
        "artifacts": [{"name": "trained_model.joblib"}],
        "dashboard_updates": [
            {
                "agent": "model_training_agent",
                "step": "train_model",
                "status": "completed",
                "message": "trained",
            }
        ],
    }


def _repair_success() -> AgentRecoveryResult:
    return AgentRecoveryResult(
        success=True,
        retryable=True,
        stdout="patched model_training_agent.py",
        stderr="",
        command=["docker", "agent", "run", "backend/configs/agents.yaml", "--agent", "model_training_agent", "prompt"],
        returncode=0,
    )


def _repair_failure() -> AgentRecoveryResult:
    return AgentRecoveryResult(
        success=False,
        retryable=False,
        stdout="",
        stderr="not installed",
        command=["docker", "agent", "run"],
        returncode=127,
        error="Docker Agent exited with code 127.",
    )


def test_successful_repair_retries_failed_step(monkeypatch) -> None:
    calls = {"run_agent": 0}

    async def fake_run_agent(agent_name, payload):
        calls["run_agent"] += 1
        return _failed_result() if calls["run_agent"] == 1 else _success_result()

    recovery = Mock(return_value=_repair_success())
    monkeypatch.setattr("app.engine.coordinator.run_agent", fake_run_agent)
    monkeypatch.setattr("app.engine.coordinator.run_docker_agent_recovery", recovery)
    monkeypatch.setattr("app.engine.coordinator.refresh_agent_after_recovery", lambda agent_name: None)

    result = asyncio.run(Coordinator().execute_plan(plan=_plan(), dataset_id="dataset-1"))

    assert result["status"] == "success"
    assert result["completed_steps"] == ["train_model"]
    assert calls["run_agent"] == 2
    assert recovery.call_count == 1


def test_failed_repair_stops_pipeline(monkeypatch) -> None:
    async def fake_run_agent(agent_name, payload):
        return _failed_result()

    recovery = Mock(return_value=_repair_failure())
    monkeypatch.setattr("app.engine.coordinator.run_agent", fake_run_agent)
    monkeypatch.setattr("app.engine.coordinator.run_docker_agent_recovery", recovery)

    result = asyncio.run(Coordinator().execute_plan(plan=_plan(), dataset_id="dataset-1"))

    assert result["status"] == "failed"
    assert result["failed_step"] == "train_model"
    assert recovery.call_count == 1
    assert "Docker Agent exited" in result["dashboard_updates"][-1]["message"]


def test_repair_attempts_stop_after_max_attempts(monkeypatch) -> None:
    calls = {"run_agent": 0}

    async def fake_run_agent(agent_name, payload):
        calls["run_agent"] += 1
        return _failed_result()

    recovery = Mock(return_value=_repair_success())
    monkeypatch.setattr("app.engine.coordinator.run_agent", fake_run_agent)
    monkeypatch.setattr("app.engine.coordinator.run_docker_agent_recovery", recovery)
    monkeypatch.setattr("app.engine.coordinator.refresh_agent_after_recovery", lambda agent_name: None)

    result = asyncio.run(Coordinator().execute_plan(plan=_plan(), dataset_id="dataset-1"))

    assert result["status"] == "failed"
    assert result["failed_step"] == "train_model"
    assert calls["run_agent"] == 3
    assert recovery.call_count == 2
    assert "repair attempt" in result["dashboard_updates"][-1]["message"]


def test_non_repairable_agent_does_not_invoke_recovery(monkeypatch) -> None:
    async def fake_run_agent(agent_name, payload):
        return _failed_result("quality failed")

    recovery = Mock(return_value=_repair_success())
    monkeypatch.setattr("app.engine.coordinator.run_agent", fake_run_agent)
    monkeypatch.setattr("app.engine.coordinator.run_docker_agent_recovery", recovery)

    result = asyncio.run(Coordinator().execute_plan(plan=_plan(agent="data_quality_agent"), dataset_id="dataset-1"))

    assert result["status"] == "failed"
    assert result["failed_step"] == "train_model"
    assert recovery.call_count == 0
