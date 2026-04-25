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
from app.services.report_latex import compile_latex_to_pdf, latex_compiler_available, markdown_to_latex


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


def _dataset_overview(dataset_id: str, owner_uid: str | None = None) -> dict[str, Any]:
    try:
        upload = get_upload_record_by_file_id(dataset_id, owner_uid=owner_uid) or {}
    except Exception:
        upload = {}
    try:
        schema = get_upload_schema_by_file_id(dataset_id, owner_uid=owner_uid) or {}
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
            lines.append("Key points considered in this section include:")
            lines.append("")
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
        "Write a polished, detailed, technically credible academic-style report draft in Markdown. "
        "Use the supplied machine-generated context, but do not expose raw JSON or say 'according to the JSON'. "
        "Prefer clear prose, meaningful section headings, evidence-backed paragraphs, and only limited bullets when appropriate. "
        "The report should read like a final technical project report, not a checklist or sparse autogenerated note."
    )
    user_prompt = (
        f"Audience: {audience or 'team'}\n"
        f"Tone: {tone or 'technical'}\n"
        f"Title: {title}\n"
        f"Executive summary seed: {executive_summary}\n"
        f"Recommended next steps: {next_steps}\n"
        "Context:\n"
        f"{context_bundle}\n\n"
        "Write the full technical report draft now.\n"
        "Requirements:\n"
        "- Use numbered major sections when appropriate.\n"
        "- Include an Abstract or Executive Summary, Introduction, Data Description, Methodology, Results, Discussion, Limitations, and Conclusion.\n"
        "- Explain what was done and why it matters.\n"
        "- Turn metrics and preprocessing details into full narrative paragraphs.\n"
        "- Avoid vague filler such as 'this section discusses' or 'random' placeholder phrasing.\n"
        "- Make the output feel like a polished final report page."
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
    overview = _dataset_overview(dataset_id, owner_uid=cfg.get("owner_uid"))
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

    methods_summary = "The project followed a staged pipeline that profiles the dataset, prepares model-ready features, trains a candidate model, and evaluates predictive performance on the selected task."
    if preprocessing_data and training_data and evaluation_data:
        methods_summary = (
            "The workflow used a multi-stage machine learning pipeline covering preprocessing, model training, and evaluation. "
            "This structure supports reproducibility by separating data preparation, model selection, and performance measurement into explicit stages."
        )
    discussion_summary = (
        "The current outputs suggest how the chosen model performed under the available data and preprocessing configuration. "
        "Interpretation should consider dataset coverage, feature quality, class balance, and the scope of the evaluation metrics that were computed."
    )
    limitations_summary = (
        "This report is constrained by the artifacts and metrics available from the executed pipeline. "
        "If data quality checks, preprocessing logs, or broader validation experiments are missing, the conclusions should be treated as provisional."
    )

    next_steps = [
        "Review the evaluation metrics and compare them to the project objective.",
        "Investigate the highest-impact quality issues before operational use.",
        "Revise the report draft with domain conclusions, caveats, and stakeholder recommendations.",
    ]

    sections = [
        _make_section(
            "Abstract",
            executive_summary,
            [
                "Summarizes the objective, pipeline stages, and most important reported findings.",
                "Intended to give a reader a complete high-level understanding before reviewing the technical sections.",
            ],
            {
                "dataset_id": dataset_id,
                "audience": cfg.get("audience"),
                "tone": cfg.get("tone"),
            },
        ),
        _make_section(
            "Introduction",
            (
                "This report documents the analytical workflow applied to the selected dataset and explains how the resulting outputs support model development and evaluation. "
                "The overall goal is to move from raw uploaded data to an interpretable technical narrative that captures data readiness, modeling decisions, and measured performance."
            ),
            [
                "Establishes the project goal and analytical scope.",
                "Explains why a staged pipeline is useful for data and model governance.",
            ],
            {
                "user_goal": "reporting_from_pipeline_outputs",
                "pipeline_agents": [entry.get("agent") for entry in prior_results],
            },
        ),
        _make_section(
            "Data Description",
            (
                f"The dataset snapshot used for reporting contains {overview.get('total_columns') or 0} column(s), "
                f"including {overview.get('numeric_columns') or 0} numeric feature(s) and {overview.get('categorical_columns') or 0} categorical feature(s). "
                f"{overview.get('columns_with_missing_values') or 0} column(s) were observed with missing values in the stored schema profile."
            ),
            [
                f"Dataset ID: {overview['dataset_id']}",
                f"Rows sampled: {overview.get('rows_sampled') or 0}",
                f"Numeric columns: {overview.get('numeric_columns') or 0}",
                f"Categorical columns: {overview.get('categorical_columns') or 0}",
            ],
            overview,
        ),
        _make_section("Methodology", methods_summary, [
            "Data profiling and quality signals were used to characterize the dataset before model interpretation.",
            "Preprocessing outputs were incorporated where available to explain the transformation pipeline.",
            "Training and evaluation artifacts were combined into a single end-to-end narrative.",
        ], {
            "preprocessing": preprocessing_data or {},
            "training": training_data or {},
            "evaluation": evaluation_data or {},
        }),
        _make_section("Data Quality", quality_summary, quality_bullets, quality_data),
        _make_section("Preprocessing", preprocessing_summary, preprocessing_bullets, preprocessing_data),
        _make_section("Model Training", training_summary, training_bullets, training_data),
        _make_section("Results", evaluation_summary, evaluation_bullets, evaluation_data),
        _make_section("Discussion", discussion_summary, [
            "Connect the quantitative outputs to the project objective.",
            "Explain whether the reported metrics appear strong enough for the intended use case.",
            "Highlight tradeoffs between model simplicity, interpretability, and measured performance.",
        ], {
            "training_summary": training_summary,
            "evaluation_summary": evaluation_summary,
        }),
        _make_section("Limitations", limitations_summary, [
            "Limited artifact availability can reduce the depth of interpretation.",
            "A single reported run may not capture run-to-run variance or deployment robustness.",
            "Additional validation, ablation studies, and stakeholder review may still be needed.",
        ], {}),
        _make_section("Conclusion", (
            "Overall, the available pipeline outputs provide a structured basis for documenting the dataset, the modeling workflow, and the observed performance. "
            "The final suitability of the solution depends on the business objective, the trustworthiness of the underlying data, and whether the measured results generalize beyond the current run."
        ), next_steps, {}),
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
        "latex_source": markdown_to_latex(draft_markdown, title),
        "sections": sections,
        "artifacts": artifacts,
        "assistant_context": context_bundle,
    }
    available, compiler = latex_compiler_available()
    report["latex_compiler_available"] = available
    report["latex_compiler"] = compiler
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
            existing = get_report_record_by_dataset_id(dataset_id, owner_uid=cfg.get("owner_uid"))
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
    latex_file_id = safe_artifact_file_id("report", dataset_id, ".tex")
    latex_path = Path(report_path).with_name(latex_file_id)
    latex_path.write_text(str(report.get("latex_source") or ""), encoding="utf-8")
    report["latex_source_file_id"] = latex_file_id
    latex_pdf_file_id = safe_artifact_file_id("report", dataset_id, ".pdf")
    compile_result = compile_latex_to_pdf(str(report.get("latex_source") or ""), latex_pdf_file_id)
    if compile_result.get("success"):
        report["compiled_pdf_file_id"] = compile_result.get("file_id")
    else:
        report["latex_compile_error"] = compile_result.get("error")
    report_path = write_json_artifact(report_file_id, report)
    try:
        save_report_record(
            dataset_id=dataset_id,
            file_id=report_file_id,
            content=report,
            owner_uid=cfg.get("owner_uid"),
        )
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
            },
            {
                "name": "report_source.tex",
                "type": "tex",
                "path": str(latex_path),
                "file_id": latex_file_id,
            },
        ] + (
            [
                {
                    "name": "report_preview.pdf",
                    "type": "pdf",
                    "path": str(compile_result["path"]),
                    "file_id": str(compile_result["file_id"]),
                }
            ]
            if compile_result.get("success")
            else []
        ),
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
