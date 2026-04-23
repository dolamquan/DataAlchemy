"""Report Agent - composes a technical report draft from prior agent results."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.models import (
    get_report_record_by_dataset_id,
    get_upload_record_by_file_id,
    get_upload_schema_by_file_id,
    save_report_record,
)
from app.engine.llm_client import LLMClientError, call_text_llm
from app.engine.registry import get_agent_config
from app.core.settings import OPENAI_MODEL
from app.services.artifacts import safe_artifact_file_id, write_json_artifact


def _resolve_config(payload_config: dict[str, Any]) -> dict[str, Any]:
    try:
        agent_cfg = get_agent_config("report_agent")
        defaults: dict[str, Any] = agent_cfg.get("defaults", {})
    except KeyError:
        defaults = {}

    resolved: dict[str, Any] = {
        "title": None,
        "audience": "team",
        "include_raw_results": True,
        "include_artifacts": True,
        "style": "structured",
        "tone": "technical",
    }
    resolved.update(defaults)
    resolved.update({k: v for k, v in payload_config.items() if v is not None})
    return resolved


def _latest_result(prior_results: list[dict[str, Any]], agent_name: str) -> dict[str, Any] | None:
    for entry in reversed(prior_results):
        if entry.get("agent") == agent_name:
            return entry
    return None


def _dataset_overview(dataset_id: str) -> dict[str, Any]:
    try:
        upload = get_upload_record_by_file_id(dataset_id) or {}
    except Exception:
        upload = {}
    try:
        schema = get_upload_schema_by_file_id(dataset_id) or {}
    except Exception:
        schema = {}
    columns = schema.get("columns", [])

    return {
        "dataset_id": dataset_id,
        "file_name": upload.get("original_filename") or schema.get("file_name") or dataset_id,
        "created_at": upload.get("created_at"),
        "file_size_bytes": upload.get("file_size_bytes"),
        "rows_sampled": schema.get("rows_sampled"),
        "total_columns": schema.get("total_columns"),
        "numeric_columns": sum(1 for col in columns if col.get("column_family") == "numeric"),
        "categorical_columns": sum(1 for col in columns if col.get("column_family") == "categorical"),
        "columns_with_missing_values": sum(1 for col in columns if (col.get("null_count") or 0) > 0),
        "columns": columns,
        "notes": schema.get("notes") or [],
    }


def _summarize_quality(entry: dict[str, Any] | None) -> tuple[str, list[str], dict[str, Any] | None]:
    if not entry:
        return "Data quality validation was not run in this session.", [], None

    result = entry.get("result") or {}
    checks = result.get("checks") or []
    recommendations = result.get("recommendations") or []
    score = result.get("quality_score")
    text = (
        f"Data quality checks completed with score {score:.2f}."
        if isinstance(score, (int, float))
        else "Data quality checks completed."
    )
    highlights = [check.get("details", "") for check in checks if isinstance(check, dict)][:6]
    return text, highlights, result


def _summarize_preprocessing(entry: dict[str, Any] | None) -> tuple[str, list[str], dict[str, Any] | None]:
    if not entry:
        return "Preprocessing did not run before this report was generated.", [], None

    result = entry.get("result") or {}
    applied_steps = result.get("applied_steps") or result.get("steps") or []
    if isinstance(applied_steps, list) and applied_steps:
        summary = f"Preprocessing prepared the dataset with {len(applied_steps)} step(s)."
        bullets = [str(step) for step in applied_steps[:8]]
    else:
        summary = "Preprocessing completed and produced a modeling dataset."
        bullets = []
    return summary, bullets, result


def _summarize_training(entry: dict[str, Any] | None) -> tuple[str, list[str], dict[str, Any] | None]:
    if not entry:
        return "Model training results were not available.", [], None

    result = entry.get("result") or {}
    model_name = result.get("chosen_model") or result.get("model")
    metric = result.get("metric")
    score = result.get("cv_score")
    target = result.get("target_column")

    summary_parts = []
    if model_name:
        summary_parts.append(f"Selected model: {model_name}.")
    if metric and score is not None:
        summary_parts.append(f"Validation {metric}: {score:.4f}.")
    if target:
        summary_parts.append(f"Target column: {target}.")
    summary = " ".join(summary_parts) or "Model training completed."

    bullets = []
    for key in ("task_type", "n_samples", "n_features", "training_time_seconds", "model_file_id"):
        value = result.get(key)
        if value is not None:
            bullets.append(f"{key}: {value}")
    return summary, bullets, result


def _summarize_evaluation(entry: dict[str, Any] | None) -> tuple[str, list[str], dict[str, Any] | None]:
    if not entry:
        return "Evaluation results were not available.", [], None

    result = entry.get("result") or {}
    metrics = result.get("metrics") or {}
    primary_metric = result.get("primary_metric")
    primary_score = result.get("primary_score")
    summary = (
        f"Evaluation completed with {primary_metric}={primary_score}."
        if primary_metric and primary_score is not None
        else "Evaluation completed."
    )

    bullets = []
    if isinstance(metrics, dict):
        for key, value in metrics.items():
            if isinstance(value, (int, float, str)):
                bullets.append(f"{key}: {value}")
            if len(bullets) >= 8:
                break
    return summary, bullets, result


def _collect_artifacts(prior_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for entry in prior_results:
        agent_name = str(entry.get("agent") or "agent")
        for artifact in entry.get("artifacts") or []:
            normalized = dict(artifact)
            normalized.setdefault("agent", agent_name)
            artifacts.append(normalized)
    return artifacts


def _make_section(title: str, summary: str, bullets: list[str], data: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "title": title,
        "summary": summary,
        "bullets": bullets,
        "data": data or {},
    }


def _build_context_bundle(
    dataset_id: str,
    overview: dict[str, Any],
    sections: list[dict[str, Any]],
    prior_results: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "dataset_overview": overview,
        "sections": sections,
        "artifacts": artifacts,
        "prior_results": prior_results,
    }


def _fallback_report_draft(title: str, executive_summary: str, sections: list[dict[str, Any]], next_steps: list[str]) -> str:
    lines: list[str] = [
        f"# {title}",
        "",
        "## Executive Summary",
        executive_summary,
        "",
    ]
    for section in sections:
        lines.append(f"## {section['title']}")
        lines.append(section["summary"])
        lines.append("")
        bullets = section.get("bullets") or []
        if bullets:
            for bullet in bullets:
                lines.append(f"- {bullet}")
            lines.append("")
    lines.append("## Recommendations")
    for step in next_steps:
        lines.append(f"- {step}")
    lines.append("")
    return "\n".join(lines).strip()


def _generate_report_draft(
    *,
    title: str,
    audience: str | None,
    tone: str | None,
    executive_summary: str,
    sections: list[dict[str, Any]],
    next_steps: list[str],
    context_bundle: dict[str, Any],
) -> str:
    system_prompt = (
        "You are a senior technical report writer for a machine learning analytics platform. "
        "Write a polished, concise, technically credible report draft in Markdown. "
        "Use the supplied machine-generated context, but do not expose raw JSON or say 'according to the JSON'. "
        "Prefer clear prose, meaningful section headings, short evidence-backed paragraphs, and compact bullet lists only when useful."
    )
    user_prompt = (
        f"Audience: {audience or 'team'}\n"
        f"Tone: {tone or 'technical'}\n"
        f"Title: {title}\n"
        f"Executive summary seed: {executive_summary}\n"
        f"Recommended next steps: {next_steps}\n"
        "Context:\n"
        f"{context_bundle}\n\n"
        "Write the full technical report draft now."
    )
    try:
        draft = call_text_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=OPENAI_MODEL,
            max_tokens=2500,
            temperature=0.4,
        )
        return draft or _fallback_report_draft(title, executive_summary, sections, next_steps)
    except (LLMClientError, RuntimeError):
        return _fallback_report_draft(title, executive_summary, sections, next_steps)


def _build_report_document(
    dataset_id: str,
    cfg: dict[str, Any],
    prior_results: list[dict[str, Any]],
) -> dict[str, Any]:
    overview = _dataset_overview(dataset_id)
    quality_summary, quality_bullets, quality_data = _summarize_quality(
        _latest_result(prior_results, "data_quality_agent")
    )
    preprocessing_summary, preprocessing_bullets, preprocessing_data = _summarize_preprocessing(
        _latest_result(prior_results, "data_preprocessing_agent")
    )
    training_summary, training_bullets, training_data = _summarize_training(
        _latest_result(prior_results, "model_training_agent")
    )
    evaluation_summary, evaluation_bullets, evaluation_data = _summarize_evaluation(
        _latest_result(prior_results, "evaluation_agent")
    )

    title = cfg.get("title") or f"Analysis Report for {overview['file_name']}"
    executive_summary = " ".join(
        part
        for part in (
            quality_summary if quality_data else None,
            training_summary if training_data else None,
            evaluation_summary if evaluation_data else None,
        )
        if part
    ) or "This report captures the latest available dataset, training, and evaluation details."

    sections = [
        _make_section(
            "Dataset Overview",
            (
                f"Dataset contains {overview.get('total_columns') or 0} column(s) "
                f"with {overview.get('columns_with_missing_values') or 0} column(s) containing nulls."
            ),
            [
                f"Dataset ID: {overview['dataset_id']}",
                f"Rows sampled: {overview.get('rows_sampled') or 0}",
                f"Numeric columns: {overview.get('numeric_columns') or 0}",
                f"Categorical columns: {overview.get('categorical_columns') or 0}",
            ],
            overview,
        ),
        _make_section("Data Quality", quality_summary, quality_bullets, quality_data),
        _make_section("Preprocessing", preprocessing_summary, preprocessing_bullets, preprocessing_data),
        _make_section("Model Training", training_summary, training_bullets, training_data),
        _make_section("Evaluation", evaluation_summary, evaluation_bullets, evaluation_data),
    ]

    next_steps = [
        "Review the evaluation metrics and compare them to the project objective.",
        "Investigate the highest-impact quality issues before operational use.",
        "Revise the report draft with domain conclusions, caveats, and stakeholder recommendations.",
    ]
    artifacts = _collect_artifacts(prior_results) if cfg.get("include_artifacts", True) else []
    context_bundle = _build_context_bundle(
        dataset_id=dataset_id,
        overview=overview,
        sections=sections,
        prior_results=prior_results if cfg.get("include_raw_results", True) else [],
        artifacts=artifacts,
    )
    draft_markdown = _generate_report_draft(
        title=title,
        audience=cfg.get("audience"),
        tone=cfg.get("tone"),
        executive_summary=executive_summary,
        sections=sections,
        next_steps=next_steps,
        context_bundle=context_bundle,
    )

    report = {
        "dataset_id": dataset_id,
        "title": title,
        "audience": cfg.get("audience"),
        "style": cfg.get("style"),
        "tone": cfg.get("tone"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executive_summary": executive_summary,
        "next_steps": next_steps,
        "draft_markdown": draft_markdown,
        "sections": sections,
        "artifacts": artifacts,
        "assistant_context": context_bundle,
    }
    return report


async def report_handler(payload: dict[str, Any]) -> dict[str, Any]:
    step = str(payload.get("step") or "write_report")
    dataset_id = str(payload.get("dataset_id") or "")
    cfg = _resolve_config(payload.get("config") or {})
    prior_results: list[dict[str, Any]] = payload.get("prior_results") or []

    if not dataset_id:
        return _failed(step, "dataset_id is required to generate a report.")

    if not prior_results:
        try:
            existing = get_report_record_by_dataset_id(dataset_id)
        except Exception:
            existing = None
        if existing is not None:
            return {
                "status": "success",
                "result": existing["content"],
                "artifacts": [
                    {
                        "name": "report_document.json",
                        "type": "json",
                        "file_id": existing["file_id"],
                        "path": str(Path("uploads") / existing["file_id"]),
                    }
                ],
                "dashboard_updates": [
                    {
                        "agent": "report_agent",
                        "step": step,
                        "status": "completed",
                        "message": "Loaded the existing saved report document.",
                    }
                ],
            }

    report = _build_report_document(dataset_id, cfg, prior_results)
    report_file_id = safe_artifact_file_id("report", dataset_id, ".json")
    report_path = write_json_artifact(report_file_id, report)
    try:
        save_report_record(dataset_id=dataset_id, file_id=report_file_id, content=report)
    except Exception:
        pass

    return {
        "status": "success",
        "result": report,
        "artifacts": [
            {
                "name": "report_document.json",
                "type": "json",
                "path": str(report_path),
                "file_id": report_file_id,
            }
        ],
        "dashboard_updates": [
            {
                "agent": "report_agent",
                "step": step,
                "status": "completed",
                "message": f"Generated editable report for dataset {dataset_id}.",
            }
        ],
    }


def _failed(step: str, message: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "result": {"error": message},
        "artifacts": [],
        "dashboard_updates": [
            {
                "agent": "report_agent",
                "step": step,
                "status": "failed",
                "message": message,
            }
        ],
    }
