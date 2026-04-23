"""Run Docker Agent repair attempts for failed ML pipeline steps."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.agent_recovery_policy import AgentRecoveryPolicy, resolve_editable_paths

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
AGENTS_CONFIG_RELATIVE = "backend/configs/agents.yaml"
DEFAULT_TIMEOUT_SECONDS = 120
MAX_PROMPT_CHARS = 12_000
MAX_ERROR_CHARS = 4_000


@dataclass(frozen=True)
class AgentRecoveryRequest:
    docker_agent_name: str
    failed_step: str
    dataset_id: str
    error_message: str
    step_config: dict[str, Any]
    prior_results: list[dict[str, Any]]
    editable_files: tuple[str, ...]
    attempt: int
    max_attempts: int


@dataclass(frozen=True)
class AgentRecoveryResult:
    success: bool
    retryable: bool
    stdout: str
    stderr: str
    command: list[str]
    returncode: int | None = None
    error: str | None = None


def truncate_text(value: Any, max_chars: int = MAX_ERROR_CHARS) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return f"{text[:max_chars]}\n...[truncated {omitted} chars]"


def build_repair_prompt(request: AgentRecoveryRequest) -> str:
    payload = {
        "task": "Repair the failed DataAlchemy ML pipeline step and explain the patch in stdout.",
        "failed_step": request.failed_step,
        "dataset_id": request.dataset_id,
        "attempt": request.attempt,
        "max_attempts": request.max_attempts,
        "error_message": truncate_text(request.error_message),
        "step_config": request.step_config,
        "prior_results": request.prior_results,
        "editable_files": list(request.editable_files),
        "rules": [
            "Only edit the listed editable_files unless creating a directly required generated script/config.",
            "Do not refactor unrelated code.",
            "Prefer the smallest production-safe fix.",
            "Preserve existing public return shapes and config fields.",
            "After patching, explain changed files and why in stdout.",
        ],
    }
    prompt = json.dumps(payload, indent=2, default=str)
    return truncate_text(prompt, MAX_PROMPT_CHARS)


def build_docker_agent_command(
    docker_agent_name: str,
    prompt: str,
    *,
    config_path: str = AGENTS_CONFIG_RELATIVE,
) -> list[str]:
    return [
        "docker",
        "agent",
        "run",
        config_path,
        "--agent",
        docker_agent_name,
        prompt,
    ]


def build_recovery_request(
    *,
    policy: AgentRecoveryPolicy,
    failed_step: str,
    dataset_id: str,
    error_message: str,
    step_config: dict[str, Any],
    prior_results: list[dict[str, Any]],
    attempt: int,
) -> AgentRecoveryRequest:
    return AgentRecoveryRequest(
        docker_agent_name=policy.docker_agent_name,
        failed_step=failed_step,
        dataset_id=dataset_id,
        error_message=error_message,
        step_config=step_config,
        prior_results=prior_results,
        editable_files=policy.editable_files,
        attempt=attempt,
        max_attempts=policy.max_attempts,
    )


def run_docker_agent_recovery(
    request: AgentRecoveryRequest,
    *,
    project_root: Path = PROJECT_ROOT,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> AgentRecoveryResult:
    try:
        resolve_editable_paths(project_root, AgentRecoveryPolicy(
            docker_agent_name=request.docker_agent_name,
            editable_files=request.editable_files,
            max_attempts=request.max_attempts,
        ))
    except ValueError as exc:
        return AgentRecoveryResult(
            success=False,
            retryable=False,
            stdout="",
            stderr="",
            command=[],
            error=str(exc),
        )

    prompt = build_repair_prompt(request)
    command = build_docker_agent_command(request.docker_agent_name, prompt)

    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return AgentRecoveryResult(
            success=False,
            retryable=False,
            stdout="",
            stderr="",
            command=command,
            error=f"Docker Agent command could not start: {exc}",
        )
    except subprocess.TimeoutExpired as exc:
        return AgentRecoveryResult(
            success=False,
            retryable=False,
            stdout=truncate_text(exc.stdout or "", 2000),
            stderr=truncate_text(exc.stderr or "", 2000),
            command=command,
            error=f"Docker Agent repair timed out after {timeout_seconds}s.",
        )
    except OSError as exc:
        return AgentRecoveryResult(
            success=False,
            retryable=False,
            stdout="",
            stderr="",
            command=command,
            error=f"Docker Agent command failed to start: {exc}",
        )

    return AgentRecoveryResult(
        success=completed.returncode == 0,
        retryable=completed.returncode == 0,
        stdout=completed.stdout,
        stderr=completed.stderr,
        command=command,
        returncode=completed.returncode,
        error=None if completed.returncode == 0 else f"Docker Agent exited with code {completed.returncode}.",
    )
