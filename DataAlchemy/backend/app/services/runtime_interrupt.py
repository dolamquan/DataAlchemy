"""Best-effort runtime interruption flags for long-running agent work."""

from __future__ import annotations

_INTERRUPTED_SESSION_IDS: set[str] = set()


class UserInterruptRequested(RuntimeError):
    """Raised when a user requested the current session to stop."""


def request_interrupt(session_id: str | None) -> None:
    if session_id:
        _INTERRUPTED_SESSION_IDS.add(session_id)


def clear_interrupt(session_id: str | None) -> None:
    if session_id:
        _INTERRUPTED_SESSION_IDS.discard(session_id)


def is_interrupted(session_id: str | None) -> bool:
    return bool(session_id and session_id in _INTERRUPTED_SESSION_IDS)


def raise_if_interrupted(session_id: str | None, *, context: str = "Execution interrupted by user.") -> None:
    if is_interrupted(session_id):
        raise UserInterruptRequested(context)
