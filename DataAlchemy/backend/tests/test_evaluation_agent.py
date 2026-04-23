"""Tests for the evaluation_agent module."""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from unittest.mock import patch

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression


def _write_classification_csv(path: Path) -> None:
    rows = [
        {"f1": 0.0, "f2": 0.0, "target": 0},
        {"f1": 0.1, "f2": 0.2, "target": 0},
        {"f1": 1.0, "f2": 1.0, "target": 1},
        {"f1": 1.2, "f2": 0.9, "target": 1},
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["f1", "f2", "target"])
        writer.writeheader()
        writer.writerows(rows)


def test_evaluation_handler_scores_classification_model(tmp_path: Path) -> None:
    from app.agents.evaluation_agent import evaluation_handler

    csv_path = tmp_path / "preprocessed_dataset.csv"
    _write_classification_csv(csv_path)

    df = pd.read_csv(csv_path)
    model = LogisticRegression().fit(df[["f1", "f2"]], df["target"])
    model_file_id = "model_dataset.csv.joblib"
    joblib.dump(model, tmp_path / model_file_id)

    payload = {
        "dataset_id": "dataset.csv",
        "step": "evaluate_model",
        "agent": "evaluation_agent",
        "config": {},
        "prior_results": [
            {
                "agent": "data_preprocessing_agent",
                "result": {"preprocessed_file_id": csv_path.name},
            },
            {
                "agent": "model_training_agent",
                "result": {
                    "task_type": "classification",
                    "target_column": "target",
                    "model_file_id": model_file_id,
                },
            },
        ],
    }

    with (
        patch("app.agents.evaluation_agent.UPLOAD_DIR", tmp_path),
        patch("app.agents.evaluation_agent.get_agent_config", return_value={"defaults": {}}),
        patch("app.services.artifacts.UPLOAD_DIR", tmp_path),
    ):
        result = asyncio.run(evaluation_handler(payload))

    assert result["status"] == "success", result.get("result", {}).get("error")
    assert result["result"]["task_type"] == "classification"
    assert result["result"]["target_column"] == "target"
    assert result["result"]["metrics"]["accuracy"] == 1.0
    assert (tmp_path / result["artifacts"][0]["file_id"]).exists()
