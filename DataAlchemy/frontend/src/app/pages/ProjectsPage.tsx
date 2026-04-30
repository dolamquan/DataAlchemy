import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Activity, AlertTriangle, Bot, Calendar, CheckCircle, Clock3, Download, FolderKanban, Send, Sparkles, User } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Progress } from "../components/ui/progress";
import { Textarea } from "../components/ui/textarea";
import {
  artifactDownloadUrl,
  authorizedWebsocketUrl,
  fetchSupervisorExecutionEvents,
  type CoordinatorExecution,
  type AgentRuntimeEvent,
  fetchSupervisorExecutionStatus,
  fetchRecentUploads,
  resetSupervisorRuntime,
  type PlanExecutionEstimate,
  sendSupervisorMessage,
  startSupervisorSession,
  type ProjectPlanResponse,
  type RecentUploadItem,
  type SupervisorResponse,
  type SupervisorExecutionStatus,
} from "../lib/uploadsApi";
import { clearAgentRuntimeSnapshot, saveAgentRuntimeEvents, saveAgentRuntimeSnapshot } from "../lib/agentRuntimeStore";

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

function formatDuration(totalSeconds?: number | null) {
  if (typeof totalSeconds !== "number" || !Number.isFinite(totalSeconds) || totalSeconds <= 0) return null;
  if (totalSeconds < 60) return `${Math.round(totalSeconds)}s`;

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.round(totalSeconds % 60);
  if (seconds === 0 || minutes >= 10) return `${minutes} min`;
  return `${minutes} min ${seconds}s`;
}

function formatDurationRange(low?: number | null, high?: number | null) {
  const lowLabel = formatDuration(low);
  const highLabel = formatDuration(high);
  if (!lowLabel && !highLabel) return null;
  if (!lowLabel) return highLabel;
  if (!highLabel) return lowLabel;
  if (lowLabel === highLabel) return lowLabel;
  return `${lowLabel} to ${highLabel}`;
}

function eventKey(event: AgentRuntimeEvent, index: number) {
  return `${event.id ?? "noid"}-${event.step_index ?? "nostep"}-${event.timestamp}-${event.type}-${event.agent ?? "agent"}-${event.step ?? "run"}-${index}`;
}

function mergeEvents(existing: AgentRuntimeEvent[], incoming: AgentRuntimeEvent[]) {
  const merged = [...existing];
  const seen = new Set(
    existing.map((event) => `${event.id ?? ""}|${event.timestamp}|${event.type}|${event.agent ?? ""}|${event.step ?? ""}|${event.step_index ?? ""}`),
  );

  for (const event of incoming) {
    const key = `${event.id ?? ""}|${event.timestamp}|${event.type}|${event.agent ?? ""}|${event.step ?? ""}|${event.step_index ?? ""}`;
    if (seen.has(key)) continue;
    merged.push(event);
    seen.add(key);
  }

  return merged;
}

function latestEventForStep(events: AgentRuntimeEvent[], stepName: string) {
  return [...events].reverse().find((event) => event.step === stepName);
}

function latestTerminalEventForStep(events: AgentRuntimeEvent[], stepName: string) {
  return [...events].reverse().find(
    (event) =>
      event.step === stepName &&
      ["step_completed", "step_failed", "repair_failed"].includes(event.type),
  );
}

function latestProgressForStep(events: AgentRuntimeEvent[], stepName: string) {
  const terminalEvent = latestTerminalEventForStep(events, stepName);
  if (terminalEvent?.type === "step_completed") {
    return undefined;
  }
  return [...events].reverse().find(
    (event) => event.step === stepName && event.type === "step_progress" && typeof event.progress_percent === "number",
  );
}

function summarizeEventResult(result: unknown) {
  if (!result) return null;
  if (typeof result === "string") return result;
  if (typeof result !== "object") return String(result);

  const payload = result as Record<string, unknown>;
  if (typeof payload.message === "string" && payload.message.trim()) return payload.message;
  if (typeof payload.error === "string" && payload.error.trim()) return payload.error;
  if (typeof payload.chosen_model === "string") {
    if (typeof payload.target_column === "string") {
      return `Trained ${payload.chosen_model} using ${payload.target_column}`;
    }
    return `Trained ${payload.chosen_model}`;
  }
  if (typeof payload.quality_score === "number") return `Quality score ${payload.quality_score.toFixed(2)}`;
  if (typeof payload.preprocessed_file_id === "string") return `Prepared ${payload.preprocessed_file_id}`;
  if (typeof payload.model_file_id === "string") return `Saved ${payload.model_file_id}`;
  return null;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  plan?: ProjectPlanResponse | null;
  execution?: CoordinatorExecution | null;
  isFinal?: boolean;
}

interface ProjectsPageState {
  selectedDatasetId: string;
  inputValue: string;
  chatMessages: ChatMessage[];
  sessionId: string | null;
  isFinalized: boolean;
}

const PROJECTS_PAGE_STATE_KEY = "dataalchemy.projectsPageState";

const EMPTY_PROJECTS_PAGE_STATE: ProjectsPageState = {
  selectedDatasetId: "",
  inputValue: "",
  chatMessages: [],
  sessionId: null,
  isFinalized: false,
};

function loadProjectsPageState(): ProjectsPageState {
  try {
    const raw = window.localStorage.getItem(PROJECTS_PAGE_STATE_KEY);
    if (!raw) return EMPTY_PROJECTS_PAGE_STATE;

    const parsed = JSON.parse(raw) as Partial<ProjectsPageState>;
    return {
      selectedDatasetId: typeof parsed.selectedDatasetId === "string" ? parsed.selectedDatasetId : "",
      inputValue: typeof parsed.inputValue === "string" ? parsed.inputValue : "",
      chatMessages: Array.isArray(parsed.chatMessages) ? parsed.chatMessages : [],
      sessionId: typeof parsed.sessionId === "string" ? parsed.sessionId : null,
      isFinalized: parsed.isFinalized === true,
    };
  } catch {
    return EMPTY_PROJECTS_PAGE_STATE;
  }
}

function saveProjectsPageState(state: ProjectsPageState) {
  try {
    window.localStorage.setItem(PROJECTS_PAGE_STATE_KEY, JSON.stringify(state));
  } catch {
    // If browser storage is unavailable, the page still works with in-memory state.
  }
}

function getExecutionStepState(stepName: string, execution?: CoordinatorExecution | null) {
  if (!execution) return "pending";
  if (execution.failed_step === stepName) return "failed";
  if (execution.completed_steps.includes(stepName)) return "completed";
  return "pending";
}

function getLiveStepState(
  step: ProjectPlanStep,
  events: AgentRuntimeEvent[],
  execution?: CoordinatorExecution | null,
) {
  const terminalEvent = latestTerminalEventForStep(events, step.step);
  if (terminalEvent?.type === "step_failed" || terminalEvent?.type === "repair_failed") return "failed";
  if (terminalEvent?.type === "step_completed") return "completed";

  const event = latestEventForStep(events, step.step);
  if (event?.type === "step_failed" || event?.type === "repair_failed") return "failed";
  if (event?.type === "step_completed") return "completed";
  if (
    ["step_started", "step_progress", "step_retried", "repair_started", "repair_succeeded"].includes(event?.type ?? "")
  ) {
    return "in_progress";
  }
  const fallback = getExecutionStepState(step.step, execution);
  if (fallback !== "pending") return fallback;
  if (step.status === "completed") return "completed";
  if (step.status === "in_progress") return "in_progress";
  if (step.status === "blocked") return "failed";
  return "pending";
}

function applyExecutionStatusToPlan(plan: ProjectPlanResponse, status: SupervisorExecutionStatus): ProjectPlanResponse {
  const completedCount = Math.max(0, status.progress?.completed ?? 0);
  const currentIndex = status.current_step_index;

  return {
    ...plan,
    plan: plan.plan.map((step, index) => {
      let nextStatus = step.status;
      if (status.failed_step === step.step) {
        nextStatus = "blocked";
      } else if (index < completedCount) {
        nextStatus = "completed";
      } else if (
        status.status === "running" &&
        typeof currentIndex === "number" &&
        currentIndex === index
      ) {
        nextStatus = "in_progress";
      } else {
        nextStatus = "pending";
      }

      return {
        ...step,
        status: nextStatus,
      };
    }),
  };
}

function stepBadgeClass(state: string) {
  if (state === "completed") return "border-green-600 text-green-700";
  if (state === "failed") return "";
  if (state === "in_progress") return "border-blue-500/50 text-blue-600";
  return "capitalize";
}

function artifactName(artifact: Record<string, unknown>) {
  const value = artifact.name ?? artifact.file_id ?? artifact.path ?? artifact.type;
  return typeof value === "string" ? value : "Generated artifact";
}

function artifactFileId(artifact: Record<string, unknown>) {
  return typeof artifact.file_id === "string" ? artifact.file_id : null;
}

interface TrainingResult {
  chosen_model: string;
  cv_score: number;
  metric: string;
  task_type: string;
  target_column: string;
  target_inferred: boolean;
  n_samples: number;
  n_features: number;
  training_time_seconds: number;
  model_file_id: string;
}

function TrainingResultCard({ execution }: { execution?: CoordinatorExecution | null }) {
  if (!execution || execution.status !== "success") return null;

  const entry = execution.results.find((r) => r.agent === "model_training_agent");
  if (!entry?.result) return null;

  const r = entry.result as TrainingResult;
  if (!r.chosen_model) return null;

  return (
    <Card className="border-blue-500/30 bg-blue-950/20">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <span>Training Results</span>
          <Badge variant="outline" className="border-green-500/40 text-green-400 text-xs">
            {r.task_type}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <div className="rounded-md border border-border bg-background p-2">
            <p className="text-[11px] text-muted-foreground">Model</p>
            <p className="text-sm text-foreground font-medium truncate">{r.chosen_model}</p>
          </div>
          <div className="rounded-md border border-border bg-background p-2">
            <p className="text-[11px] text-muted-foreground">{r.metric}</p>
            <p className="text-sm text-foreground font-medium">{r.cv_score.toFixed(4)}</p>
          </div>
          <div className="rounded-md border border-border bg-background p-2">
            <p className="text-[11px] text-muted-foreground">Target</p>
            <p className="text-sm text-foreground truncate">
              {r.target_column}
              {r.target_inferred && (
                <span className="text-muted-foreground"> (inferred)</span>
              )}
            </p>
          </div>
          <div className="rounded-md border border-border bg-background p-2">
            <p className="text-[11px] text-muted-foreground">Dataset</p>
            <p className="text-sm text-foreground">{r.n_samples.toLocaleString()} × {r.n_features}</p>
          </div>
        </div>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">Trained in {r.training_time_seconds}s</p>
          <a href={artifactDownloadUrl(r.model_file_id)} download={r.model_file_id}>
            <Button variant="outline" size="sm" className="gap-1.5 text-xs">
              <Download className="w-3.5 h-3.5" />
              Download model (.joblib)
            </Button>
          </a>
        </div>
      </CardContent>
    </Card>
  );
}

function ExecutionEstimateCard({ estimate }: { estimate?: PlanExecutionEstimate | null }) {
  if (!estimate) return null;

  const totalLabel = formatDurationRange(estimate.total_seconds_low, estimate.total_seconds_high);
  const trainingLabel = formatDurationRange(estimate.training_seconds_low, estimate.training_seconds_high);

  return (
    <Card className="border-amber-500/30 bg-amber-50/60">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Clock3 className="w-4 h-4" />
          Expected Runtime
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div className="rounded-md border border-border bg-background p-2">
            <p className="text-[11px] text-muted-foreground">Whole plan</p>
            <p className="text-sm text-foreground font-medium">{totalLabel ?? "Estimating..."}</p>
          </div>
          {trainingLabel && (
            <div className="rounded-md border border-border bg-background p-2">
              <p className="text-[11px] text-muted-foreground">Training phase</p>
              <p className="text-sm text-foreground font-medium">{trainingLabel}</p>
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground">{estimate.summary}</p>
      </CardContent>
    </Card>
  );
}

function ExecutionPanel({
  plan,
  execution,
  events,
}: {
  plan: ProjectPlanResponse;
  execution?: CoordinatorExecution | null;
  events: AgentRuntimeEvent[];
}) {
  const coordinatorFailed = events.some((event) => event.type === "coordinator_failed");
  const coordinatorCompleted = events.some((event) => event.type === "coordinator_completed");
  const coordinatorStarted = events.some((event) => event.type === "coordinator_started");
  const status = execution?.status ?? (coordinatorFailed ? "failed" : coordinatorCompleted ? "success" : coordinatorStarted ? "running" : "pending");
  const activityFeed = [...events].reverse().map((event, index) => ({
    key: eventKey(event, index),
    timestamp: event.timestamp,
    event: `${event.agent ?? "agent"}${event.step ? ` / ${event.step}` : ""}: ${event.message ?? event.status ?? event.type}`,
  }));

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

      <ExecutionEstimateCard estimate={plan.execution_estimate} />

      <div className="space-y-2">
        {plan.plan.map((item, index) => {
          const state = getLiveStepState(item, events, execution);
          const progress = latestProgressForStep(events, item.step);
          const latestEvent = latestTerminalEventForStep(events, item.step) ?? latestEventForStep(events, item.step);
          const output =
            (latestEvent?.type === "step_completed"
              ? summarizeEventResult(latestEvent.result) ?? summarizeEventResult(latestEvent.result_summary)
              : null)
            ?? latestEvent?.message
            ?? "Waiting for this step to start.";

          return (
            <div key={`${item.step}-${index}-execution`} className="rounded-md border border-border bg-background p-2.5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <p className="text-xs text-foreground">
                  {index + 1}. {item.step}
                </p>
                <Badge
                  variant={state === "failed" ? "destructive" : "outline"}
                  className={stepBadgeClass(state)}
                >
                  {state.replaceAll("_", " ")}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">Agent: {item.agent}</p>
              <p className="text-[11px] text-muted-foreground mt-1">Output: {output}</p>
              {typeof progress?.progress_percent === "number" && state === "in_progress" && (
                <div className="mt-3 space-y-1.5">
                  <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                    <span className="truncate">{progress.message ?? "In progress"}</span>
                    <span>{progress.progress_percent}%</span>
                  </div>
                  <Progress value={progress.progress_percent} className="h-1.5" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <TrainingResultCard execution={execution} />

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

      {!!activityFeed.length && (
        <div className="rounded-md border border-border bg-background p-2.5">
          <p className="text-xs font-medium text-foreground mb-2 flex items-center gap-2">
            <Activity className="w-3.5 h-3.5" />
            Live Activity
          </p>
          <div className="space-y-1.5 max-h-36 overflow-auto pr-1">
            {activityFeed.map((item) => (
              <div key={item.key}>
                <p className="text-[11px] text-muted-foreground">{formatDate(item.timestamp)}</p>
                <p className="text-[11px] text-foreground mt-0.5">{item.event}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!!execution?.artifacts?.length && (
        <div className="rounded-md border border-border bg-background p-2.5">
          <p className="text-xs font-medium text-foreground mb-2">Artifacts</p>
          <div className="space-y-2">
            {execution.artifacts.map((artifact, idx) => {
              const fileId = artifactFileId(artifact);
              return (
                <div key={`${artifactName(artifact)}-${idx}`} className="flex items-center justify-between gap-2 rounded border border-border p-2">
                  <div className="min-w-0">
                    <p className="text-xs text-foreground truncate">{artifactName(artifact)}</p>
                    <p className="text-[11px] text-muted-foreground truncate">
                      {fileId ?? "Inline artifact"}
                    </p>
                  </div>
                  {fileId && (
                    <a href={artifactDownloadUrl(fileId)} download={fileId}>
                      <Button variant="outline" size="sm" className="gap-1.5 text-xs">
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </Button>
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function PlanCard({ plan, isFinal }: { plan: ProjectPlanResponse; isFinal?: boolean }) {
  const totalLabel = formatDurationRange(
    plan.execution_estimate?.total_seconds_low,
    plan.execution_estimate?.total_seconds_high,
  );

  return (
    <div className="space-y-3 mt-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={isFinal ? "default" : "secondary"} className="capitalize">
          {isFinal ? "Final Plan" : "Draft Plan"} — {prettyGoal(plan.user_goal)}
        </Badge>
        {totalLabel && (
          <Badge variant="outline" className="gap-1.5">
            <Clock3 className="w-3 h-3" />
            Expected runtime {totalLabel}
          </Badge>
        )}
      </div>
      <p className="text-sm text-muted-foreground">{plan.summary}</p>
      {plan.execution_estimate?.summary && (
        <p className="text-xs text-muted-foreground">{plan.execution_estimate.summary}</p>
      )}
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
  const navigate = useNavigate();
  const [storedPageState] = useState(loadProjectsPageState);
  const [uploads, setUploads] = useState<RecentUploadItem[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(storedPageState.selectedDatasetId);
  const [inputValue, setInputValue] = useState(storedPageState.inputValue);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(storedPageState.chatMessages);
  const [sessionId, setSessionId] = useState<string | null>(storedPageState.sessionId);
  const [isFinalized, setIsFinalized] = useState(storedPageState.isFinalized);
  const [runtimeEvents, setRuntimeEvents] = useState<AgentRuntimeEvent[]>([]);

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
    saveProjectsPageState({
      selectedDatasetId,
      inputValue,
      chatMessages,
      sessionId,
      isFinalized,
    });
  }, [selectedDatasetId, inputValue, chatMessages, sessionId, isFinalized]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  async function resetRuntimeState() {
    clearAgentRuntimeSnapshot();
    setChatMessages([]);
    setSessionId(null);
    setIsFinalized(false);
    setRuntimeEvents([]);
    setInputValue("");
    setError(null);

    try {
      await resetSupervisorRuntime();
    } catch {
      // Still clear local runtime state even if the backend reset fails.
    }
  }

  useEffect(() => {
    if (!sessionId || !isFinalized) {
      return;
    }

    let cancelled = false;
    let socket: WebSocket | null = null;

    const syncExecution = async () => {
      try {
        const status = await fetchSupervisorExecutionStatus(sessionId);
        if (cancelled) {
          return;
        }

        setChatMessages((current) => {
          const next = current.map((message, index) =>
            index === current.length - 1 && message.role === "assistant" && message.isFinal
              ? {
                  ...message,
                  plan: applyExecutionStatusToPlan(message.plan ?? status.plan, status),
                  execution: status.execution ?? message.execution,
                }
              : message,
          );

          const finalMessage = next.at(-1);
          if (finalMessage?.role === "assistant" && finalMessage.isFinal) {
            saveAgentRuntimeSnapshot(
              {
                session_id: sessionId,
                type: "final",
                message: finalMessage.content,
                plan: finalMessage.plan ?? applyExecutionStatusToPlan(status.plan, status),
                execution: finalMessage.execution ?? null,
              },
              selectedDatasetId,
            );
          }
          return next;
        });
      } catch {
        // Best-effort polling should not interrupt the chat UI.
      }
    };

    const syncEvents = async () => {
      try {
        const payload = await fetchSupervisorExecutionEvents(sessionId);
        if (cancelled) {
          return;
        }

        setRuntimeEvents((current) => {
          const next = mergeEvents(current, payload.events);
          saveAgentRuntimeEvents(sessionId, next);
          return next;
        });
      } catch {
        // Event sync is best-effort.
      }
    };

    const connect = () => {
      const url = authorizedWebsocketUrl(sessionId);
      socket = new WebSocket(url);
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as AgentRuntimeEvent;
        setRuntimeEvents((current) => {
          const next = mergeEvents(current, [event]);
          saveAgentRuntimeEvents(sessionId, next);
          return next;
        });
      };
      socket.onclose = () => {
        if (!cancelled) {
          window.setTimeout(connect, 1500);
        }
      };
    };

    void syncExecution();
    void syncEvents();
    connect();
    const timer = window.setInterval(() => {
      void syncExecution();
      void syncEvents();
    }, 3000);

    return () => {
      cancelled = true;
      socket?.close();
      window.clearInterval(timer);
    };
  }, [isFinalized, selectedDatasetId, sessionId]);

  async function loadDatasets() {
    setUploadsLoading(true);
    setError(null);
    try {
      const items = await fetchRecentUploads(50);
      setUploads(items);
      if (items.length > 0) {
        setSelectedDatasetId((current) => {
          if (current && items.some((item) => item.file_id === current)) {
            return current;
          }
          return items[0].file_id;
        });
      } else {
        setSelectedDatasetId("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load datasets");
    } finally {
      setUploadsLoading(false);
    }
  }

  async function handleNewSession() {
    await resetRuntimeState();
  }

  function handleSupervisorResponse(response: SupervisorResponse) {
    const recoveredSession = !!sessionId && response.session_id !== sessionId;
    setSessionId(response.session_id);
    if (response.session_id !== sessionId) {
      setRuntimeEvents([]);
    }
    saveAgentRuntimeSnapshot(response, selectedDatasetId);

    const assistantMsg: ChatMessage = {
      role: "assistant",
      content: [
        recoveredSession ? "Your previous supervisor session expired, so I started a fresh one for this dataset." : "",
        response.message ?? (response.type === "final" ? "Plan confirmed and locked." : ""),
      ].filter(Boolean).join("\n\n"),
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
        response = await sendSupervisorMessage(sessionId, text, selectedDatasetId);
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
            <Button variant="outline" onClick={() => void handleNewSession()} disabled={sending}>
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
              void handleNewSession();
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
              No restorable uploaded datasets found. Use Upload Dataset to add the CSV again.
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
            <CardContent className="text-xs text-muted-foreground">
              Source: {selectedDataset.storage_source === "db" ? "database copy" : "upload storage"}
            </CardContent>
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
                  {msg.isFinal && msg.plan && <ExecutionPanel plan={msg.plan} execution={msg.execution} events={runtimeEvents} />}
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
                        : runtimeEvents.length > 0
                          ? "Plan confirmed and streaming live progress"
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
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 rounded-lg border border-green-200 bg-green-50 p-3">
              <p className="text-sm text-green-700 font-medium">
                Plan finalized. Live step progress is streaming above as each agent runs.
              </p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => void navigate("/app/agents")}>
                  Open Agents View
                </Button>
                <Button variant="outline" size="sm" onClick={handleNewSession}>
                  Start New Session
                </Button>
              </div>
            </div>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
