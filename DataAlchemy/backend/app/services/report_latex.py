from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.settings import UPLOAD_DIR

_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_compiler_available() -> tuple[bool, str | None]:
    for candidate in ("pdflatex", "xelatex", "tectonic"):
        resolved = shutil.which(candidate)
        if resolved:
            return True, candidate
    return False, None


def escape_latex(text: str) -> str:
    escaped = text
    for source, replacement in _LATEX_SPECIALS.items():
        escaped = escaped.replace(source, replacement)
    return escaped


def _stage_latex_assets(latex_source: str, build_dir: Path) -> None:
    image_paths = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", latex_source)
    for raw_path in image_paths:
        normalized = raw_path.strip().strip("\"'")
        if not normalized or re.match(r"^(https?:|data:)", normalized):
            continue

        requested_path = Path(normalized)
        source_candidates: list[Path] = []
        if requested_path.is_absolute():
            source_candidates.append(requested_path)
        else:
            source_candidates.append(UPLOAD_DIR / requested_path)
            source_candidates.append(UPLOAD_DIR / requested_path.name)

        source_path = next((candidate for candidate in source_candidates if candidate.exists() and candidate.is_file()), None)
        if source_path is None:
            continue

        target_path = build_dir / requested_path
        if requested_path.is_absolute():
            target_path = build_dir / source_path.name

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def markdown_to_latex(markdown: str, title: str) -> str:
    lines = markdown.splitlines()
    body: list[str] = []
    in_itemize = False

    def close_itemize() -> None:
        nonlocal in_itemize
        if in_itemize:
            body.append(r"\end{itemize}")
            body.append("")
            in_itemize = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            close_itemize()
            body.append("")
            continue

        if line.startswith("# "):
            close_itemize()
            continue
        if line.startswith("## "):
            close_itemize()
            body.append(rf"\section{{{escape_latex(line[3:])}}}")
            continue
        if line.startswith("### "):
            close_itemize()
            body.append(rf"\subsection{{{escape_latex(line[4:])}}}")
            continue
        if line.startswith("- "):
            if not in_itemize:
                body.append(r"\begin{itemize}")
                in_itemize = True
            body.append(rf"\item {escape_latex(line[2:])}")
            continue

        close_itemize()
        body.append(escape_latex(line))

    close_itemize()
    rendered_body = "\n".join(body)
    return (
        r"\documentclass[11pt]{article}" "\n"
        r"\usepackage[margin=1in]{geometry}" "\n"
        r"\usepackage[T1]{fontenc}" "\n"
        r"\usepackage[utf8]{inputenc}" "\n"
        r"\usepackage{lmodern}" "\n"
        r"\usepackage{microtype}" "\n"
        r"\usepackage{enumitem}" "\n"
        r"\usepackage{xcolor}" "\n"
        r"\usepackage{graphicx}" "\n"
        r"\usepackage{caption}" "\n"
        r"\setlist[itemize]{leftmargin=1.5em}" "\n"
        r"\title{" + escape_latex(title) + "}\n"
        r"\date{}" "\n"
        r"\begin{document}" "\n"
        r"\maketitle" "\n\n"
        + rendered_body +
        "\n\n\\end{document}\n"
    )


def compile_latex_to_pdf(latex_source: str, output_file_id: str) -> dict[str, str | bool | None]:
    available, compiler = latex_compiler_available()
    if not available or not compiler:
        return {
            "success": False,
            "error": "No LaTeX compiler is installed on the backend.",
            "file_id": None,
            "path": None,
        }

    build_root = UPLOAD_DIR / "latex_build"
    build_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=build_root) as tmp_dir:
        tmp_path = Path(tmp_dir)
        tex_file = tmp_path / "report.tex"
        tex_file.write_text(latex_source, encoding="utf-8")
        _stage_latex_assets(latex_source, tmp_path)

        if compiler == "tectonic":
            command = [compiler, str(tex_file), "--outdir", str(tmp_path)]
        else:
            command = [compiler, "-interaction=nonstopmode", "-halt-on-error", str(tex_file)]

        result = subprocess.run(
            command,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        pdf_path = tmp_path / "report.pdf"
        if result.returncode != 0 or not pdf_path.exists():
            stderr = (result.stderr or result.stdout or "").strip()
            return {
                "success": False,
                "error": stderr[:1200] or "LaTeX compilation failed.",
                "file_id": None,
                "path": None,
            }

        final_path = UPLOAD_DIR / output_file_id
        final_path.write_bytes(pdf_path.read_bytes())
        return {
            "success": True,
            "error": None,
            "file_id": output_file_id,
            "path": str(final_path),
        }
