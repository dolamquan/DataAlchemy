"""Tests for Docker Agent recovery service helpers."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from app.services.agent_recovery_policy import get_recovery_policy
from app.services.agent_recovery_service import (
    AGENTS_CONFIG_DIR,
    AgentRecoveryRequest,
    build_docker_agent_command,
    build_docker_agent_runner_command,
    build_docker_ai_command,
    build_recovery_request,
    PROJECT_ROOT,
    repair_runner_cwd,
    repair_runner_name,
    resolve_docker_repair_command,
    run_docker_agent_recovery,
    truncate_text,
)


def test_build_docker_agent_command() -> None:
    command = build_docker_agent_command("model_training_agent", "repair me")

    assert command == [
        "docker",
        "agent",
        "run",
        "backend/configs/agents.yaml",
        "--agent",
        "model_training_agent",
        "repair me",
    ]


def test_build_docker_ai_command() -> None:
    command = build_docker_ai_command("repair me")

    assert command == ["docker", "ai", "repair me"]


def test_build_docker_agent_runner_command() -> None:
    command = build_docker_agent_runner_command("model_training_agent", "repair me")

    assert command == [
        "docker-agent",
        "run",
        "agents.yaml",
        "--agent",
        "model_training_agent",
        "--exec",
        "repair me",
    ]


def test_repair_runner_name() -> None:
    assert repair_runner_name(["docker-agent", "run"]) == "docker-agent"
    assert repair_runner_name(["docker", "agent", "run"]) == "docker agent"
    assert repair_runner_name(["docker", "ai", "prompt"]) == "docker ai"


def test_repair_runner_cwd() -> None:
    assert repair_runner_cwd(["docker-agent", "run", "agents.yaml"], PROJECT_ROOT) == AGENTS_CONFIG_DIR
    assert repair_runner_cwd(["docker", "ai", "prompt"], PROJECT_ROOT) == PROJECT_ROOT


def test_truncate_text() -> None:
    text = truncate_text("abcdef", max_chars=3)

    assert text.startswith("abc")
    assert "truncated 3 chars" in text


def test_build_recovery_request_from_policy() -> None:
    policy = get_recovery_policy("data_preprocessing_agent")
    assert policy is not None

    request = build_recovery_request(
        policy=policy,
        failed_step="prepare_data",
        dataset_id="dataset-1",
        error_message="boom",
        step_config={"target_column": "y"},
        prior_results=[],
        attempt=1,
    )

    assert request.docker_agent_name == "data_preprocessing_agent"
    assert request.failed_step == "prepare_data"
    assert "backend/app/agents/data_preprocessing_agent.py" in request.editable_files


def test_run_docker_agent_recovery_success(monkeypatch) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="patched", stderr="")

    monkeypatch.setattr(
        "app.services.agent_recovery_service.shutil.which",
        lambda name: "docker-agent" if name == "docker-agent" else "docker",
    )
    monkeypatch.setattr(subprocess, "run", fake_run)
    request = AgentRecoveryRequest(
        docker_agent_name="model_training_agent",
        failed_step="train_model",
        dataset_id="dataset-1",
        error_message="bad target",
        step_config={},
        prior_results=[],
        editable_files=("backend/app/agents/model_training_agent.py",),
        attempt=1,
        max_attempts=2,
    )

    result = run_docker_agent_recovery(request, project_root=PROJECT_ROOT, timeout_seconds=10)

    assert result.success is True
    assert result.retryable is True
    assert result.stdout == "patched"
    assert calls[0][0][:6] == ["docker-agent", "run", "agents.yaml", "--agent", "model_training_agent", "--exec"]
    assert calls[0][1]["cwd"] == AGENTS_CONFIG_DIR


def test_resolve_docker_repair_command_prefers_docker_ai_when_agent_missing(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        if command == ["docker", "--help"]:
            return SimpleNamespace(returncode=0, stdout="Usage: docker\nManagement Commands:\n  ai*  Docker AI Agent", stderr="")
        raise AssertionError("only docker --help should run during command resolution")

    monkeypatch.setattr(
        "app.services.agent_recovery_service.shutil.which",
        lambda name: None if name == "docker-agent" else "docker",
    )
    monkeypatch.setattr(subprocess, "run", fake_run)

    command, error = resolve_docker_repair_command("model_training_agent", "repair me")

    assert error is None
    assert command == ["docker", "ai", "repair me"]


def test_run_docker_agent_recovery_missing_command(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr("app.services.agent_recovery_service.shutil.which", lambda _: None)
    monkeypatch.setattr(subprocess, "run", fake_run)
    request = AgentRecoveryRequest(
        docker_agent_name="model_training_agent",
        failed_step="train_model",
        dataset_id="dataset-1",
        error_message="bad target",
        step_config={},
        prior_results=[],
        editable_files=("backend/app/agents/model_training_agent.py",),
        attempt=1,
        max_attempts=2,
    )

    result = run_docker_agent_recovery(request, project_root=PROJECT_ROOT, timeout_seconds=10)

    assert result.success is False
    assert result.retryable is False
    assert "neither the docker cli nor docker-agent executable" in (result.error or "").lower()


def test_run_docker_agent_recovery_uses_docker_ai_when_available(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        if command == ["docker", "--help"]:
            return SimpleNamespace(returncode=0, stdout="Usage: docker\nManagement Commands:\n  ai*  Docker AI Agent", stderr="")
        if command == ["docker", "ai", command[-1]]:
            return SimpleNamespace(returncode=0, stdout="patched with ai", stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(
        "app.services.agent_recovery_service.shutil.which",
        lambda name: None if name == "docker-agent" else "docker",
    )
    monkeypatch.setattr(subprocess, "run", fake_run)
    request = AgentRecoveryRequest(
        docker_agent_name="model_training_agent",
        failed_step="train_model",
        dataset_id="dataset-1",
        error_message="bad target",
        step_config={},
        prior_results=[],
        editable_files=("backend/app/agents/model_training_agent.py",),
        attempt=1,
        max_attempts=2,
    )

    result = run_docker_agent_recovery(request, project_root=PROJECT_ROOT, timeout_seconds=10)

    assert result.success is True
    assert result.retryable is True
    assert result.stdout == "patched with ai"
    assert result.command[:2] == ["docker", "ai"]
