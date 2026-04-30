"""Tests for supervisor config compatibility helpers."""

from __future__ import annotations

import pytest

from app.engine.supervisor import (
    _supervisor_base_prompt,
    _supervisor_max_tokens,
    _supervisor_model,
    _supervisor_temperature,
)


def test_supervisor_base_prompt_prefers_instruction() -> None:
    config = {
        "instruction": "Use the new config field.",
        "system_prompt": "Use the legacy field.",
    }

    assert _supervisor_base_prompt(config) == "Use the new config field."


def test_supervisor_base_prompt_falls_back_to_legacy_system_prompt() -> None:
    config = {"system_prompt": "Legacy prompt"}

    assert _supervisor_base_prompt(config) == "Legacy prompt"


def test_supervisor_base_prompt_requires_prompt_field() -> None:
    with pytest.raises(KeyError):
        _supervisor_base_prompt({})


def test_supervisor_runtime_defaults() -> None:
    assert _supervisor_model({}) == "gpt-5.1"
    assert _supervisor_max_tokens({}) == 4096
    assert _supervisor_temperature({}) == 0.2


def test_supervisor_runtime_values_are_sanitized() -> None:
    assert _supervisor_model({"model": ""}) == "gpt-5.1"
    assert _supervisor_max_tokens({"max_tokens": -1}) == 4096
    assert _supervisor_temperature({"temperature": "warm"}) == 0.2
