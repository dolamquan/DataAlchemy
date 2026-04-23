"""Unit tests for the report_agent module."""

from __future__ import annotations

import asyncio


def test_report_handler_generates_editable_report(monkeypatch, tmp_path) -> None:
    from app.agents.report_agent import report_handler

    saved_reports: list[dict] = []

    monkeypatch.setattr(
        "app.agents.report_agent.get_upload_record_by_file_id",
        lambda dataset_id: {
            "file_id": dataset_id,
            "original_filename": "customers.csv",
            "file_size_bytes": 1024,
            "created_at": "2026-04-23T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        "app.agents.report_agent.get_upload_schema_by_file_id",
        lambda dataset_id: {
            "rows_sampled": 100,
            "total_columns": 4,
            "columns": [
                {"name": "age", "column_family": "numeric", "null_count": 0},
                {"name": "city", "column_family": "categorical", "null_count": 5},
            ],
            "notes": ["schema note"],
        },
    )
    monkeypatch.setattr("app.agents.report_agent.get_report_record_by_dataset_id", lambda dataset_id: None)
    monkeypatch.setattr(
        "app.agents.report_agent.save_report_record",
        lambda **kwargs: saved_reports.append(kwargs),
    )
    monkeypatch.setattr(
        "app.agents.report_agent.write_json_artifact",
        lambda file_id, payload: tmp_path / file_id,
    )

    payload = {
        "step": "write_report",
        "dataset_id": "dataset-1.csv",
        "prior_results": [
            {
                "agent": "model_training_agent",
                "step": "train_model",
                "result": {
                    "chosen_model": "RandomForestClassifier",
                    "metric": "accuracy",
                    "cv_score": 0.92,
                    "target_column": "Exited",
                },
                "artifacts": [{"name": "trained_model.joblib", "file_id": "model_dataset-1.joblib"}],
            },
            {
                "agent": "evaluation_agent",
                "step": "evaluate_model",
                "result": {
                    "primary_metric": "accuracy",
                    "primary_score": 0.91,
                    "metrics": {"accuracy": 0.91, "f1_macro": 0.9},
                },
                "artifacts": [{"name": "evaluation_report.json", "file_id": "evaluation_dataset-1.json"}],
            },
        ],
    }

    result = asyncio.run(report_handler(payload))

    assert result["status"] == "success"
    assert result["result"]["title"] == "Analysis Report for customers.csv"
    assert len(result["result"]["sections"]) >= 4
    assert len(result["result"]["artifacts"]) == 2
    assert saved_reports[0]["dataset_id"] == "dataset-1.csv"
