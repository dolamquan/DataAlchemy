import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Bot,
  Download,
  Eye,
  FileText,
  PencilLine,
  RefreshCcw,
  Save,
  Send,
  Sparkles,
} from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Textarea } from "../components/ui/textarea";
import { loadAgentRuntimeSnapshot } from "../lib/agentRuntimeStore";
import {
  artifactDownloadUrl,
  assistWithReport,
  compileReportLatex,
  fetchRecentUploads,
  fetchSavedReport,
  generateReport,
  saveReport,
  type RecentUploadItem,
  type ReportDocument,
} from "../lib/uploadsApi";

interface AssistantMessage {
  role: "assistant" | "user";
  content: string;
}

function formatDate(iso?: string) {
  if (!iso) return "Unknown";
  const value = new Date(iso);
  return Number.isNaN(value.getTime()) ? "Unknown" : value.toLocaleString();
}

function emptyReport(datasetId: string): ReportDocument {
  return {
    dataset_id: datasetId,
    title: "Untitled technical report",
    executive_summary: "",
    next_steps: [],
    draft_markdown: "",
    latex_source: "",
    sections: [],
    artifacts: [],
    assistant_context: {},
    latex_compiler_available: false,
    latex_compiler: null,
    compiled_pdf_file_id: null,
    latex_compile_error: null,
  };
}

function reportTitleFromLatex(latex: string, fallback: string) {
  const match = latex.match(/\\title\{([\s\S]*?)\}/);
  return match?.[1]?.trim() || fallback;
}

function normalizeLatexText(value: string) {
  return value
    .replace(/\\textbackslash\{\}/g, "\\")
    .replace(/\\_/g, "_")
    .replace(/\\&/g, "&")
    .replace(/\\%/g, "%")
    .replace(/\\#/g, "#")
    .replace(/\\\$/g, "$")
    .replace(/\\\{/g, "{")
    .replace(/\\\}/g, "}")
    .replace(/\\textasciitilde\{\}/g, "~")
    .replace(/\\textasciicircum\{\}/g, "^")
    .trim();
}

function resolveLatexImageSource(value: string) {
  const normalized = normalizeLatexText(value).replace(/^['"]|['"]$/g, "");
  if (!normalized) return null;
  if (
    normalized.startsWith("http://") ||
    normalized.startsWith("https://") ||
    normalized.startsWith("data:") ||
    normalized.startsWith("/")
  ) {
    return normalized;
  }
  const fileId = normalized.split(/[\\/]/).filter(Boolean).pop();
  return fileId ? artifactDownloadUrl(fileId) : null;
}

function renderLatexPreview(latex: string) {
  const lines = latex.split("\n");
  const blocks: JSX.Element[] = [];
  let paragraph: string[] = [];
  let bullets: string[] = [];
  let inItemize = false;
  let inFigure = false;
  let figureImageSource: string | null = null;
  let figureCaption: string | null = null;

  const pushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push(
      <p key={`p-${blocks.length}`} className="text-[15px] leading-8 text-slate-200">
        {paragraph.join(" ")}
      </p>,
    );
    paragraph = [];
  };

  const pushBullets = () => {
    if (!bullets.length) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="list-disc space-y-2 pl-6 text-[15px] leading-8 text-slate-200">
        {bullets.map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  const pushFigure = () => {
    if (!figureImageSource && !figureCaption) return;
    blocks.push(
      <figure
        key={`figure-${blocks.length}`}
        className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-4"
      >
        {figureImageSource ? (
          <img
            src={figureImageSource}
            alt={figureCaption ?? "Report figure"}
            className="max-h-[26rem] w-full rounded-xl object-contain"
          />
        ) : null}
        {figureCaption ? (
          <figcaption className="mt-3 text-sm leading-6 text-slate-300">{figureCaption}</figcaption>
        ) : null}
      </figure>,
    );
    figureImageSource = null;
    figureCaption = null;
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      pushParagraph();
      if (!inItemize) {
        pushBullets();
      }
      if (!inFigure) {
        pushFigure();
      }
      continue;
    }

    if (
      line.startsWith("\\documentclass") ||
      line.startsWith("\\usepackage") ||
      line.startsWith("\\setlist") ||
      line === "\\begin{document}" ||
      line === "\\end{document}" ||
      line === "\\maketitle" ||
      line.startsWith("\\date{")
    ) {
      continue;
    }

    const titleMatch = line.match(/^\\title\{([\s\S]*)\}$/);
    if (titleMatch) {
      pushParagraph();
      pushBullets();
      pushFigure();
      blocks.push(
        <h1 key={`title-${blocks.length}`} className="text-3xl font-semibold tracking-tight text-white">
          {normalizeLatexText(titleMatch[1])}
        </h1>,
      );
      continue;
    }

    const sectionMatch = line.match(/^\\section\{([\s\S]*)\}$/);
    if (sectionMatch) {
      pushParagraph();
      pushBullets();
      pushFigure();
      blocks.push(
        <h2 key={`section-${blocks.length}`} className="pt-4 text-xl font-semibold text-blue-100">
          {normalizeLatexText(sectionMatch[1])}
        </h2>,
      );
      continue;
    }

    const subsectionMatch = line.match(/^\\subsection\{([\s\S]*)\}$/);
    if (subsectionMatch) {
      pushParagraph();
      pushBullets();
      pushFigure();
      blocks.push(
        <h3 key={`subsection-${blocks.length}`} className="pt-2 text-lg font-medium text-slate-100">
          {normalizeLatexText(subsectionMatch[1])}
        </h3>,
      );
      continue;
    }

    if (line === "\\begin{itemize}") {
      pushParagraph();
      pushFigure();
      inItemize = true;
      continue;
    }

    if (line === "\\end{itemize}") {
      inItemize = false;
      pushBullets();
      continue;
    }

    const itemMatch = line.match(/^\\item\s+([\s\S]*)$/);
    if (itemMatch) {
      bullets.push(normalizeLatexText(itemMatch[1]));
      continue;
    }

    if (line.startsWith("\\begin{figure")) {
      pushParagraph();
      pushBullets();
      pushFigure();
      inFigure = true;
      continue;
    }

    if (line === "\\end{figure}") {
      inFigure = false;
      pushFigure();
      continue;
    }

    if (line === "\\centering") {
      continue;
    }

    const captionMatch = line.match(/^\\caption\{([\s\S]*)\}$/);
    if (captionMatch) {
      figureCaption = normalizeLatexText(captionMatch[1]);
      if (!inFigure) {
        pushFigure();
      }
      continue;
    }

    const includeGraphicsMatch = line.match(/^\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}$/);
    if (includeGraphicsMatch) {
      figureImageSource = resolveLatexImageSource(includeGraphicsMatch[1]);
      if (!inFigure) {
        pushFigure();
      }
      continue;
    }

    if (line.startsWith("\\")) {
      continue;
    }

    paragraph.push(normalizeLatexText(line));
  }

  pushParagraph();
  pushBullets();

  return (
    <div className="space-y-5 px-8 py-8 font-serif">
      {blocks.length > 0 ? blocks : <p className="text-[15px] leading-8 text-slate-300">No LaTeX content to preview yet.</p>}
    </div>
  );
}

export function ReportsPage() {
  const [uploads, setUploads] = useState<RecentUploadItem[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [report, setReport] = useState<ReportDocument | null>(null);
  const [latexText, setLatexText] = useState("");
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantMessages, setAssistantMessages] = useState<AssistantMessage[]>([
    {
      role: "assistant",
      content:
        "I can help refine the LaTeX report source. Ask me to rewrite a section, improve tone, or generate replacement LaTeX for part of the document.",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [assisting, setAssisting] = useState(false);
  const [compiling, setCompiling] = useState(false);
  const [compileMessage, setCompileMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<"preview" | "edit">("edit");

  const runtimeSnapshot = loadAgentRuntimeSnapshot();
  const runtimeResults =
    runtimeSnapshot?.datasetId === selectedDatasetId ? runtimeSnapshot.execution?.results ?? [] : [];

  const contextSummary = useMemo(() => {
    if (!report?.assistant_context) return [];
    const overview = report.assistant_context.dataset_overview as Record<string, unknown> | undefined;
    const rows = typeof overview?.rows_sampled === "number" ? overview.rows_sampled : 0;
    const cols = typeof overview?.total_columns === "number" ? overview.total_columns : 0;
    return [`${rows.toLocaleString()} sampled rows`, `${cols} columns`];
  }, [report]);

  useEffect(() => {
    void initializePage();
  }, []);

  useEffect(() => {
    if (selectedDatasetId) {
      void loadReport(selectedDatasetId);
    }
  }, [selectedDatasetId]);

  useEffect(() => {
    if (!selectedDatasetId || !latexText.trim() || !report?.latex_compiler_available) return;
    const timeout = window.setTimeout(() => {
      void handleCompile(latexText, false);
    }, 1200);
    return () => window.clearTimeout(timeout);
  }, [latexText, selectedDatasetId, report?.latex_compiler_available]);

  async function initializePage() {
    setLoading(true);
    setError(null);
    try {
      const items = await fetchRecentUploads(50);
      setUploads(items);
      if (items.length > 0) {
        setSelectedDatasetId(items[0].file_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load datasets");
    } finally {
      setLoading(false);
    }
  }

  async function loadReport(datasetId: string) {
    setLoading(true);
    setError(null);
    try {
      const saved = await fetchSavedReport(datasetId);
      const nextReport = saved?.content ?? emptyReport(datasetId);
      setReport(nextReport);
      setLatexText(nextReport.latex_source ?? "");
      setSavedAt(saved?.updated_at ?? null);
      setCompileMessage(nextReport.latex_compile_error ?? null);
      setAssistantMessages((current) => current.slice(0, 1));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    if (!selectedDatasetId) return;
    setGenerating(true);
    setError(null);
    try {
      const generated = await generateReport(selectedDatasetId, runtimeResults);
      setReport(generated.result);
      setLatexText(generated.result.latex_source ?? "");
      setSavedAt(new Date().toISOString());
      setEditorMode("edit");
      setCompileMessage(generated.result.latex_compile_error ?? null);
      setAssistantMessages([
        {
          role: "assistant",
          content:
            "The report agent generated LaTeX source for the report. I can help rewrite sections or produce replacement LaTeX blocks.",
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSave() {
    if (!selectedDatasetId || !report) return;
    setSaving(true);
    setError(null);
    try {
      const payload: ReportDocument = {
        ...report,
        title: reportTitleFromLatex(latexText, report.title),
        latex_source: latexText,
      };
      const saved = await saveReport(selectedDatasetId, payload);
      setReport(saved.content);
      setLatexText(saved.content.latex_source ?? latexText);
      setSavedAt(saved.updated_at);
      setCompileMessage(saved.content.latex_compile_error ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save report");
    } finally {
      setSaving(false);
    }
  }

  async function handleCompile(source: string, updateMessage = true) {
    if (!selectedDatasetId) return;
    setCompiling(true);
    try {
      const result = await compileReportLatex(selectedDatasetId, source);
      setReport((current) =>
        current
          ? {
              ...current,
              compiled_pdf_file_id: result.file_id ?? null,
              latex_compile_error: result.error ?? null,
              latex_compiler_available: result.compiler_available ?? current.latex_compiler_available,
              latex_compiler: result.compiler ?? current.latex_compiler,
            }
          : current,
      );
      if (updateMessage) {
        setCompileMessage(
          result.success
            ? "LaTeX compiled successfully."
            : result.error || "LaTeX compilation is unavailable.",
        );
      }
    } catch (err) {
      if (updateMessage) {
        setCompileMessage(err instanceof Error ? err.message : "Failed to compile LaTeX");
      }
    } finally {
      setCompiling(false);
    }
  }

  async function handleAssist() {
    if (!selectedDatasetId || !assistantInput.trim()) return;
    const prompt = assistantInput.trim();
    setAssistantMessages((current) => [...current, { role: "user", content: prompt }]);
    setAssistantInput("");
    setAssisting(true);
    setError(null);
    try {
      const reply = await assistWithReport(selectedDatasetId, prompt, latexText);
      setAssistantMessages((current) => [...current, { role: "assistant", content: reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get assistant response");
    } finally {
      setAssisting(false);
    }
  }

  function applyLatestAssistantReply() {
    const latestAssistant = [...assistantMessages].reverse().find((message) => message.role === "assistant");
    if (!latestAssistant) return;
    setLatexText((current) => `${current.trim()}\n\n${latestAssistant.content}`.trim());
  }

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_28%),linear-gradient(180deg,_rgba(15,23,42,0.94),_rgba(2,6,23,1))]">
      <div className="border-b border-border/70 bg-card/75 backdrop-blur">
        <div className="mx-auto max-w-[1600px] px-8 py-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <div className="mb-2 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-blue-400/30 bg-blue-500/10 text-blue-300">
                  <FileText className="h-5 w-5" />
                </div>
                <div>
                  <h1 className="text-foreground">LaTeX Report Editor</h1>
                  <p className="text-sm text-muted-foreground">
                    Edit the LaTeX source on the left and render the compiled report preview on the right when a TeX engine is available.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="border-blue-400/30 bg-blue-500/5 text-blue-200">
                  <BarChart3 className="mr-1.5 h-3 w-3" />
                  LaTeX authoring mode
                </Badge>
                <Badge variant="outline" className="border-border/70 bg-background/40 text-muted-foreground">
                  {report?.latex_compiler_available
                    ? `Compiler ready: ${report.latex_compiler ?? "TeX engine"}`
                    : "Compiler unavailable in this environment"}
                </Badge>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                className="h-10 min-w-[260px] rounded-xl border border-border/70 bg-background/70 px-3 text-sm text-foreground"
                value={selectedDatasetId}
                onChange={(event) => setSelectedDatasetId(event.target.value)}
                disabled={loading || uploads.length === 0}
              >
                {uploads.length === 0 && <option value="">No datasets available</option>}
                {uploads.map((item) => (
                  <option key={item.file_id} value={item.file_id}>
                    {item.original_filename}
                  </option>
                ))}
              </select>
              <Button variant="outline" onClick={() => void initializePage()} disabled={loading || generating}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
              <Button onClick={() => void handleGenerate()} disabled={!selectedDatasetId || generating}>
                <Sparkles className="mr-2 h-4 w-4" />
                {generating ? "Generating..." : "Generate LaTeX"}
              </Button>
              <Button variant="outline" onClick={() => void handleCompile(latexText)} disabled={!latexText.trim() || compiling}>
                <Eye className="mr-2 h-4 w-4" />
                {compiling ? "Compiling..." : "Compile Preview"}
              </Button>
              <Button variant="outline" onClick={() => void handleSave()} disabled={!report || saving}>
                <Save className="mr-2 h-4 w-4" />
                {saving ? "Saving..." : "Save"}
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
            {savedAt && <span>Last saved: {formatDate(savedAt)}</span>}
            {runtimeResults.length > 0 && <span>{runtimeResults.length} runtime result(s) available for report generation</span>}
            {contextSummary.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-[1600px] grid-cols-1 gap-0 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="border-r border-border/60 px-8 py-8">
          {error && (
            <Card className="mb-6 border-red-500/30 bg-red-500/5">
              <CardContent className="pt-6 text-sm text-red-300">{error}</CardContent>
            </Card>
          )}

          <div className="mx-auto max-w-6xl">
            <Card className="border-border/60 bg-card/85 shadow-[0_24px_80px_rgba(15,23,42,0.35)] backdrop-blur">
              <CardHeader className="border-b border-border/60 pb-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <CardTitle className="text-xl text-foreground">
                      {reportTitleFromLatex(latexText, report?.title ?? "Technical report")}
                    </CardTitle>
                    <CardDescription>
                      Manual editor uses LaTeX source. The preview panel renders the compiled PDF when a LaTeX compiler is installed on the backend.
                    </CardDescription>
                  </div>
                  <div className="flex overflow-hidden rounded-xl border border-border/60 bg-background/70">
                    <Button
                      variant="ghost"
                      size="sm"
                      className={`rounded-none ${editorMode === "preview" ? "bg-blue-500/10 text-blue-200" : ""}`}
                      onClick={() => setEditorMode("preview")}
                    >
                      <Eye className="mr-2 h-3.5 w-3.5" />
                      Preview
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className={`rounded-none ${editorMode === "edit" ? "bg-blue-500/10 text-blue-200" : ""}`}
                      onClick={() => setEditorMode("edit")}
                    >
                      <PencilLine className="mr-2 h-3.5 w-3.5" />
                      Edit Live
                    </Button>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="p-0">
                {editorMode === "preview" ? (
                  <div className="min-h-[calc(100vh-18rem)] bg-[linear-gradient(180deg,rgba(15,23,42,0.22),rgba(15,23,42,0.08))] p-6">
                    {report?.compiled_pdf_file_id ? (
                      <iframe
                        title="LaTeX PDF preview"
                        src={artifactDownloadUrl(report.compiled_pdf_file_id)}
                        className="h-[calc(100vh-22rem)] w-full rounded-xl border border-border/60 bg-white"
                      />
                    ) : (
                      <div className="overflow-hidden rounded-xl border border-border/60 bg-background/60">
                        <div className="border-b border-border/60 px-8 py-4">
                          <p className="text-sm font-medium text-slate-100">Client Preview</p>
                          <p className="text-xs text-muted-foreground">
                            This is a frontend-rendered approximation of the LaTeX document. Install a backend TeX compiler for true PDF rendering.
                          </p>
                        </div>
                        {renderLatexPreview(latexText)}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="grid min-h-[calc(100vh-18rem)] grid-cols-1 divide-y divide-border/60 xl:grid-cols-2 xl:divide-x xl:divide-y-0">
                    <div className="bg-[linear-gradient(180deg,rgba(15,23,42,0.16),rgba(15,23,42,0.04))]">
                      <div className="border-b border-border/60 px-8 py-4">
                        <p className="text-sm font-medium text-slate-100">Manual LaTeX Editor</p>
                        <p className="text-xs text-muted-foreground">
                          Edit the report source directly in LaTeX.
                        </p>
                      </div>
                      <Textarea
                        value={latexText}
                        onChange={(event) => setLatexText(event.target.value)}
                        placeholder="\\documentclass{article}"
                        className="min-h-[calc(100vh-22rem)] resize-none border-0 bg-transparent px-8 py-8 font-mono text-[13px] leading-7 text-foreground shadow-none focus-visible:ring-0"
                      />
                    </div>
                    <div className="bg-[linear-gradient(180deg,rgba(15,23,42,0.22),rgba(15,23,42,0.08))]">
                      <div className="border-b border-border/60 px-8 py-4">
                        <p className="text-sm font-medium text-slate-100">Live Preview</p>
                        <p className="text-xs text-muted-foreground">
                          This renders the compiled PDF when a backend LaTeX compiler is installed.
                        </p>
                      </div>
                      <div className="p-6">
                        {report?.compiled_pdf_file_id ? (
                          <iframe
                            title="LaTeX PDF preview"
                            src={artifactDownloadUrl(report.compiled_pdf_file_id)}
                            className="h-[calc(100vh-26rem)] w-full rounded-xl border border-border/60 bg-white"
                          />
                        ) : (
                          <div className="overflow-hidden rounded-xl border border-border/60 bg-background/60">
                            <div className="border-b border-border/60 px-8 py-4">
                              <p className="text-sm font-medium text-slate-100">Client Preview</p>
                              <p className="text-xs text-muted-foreground">
                                This preview interprets the LaTeX source in the browser. A backend TeX compiler is still needed for exact PDF output.
                              </p>
                            </div>
                            <div className="max-h-[calc(100vh-26rem)] overflow-auto">
                              {renderLatexPreview(latexText)}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
            {compileMessage && (
              <p className="mt-3 text-sm text-muted-foreground">{compileMessage}</p>
            )}
          </div>
        </section>

        <aside className="flex min-h-[calc(100vh-81px)] flex-col bg-card/50 backdrop-blur">
          <div className="border-b border-border/60 px-6 py-6">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-violet-500 text-white shadow-lg shadow-blue-950/30">
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg text-foreground">AI Assistant</h2>
                <p className="text-sm text-muted-foreground">Always here to help shape the LaTeX report</p>
              </div>
            </div>
          </div>

          <div className="flex-1 space-y-4 overflow-auto px-6 py-6">
            {assistantMessages.map((message, index) => (
              <div key={`${message.role}-${index}`} className="flex gap-3">
                <div
                  className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    message.role === "assistant"
                      ? "bg-blue-500/15 text-blue-300"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {message.role === "assistant" ? <Sparkles className="h-4 w-4" /> : <Send className="h-3.5 w-3.5" />}
                </div>
                <div
                  className={`max-w-full rounded-2xl px-4 py-3 text-sm leading-7 ${
                    message.role === "assistant"
                      ? "bg-background/80 text-foreground shadow-sm"
                      : "bg-blue-500/10 text-blue-100"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
              </div>
            ))}

            {assisting && (
              <div className="flex gap-3">
                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-500/15 text-blue-300">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div className="rounded-2xl bg-background/80 px-4 py-3 text-sm text-muted-foreground">
                  Thinking about the best LaTeX revision...
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-border/60 px-6 py-5">
            <div className="mb-3 flex gap-2">
              <Button variant="outline" size="sm" onClick={applyLatestAssistantReply} disabled={assistantMessages.length < 2}>
                Use Last Reply
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAssistantInput("Rewrite the introduction as valid LaTeX with a stronger formal tone.")}
              >
                Rewrite Intro
              </Button>
            </div>
            <Textarea
              value={assistantInput}
              onChange={(event) => setAssistantInput(event.target.value)}
              placeholder="Ask me to improve a section, explain results, or return replacement LaTeX..."
              className="min-h-[92px] resize-none rounded-2xl border-border/70 bg-background/75 text-white placeholder:text-slate-400 caret-white"
            />
            <Button className="mt-3 w-full" onClick={() => void handleAssist()} disabled={assisting || !assistantInput.trim()}>
              <Send className="mr-2 h-4 w-4" />
              {assisting ? "Thinking..." : "Ask Assistant"}
            </Button>
          </div>
        </aside>
      </div>
    </div>
  );
}
