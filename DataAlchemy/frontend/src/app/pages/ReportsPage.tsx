import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Bot,
  Download,
  FileText,
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
    sections: [],
    artifacts: [],
    assistant_context: {},
  };
}

function reportTitleFromDraft(draft: string, fallback: string) {
  const line = draft.split("\n").find((item) => item.trim().startsWith("# "));
  return line ? line.replace(/^#\s+/, "").trim() : fallback;
}

export function ReportsPage() {
  const [uploads, setUploads] = useState<RecentUploadItem[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [report, setReport] = useState<ReportDocument | null>(null);
  const [draftText, setDraftText] = useState("");
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantMessages, setAssistantMessages] = useState<AssistantMessage[]>([
    {
      role: "assistant",
      content:
        "I can help turn the generated analysis into a polished technical report. Ask me to rewrite a section, strengthen conclusions, or make the tone more formal.",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [assisting, setAssisting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const runtimeSnapshot = loadAgentRuntimeSnapshot();
  const runtimeResults =
    runtimeSnapshot?.datasetId === selectedDatasetId ? runtimeSnapshot.execution?.results ?? [] : [];

  const contextSummary = useMemo(() => {
    if (!report?.assistant_context) return [];
    const overview = report.assistant_context.dataset_overview as Record<string, unknown> | undefined;
    const rows = typeof overview?.rows_sampled === "number" ? overview.rows_sampled : 0;
    const cols = typeof overview?.total_columns === "number" ? overview.total_columns : 0;
    const artifacts = Array.isArray(report.artifacts) ? report.artifacts.length : 0;
    return [
      `${rows.toLocaleString()} sampled rows`,
      `${cols} columns`,
      `${artifacts} artifact${artifacts === 1 ? "" : "s"} in context`,
    ];
  }, [report]);

  useEffect(() => {
    void initializePage();
  }, []);

  useEffect(() => {
    if (selectedDatasetId) {
      void loadReport(selectedDatasetId);
    }
  }, [selectedDatasetId]);

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
      setDraftText(nextReport.draft_markdown ?? "");
      setSavedAt(saved?.updated_at ?? null);
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
      setDraftText(generated.result.draft_markdown ?? "");
      setSavedAt(new Date().toISOString());
      setAssistantMessages([
        {
          role: "assistant",
          content:
            "The report agent drafted a technical report using the latest run context. Ask me to tighten the prose, rewrite a section, or tailor it for a specific audience.",
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
        title: reportTitleFromDraft(draftText, report.title),
        draft_markdown: draftText,
      };
      const saved = await saveReport(selectedDatasetId, payload);
      setReport(saved.content);
      setDraftText(saved.content.draft_markdown ?? draftText);
      setSavedAt(saved.updated_at);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save report");
    } finally {
      setSaving(false);
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
      const reply = await assistWithReport(selectedDatasetId, prompt, draftText);
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
    setDraftText((current) => `${current.trim()}\n\n${latestAssistant.content}`.trim());
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
                  <h1 className="text-foreground">Report Editor</h1>
                  <p className="text-sm text-muted-foreground">
                    Draft a technical report with the report agent on the left and a writing copilot on the right.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="border-blue-400/30 bg-blue-500/5 text-blue-200">
                  <BarChart3 className="mr-1.5 h-3 w-3" />
                  Technical report mode
                </Badge>
                <Badge variant="outline" className="border-border/70 bg-background/40 text-muted-foreground">
                  Hidden machine context available to assistant
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
                {generating ? "Generating..." : "Generate Draft"}
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

          <div className="mx-auto max-w-5xl">
            <Card className="border-border/60 bg-card/85 shadow-[0_24px_80px_rgba(15,23,42,0.35)] backdrop-blur">
              <CardHeader className="border-b border-border/60 pb-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <CardTitle className="text-xl text-foreground">
                      {reportTitleFromDraft(draftText, report?.title ?? "Technical report")}
                    </CardTitle>
                    <CardDescription>
                      The report agent drafts the document for you. Edit freely here while the assistant uses the hidden run context to support revisions.
                    </CardDescription>
                  </div>
                  {report?.artifacts?.length ? (
                    <div className="flex flex-wrap gap-2">
                      {report.artifacts.slice(0, 2).map((artifact, index) => {
                        const fileId = typeof artifact.file_id === "string" ? artifact.file_id : null;
                        const label = typeof artifact.name === "string" ? artifact.name : `artifact-${index + 1}`;
                        if (!fileId) return null;
                        return (
                          <a key={fileId} href={artifactDownloadUrl(fileId)} download={fileId}>
                            <Button variant="outline" size="sm" className="gap-1.5">
                              <Download className="h-3.5 w-3.5" />
                              {label}
                            </Button>
                          </a>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              </CardHeader>

              <CardContent className="p-0">
                <Textarea
                  value={draftText}
                  onChange={(event) => setDraftText(event.target.value)}
                  placeholder="Start writing your report here..."
                  className="min-h-[calc(100vh-18rem)] resize-none border-0 bg-transparent px-8 py-8 font-serif text-[15px] leading-8 text-foreground shadow-none focus-visible:ring-0"
                />
              </CardContent>
            </Card>
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
                <p className="text-sm text-muted-foreground">Always here to help shape the report</p>
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
                  Thinking about the best revision...
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
                onClick={() => setAssistantInput("Rewrite the introduction to sound more formal and publication-ready.")}
              >
                Rewrite Intro
              </Button>
            </div>
            <div className="flex gap-2">
              <Textarea
                value={assistantInput}
                onChange={(event) => setAssistantInput(event.target.value)}
                placeholder="Ask me to improve a section, explain results, or tailor the report..."
                className="min-h-[92px] resize-none rounded-2xl border-border/70 bg-background/75"
              />
            </div>
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
