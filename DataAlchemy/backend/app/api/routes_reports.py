from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.settings import OPENAI_MODEL, UPLOAD_DIR
from app.db.models import get_report_record_by_dataset_id, save_report_record
from app.engine.llm_client import LLMClientError, call_text_llm
from app.engine.agent_runtime import run_agent
from app.engine.schemas import ReportAssistRequest, ReportCompileRequest, ReportGenerateRequest, ReportSaveRequest
from app.services.artifacts import safe_artifact_file_id, write_json_artifact
from app.services.report_latex import compile_latex_to_pdf, latex_compiler_available

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{dataset_id}")
def get_report(dataset_id: str):
	record = get_report_record_by_dataset_id(dataset_id)
	if record is None:
		raise HTTPException(status_code=404, detail="Report not found")
	return record


@router.post("/generate")
async def generate_report(payload: ReportGenerateRequest):
	result = await run_agent(
		"report_agent",
		{
			"agent": "report_agent",
			"step": "write_report",
			"dataset_id": payload.dataset_id,
			"config": payload.config or {},
			"prior_results": payload.prior_results,
		},
	)
	if result.get("status") != "success":
		raise HTTPException(status_code=400, detail=((result.get("result") or {}).get("error") or "Report generation failed"))
	return result


@router.post("/{dataset_id}/save")
def save_report(dataset_id: str, payload: ReportSaveRequest):
	file_id = safe_artifact_file_id("report", dataset_id, ".json")
	content = payload.content
	latex_source = str(content.get("latex_source") or "")
	latex_file_id = safe_artifact_file_id("report", dataset_id, ".tex")
	compile_error = None
	compiled_pdf_file_id = None
	if latex_source:
		(UPLOAD_DIR / latex_file_id).write_text(latex_source, encoding="utf-8")
	if latex_source:
		pdf_file_id = safe_artifact_file_id("report", dataset_id, ".pdf")
		compile_result = compile_latex_to_pdf(latex_source, pdf_file_id)
		if compile_result.get("success"):
			compiled_pdf_file_id = compile_result.get("file_id")
		else:
			compile_error = compile_result.get("error")
		content["compiled_pdf_file_id"] = compiled_pdf_file_id
		content["latex_compile_error"] = compile_error
		available, compiler = latex_compiler_available()
		content["latex_compiler_available"] = available
		content["latex_compiler"] = compiler
	write_json_artifact(file_id, content)
	save_report_record(dataset_id=dataset_id, file_id=file_id, content=content)
	return {"dataset_id": dataset_id, "file_id": file_id, "content": content}


@router.post("/compile")
def compile_report(payload: ReportCompileRequest):
	record = get_report_record_by_dataset_id(payload.dataset_id)
	if record is None:
		raise HTTPException(status_code=404, detail="Report not found")
	content = record["content"]
	latex_source = payload.latex_source or content.get("latex_source") or ""
	if not latex_source:
		raise HTTPException(status_code=400, detail="No LaTeX source available to compile")
	file_id = safe_artifact_file_id("report", payload.dataset_id, ".pdf")
	result = compile_latex_to_pdf(str(latex_source), file_id)
	available, compiler = latex_compiler_available()
	content["latex_compiler_available"] = available
	content["latex_compiler"] = compiler
	content["compiled_pdf_file_id"] = result.get("file_id")
	content["latex_compile_error"] = result.get("error")
	save_report_record(dataset_id=payload.dataset_id, file_id=record["file_id"], content=content)
	return {
		"success": bool(result.get("success")),
		"file_id": result.get("file_id"),
		"error": result.get("error"),
		"compiler_available": available,
		"compiler": compiler,
	}


@router.post("/assist")
def assist_with_report(payload: ReportAssistRequest):
	record = get_report_record_by_dataset_id(payload.dataset_id)
	if record is None:
		raise HTTPException(status_code=404, detail="Report not found")

	report = record["content"]
	system_prompt = (
		"You are an in-app AI writing assistant for DataAlchemy. "
		"Help the user improve a technical data science report. "
		"Be concise, practical, and grounded in the hidden report context. "
		"Do not expose raw JSON directly. "
		"When appropriate, provide a revised paragraph or section the user can paste into the editor."
	)
	user_prompt = (
		f"User request: {payload.message}\n\n"
		f"Current draft:\n{payload.current_draft or report.get('draft_markdown', '')}\n\n"
		f"Hidden report context:\n{report.get('assistant_context', {})}\n"
	)
	try:
		reply = call_text_llm(
			system_prompt=system_prompt,
			user_prompt=user_prompt,
			model=OPENAI_MODEL,
			max_tokens=1200,
			temperature=0.5,
		)
	except LLMClientError as exc:
		raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

	return {"reply": reply}
