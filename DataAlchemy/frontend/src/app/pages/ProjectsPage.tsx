import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Bot, Calendar, CheckCircle, FolderKanban, Send, Sparkles, User } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Textarea } from "../components/ui/textarea";
import {
  type CoordinatorExecution,
  fetchRecentUploads,
  sendSupervisorMessage,
  startSupervisorSession,
  type ProjectPlanResponse,
  type RecentUploadItem,
  type SupervisorResponse,
} from "../lib/uploadsApi";

function formatBytes(bytes?: number) {
  if (bytes === undefined || bytes === null) return "-";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const idx = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, idx)).toFixed(2)} ${units[idx]}`;
}

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

function prettyGoal(goal: string) {
  return goal.replaceAll("_", " ");
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  plan?: ProjectPlanResponse | null;
  execution?: CoordinatorExecution | null;
  isFinal?: boolean;
}

function getExecutionStepState(stepName: string, execution?: CoordinatorExecution | null) {
  if (!execution) return "pending";
  if (execution.failed_step === stepName) return "failed";
  if (execution.completed_steps.includes(stepName)) return "completed";
  return "pending";
}

function ExecutionPanel({ plan, execution }: { plan: ProjectPlanResponse; execution?: CoordinatorExecution | null }) {
  const status = execution?.status ?? "pending";

  return (
    <div className="mt-3 rounded-lg border border-border bg-muted/20 p-3 space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-sm font-medium text-foreground">Coordinator Execution</p>
        <Badge
          variant={status === "failed" ? "destructive" : status === "success" ? "default" : "secondary"}
          className="capitalize"
        >
          {status}
        </Badge>
      </div>

      <p className="text-xs text-muted-foreground">
        Worker agents are currently placeholder handlers. This view reflects orchestration flow and step state.
      </p>

      <div className="space-y-2">
        {plan.plan.map((item, index) => {
          const state = getExecutionStepState(item.step, execution);
          return (
            <div key={`${item.step}-${index}-execution`} className="rounded-md border border-border bg-background p-2.5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <p className="text-xs text-foreground">
                  {index + 1}. {item.step}
                </p>
                <Badge
                  variant={state === "failed" ? "destructive" : "outline"}
                  className={state === "completed" ? "border-green-600 text-green-700" : "capitalize"}
                >
                  {state}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Agent: {item.agent}</p>
            </div>
          );
        })}
      </div>

      {!!execution && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <div className="rounded-md border border-border bg-background p-2">
            <p className="text-[11px] text-muted-foreground">Completed Steps</p>
            <p className="text-sm text-foreground">{execution.completed_steps.length}</p>
          </div>
          <div className="rounded-md border border-border bg-background p-2">
            <p className="text-[11px] text-muted-foreground">Artifacts</p>
            <p className="text-sm text-foreground">{execution.artifacts.length}</p>
          </div>
          <div className="rounded-md border border-border bg-background p-2">
            <p className="text-[11px] text-muted-foreground">Failed Step</p>
            <p className="text-sm text-foreground">{execution.failed_step ?? "None"}</p>
          </div>
        </div>
      )}

      {!!execution?.dashboard_updates?.length && (
        <div className="rounded-md border border-border bg-background p-2.5">
          <p className="text-xs font-medium text-foreground mb-2">Dashboard Updates</p>
          <div className="space-y-1.5 max-h-28 overflow-auto pr-1">
            {execution.dashboard_updates.map((update, idx) => (
              <p key={idx} className="text-[11px] text-muted-foreground">
                [{update.status ?? "info"}] {update.agent ?? "agent"}/{update.step ?? "step"}: {update.message ?? "-"}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PlanCard({ plan, isFinal }: { plan: ProjectPlanResponse; isFinal?: boolean }) {
  return (
    <div className="space-y-3 mt-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={isFinal ? "default" : "secondary"} className="capitalize">
          {isFinal ? "Final Plan" : "Draft Plan"} — {prettyGoal(plan.user_goal)}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">{plan.summary}</p>
      <div className="space-y-2">
        {plan.plan.map((item, index) => (
          <div key={`${item.step}-${index}`} className="rounded-lg border border-border p-3 bg-card">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div>
                <p className="text-sm text-foreground">
                  {index + 1}. {item.step}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">Agent: {item.agent}</p>
                {item.config && Object.keys(item.config).length > 0 && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Config: {Object.entries(item.config).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")}
                  </p>
                )}
              </div>
              <Badge variant="outline" className="capitalize">
                {item.status}
              </Badge>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProjectsPage() {
  const [uploads, setUploads] = useState<RecentUploadItem[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [inputValue, setInputValue] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isFinalized, setIsFinalized] = useState(false);

  const [uploadsLoading, setUploadsLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  const selectedDataset = useMemo(
    () => uploads.find((item) => item.file_id === selectedDatasetId) ?? null,
    [uploads, selectedDatasetId],
  );

  useEffect(() => {
    void loadDatasets();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  async function loadDatasets() {
    setUploadsLoading(true);
    setError(null);
    try {
      const items = await fetchRecentUploads(50);
      setUploads(items);
      if (items.length > 0) {
        setSelectedDatasetId((current) => current || items[0].file_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load datasets");
    } finally {
      setUploadsLoading(false);
    }
  }

  function handleNewSession() {
    setChatMessages([]);
    setSessionId(null);
    setIsFinalized(false);
    setError(null);
    setInputValue("");
  }

  function handleSupervisorResponse(response: SupervisorResponse) {
    setSessionId(response.session_id);

    const assistantMsg: ChatMessage = {
      role: "assistant",
      content: response.message ?? (response.type === "final" ? "Plan confirmed and locked." : ""),
      plan: response.plan,
      execution: response.execution ?? null,
      isFinal: response.type === "final",
    };

    setChatMessages((prev) => [...prev, assistantMsg]);

    if (response.type === "final") {
      setIsFinalized(true);
    }
  }

  async function handleSend() {
    const text = inputValue.trim();
    if (!text) return;

    if (!sessionId && !selectedDatasetId) {
      setError("Select a dataset first.");
      return;
    }

    const userMsg: ChatMessage = { role: "user", content: text };
    setChatMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    setSending(true);
    setError(null);

    try {
      let response: SupervisorResponse;

      if (!sessionId) {
        response = await startSupervisorSession(selectedDatasetId, text);
      } else {
        response = await sendSupervisorMessage(sessionId, text);
      }

      handleSupervisorResponse(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!sending && !isFinalized) {
        void handleSend();
      }
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-foreground">Projects</h1>
            <Badge variant="outline" className="gap-1.5">
              <Sparkles className="w-3 h-3 text-blue-500" />
              Supervisor Agent
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Describe what you want to do with your dataset. The Supervisor will draft a plan for your review.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void loadDatasets()} disabled={uploadsLoading || sending}>
            Refresh Datasets
          </Button>
          {sessionId && (
            <Button variant="outline" onClick={handleNewSession} disabled={sending}>
              New Session
            </Button>
          )}
        </div>
      </div>

      {/* Dataset Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Dataset Selection</CardTitle>
          <CardDescription>Choose an uploaded dataset to plan against.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <select
            className="h-10 rounded-md border border-border bg-background px-3 text-sm w-full max-w-2xl"
            value={selectedDatasetId}
            onChange={(event) => {
              setSelectedDatasetId(event.target.value);
              handleNewSession();
            }}
            disabled={uploadsLoading || uploads.length === 0 || !!sessionId}
          >
            {uploads.length === 0 && <option value="">No datasets available</option>}
            {uploads.map((item) => (
              <option key={item.file_id} value={item.file_id}>
                {item.original_filename} ({formatBytes(item.file_size_bytes)})
              </option>
            ))}
          </select>
          {uploadsLoading && <p className="text-sm text-muted-foreground">Loading datasets...</p>}
          {!uploadsLoading && uploads.length === 0 && (
            <div className="text-sm text-muted-foreground rounded border border-dashed p-3">
              No uploaded datasets found. Use Upload Dataset first.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dataset Info Cards */}
      {selectedDataset && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Dataset</CardDescription>
              <CardTitle className="text-base truncate">{selectedDataset.original_filename}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">{selectedDataset.file_id}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>File Size</CardDescription>
              <CardTitle className="text-base">{formatBytes(selectedDataset.file_size_bytes)}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">From upload history</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Uploaded At</CardDescription>
              <CardTitle className="text-base">{formatDate(selectedDataset.created_at)}</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              Ready for planning
            </CardContent>
          </Card>
        </div>
      )}

      {/* Chat Interface */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="w-4 h-4" />
            Supervisor Agent Chat
          </CardTitle>
          <CardDescription>
            Tell the supervisor what you want to do. It will draft a plan for you to review and refine.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Messages */}
          <div className="min-h-[120px] max-h-[500px] overflow-y-auto space-y-4 rounded-lg border border-border p-4 bg-muted/30">
            {chatMessages.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                Start by describing your goal. For example: &quot;Train a model to predict churn using the Exited
                column&quot;
              </p>
            )}

            {chatMessages.map((msg, index) => (
              <div key={index} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "assistant" && (
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center mt-0.5">
                    <Bot className="w-4 h-4 text-blue-600" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-lg p-3 ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-background border border-border"
                  }`}
                >
                  {msg.content && <p className="text-sm whitespace-pre-wrap">{msg.content}</p>}
                  {msg.plan && <PlanCard plan={msg.plan} isFinal={msg.isFinal} />}
                  {msg.isFinal && msg.plan && <ExecutionPanel plan={msg.plan} execution={msg.execution} />}
                  {msg.isFinal && (
                    <div
                      className={`flex items-center gap-1.5 mt-3 text-xs font-medium ${
                        msg.execution?.status === "failed" ? "text-red-600" : "text-green-600"
                      }`}
                    >
                      {msg.execution?.status === "failed" ? (
                        <AlertTriangle className="w-3.5 h-3.5" />
                      ) : (
                        <CheckCircle className="w-3.5 h-3.5" />
                      )}
                      {msg.execution?.status === "failed"
                        ? "Coordinator stopped after a failed step"
                        : "Plan confirmed and handed off to Coordinator"}
                    </div>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center mt-0.5">
                    <User className="w-4 h-4 text-gray-600" />
                  </div>
                )}
              </div>
            ))}

            {sending && (
              <div className="flex gap-3 justify-start">
                <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-blue-600" />
                </div>
                <div className="bg-background border border-border rounded-lg p-3">
                  <p className="text-sm text-muted-foreground animate-pulse">Thinking...</p>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          {!isFinalized ? (
            <div className="flex gap-3">
              <Textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                className="min-h-[44px] max-h-32 resize-none"
                placeholder={
                  sessionId
                    ? "Request changes or confirm the plan..."
                    : "Describe what you want to do with this dataset..."
                }
                disabled={sending || !selectedDatasetId}
              />
              <Button
                onClick={() => void handleSend()}
                disabled={sending || !inputValue.trim() || !selectedDatasetId}
                className="self-end"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 p-3">
              <p className="text-sm text-green-700 font-medium">
                Plan finalized. Coordinator run has been visualized above.
              </p>
              <Button variant="outline" size="sm" onClick={handleNewSession}>
                Start New Session
              </Button>
            </div>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
