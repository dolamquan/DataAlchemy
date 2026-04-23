"""Policy for deciding which failed agent steps can self-repair."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentRecoveryPolicy:
    docker_agent_name: str
    editable_files: tuple[str, ...]
    max_attempts: int = 2


_POLICIES: dict[str, AgentRecoveryPolicy] = {
    "data_preprocessing_agent": AgentRecoveryPolicy(
        docker_agent_name="data_preprocessing_agent",
        editable_files=(
            "backend/app/agents/data_preprocessing_agent.py",
            "backend/configs/agents.yaml",
        ),
    ),
    "model_training_agent": AgentRecoveryPolicy(
        docker_agent_name="model_training_agent",
        editable_files=(
            "backend/app/agents/model_training_agent.py",
            "backend/configs/agents.yaml",
        ),
    ),
    "evaluation_agent": AgentRecoveryPolicy(
        docker_agent_name="evaluation_agent",
        editable_files=(
            "backend/app/agents/evaluation_agent.py",
            "backend/configs/agents.yaml",
        ),
    ),
}


def get_recovery_policy(agent_name: str) -> AgentRecoveryPolicy | None:
    """Return recovery policy for a repairable worker agent."""
    return _POLICIES.get(agent_name)


def resolve_editable_paths(project_root: Path, policy: AgentRecoveryPolicy) -> list[Path]:
    """Resolve editable files and verify they stay under project_root."""
    root = project_root.resolve()
    resolved: list[Path] = []

    for rel_path in policy.editable_files:
        path = (root / rel_path).resolve()
        if root != path and root not in path.parents:
            raise ValueError(f"Editable path escapes project root: {rel_path}")
        resolved.append(path)

    return resolved
