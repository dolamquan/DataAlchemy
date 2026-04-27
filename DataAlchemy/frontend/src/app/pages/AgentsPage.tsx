import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Brain,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileBarChart,
  Filter,
  FlaskConical,
  GitBranch,
  HardDrive,
  Orbit,
  Radio,
  RefreshCw,
  ShieldCheck,
  Upload,
  Wrench,
} from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Progress } from "../components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  AGENT_RUNTIME_STORAGE_KEY,
  clearAgentRuntimeSnapshot,
  loadAgentRuntimeSnapshot,
  saveAgentRuntimeEvents,
  type AgentRuntimeSnapshot,
} from "../lib/agentRuntimeStore";
import {
  artifactDownloadUrl,
  authorizedWebsocketUrl,
  fetchSupervisorExecutionEvents,
  fetchSupervisorExecutionStatus,
  resetSupervisorRuntime,
  type AgentRuntimeEvent,
  type CoordinatorExecutionResult,
  type ProjectPlanResponse,
  type ProjectPlanStep,
} from "../lib/uploadsApi";

type AgentStatus = "active" | "idle" | "degraded" | "offline";
type StepStatus = "completed" | "in_progress" | "pending" | "failed";
type AgentRole = "supervisor" | "coordinator" | "worker";
type ConnectionState = "disconnected" | "connecting" | "live";

interface AgentRecord {
  id: string;
  name: string;
  role: AgentRole;
  status: AgentStatus;
  lastTask: string;
  lastUpdated: string;
  progressPercent?: number;
  progressMessage?: string;
  outputs: string[];
  artifacts: AgentArtifact[];
  logs: Array<{ timestamp: string; message: string }>;
}

interface AgentArtifact {
  label: string;
  type?: string;
  fileId?: string;
  downloadUrl?: string;
}

interface WorkflowStep {
  step: string;
  assignedAgent: string;
  status: StepStatus;
  output: string;
}

interface FlowStage {
  id: string;
  label: string;
  detail: string;
  status: StepStatus;
}

const CORE_AGENT_REGISTRY: Array<{ id: string; name: string; role: AgentRole }> = [
  { id: "supervisor", name: "Supervisor", role: "supervisor" },
  { id: "coordinator", name: "Coordinator", role: "coordinator" },
  { id: "data_quality_agent", name: "Data Quality Agent", role: "worker" },
  { id: "model_training_agent", name: "Model Training Agent", role: "worker" },
  { id: "evaluation_agent", name: "Evaluate Agent", role: "worker" },
  { id: "report_agent", name: "Report Agent", role: "worker" },
];

const KNOWN_AGENT_DETAILS: Record<string, { name: string; role: AgentRole }> = {
  supervisor: { name: "Supervisor", role: "supervisor" },
  coordinator: { name: "Coordinator", role: "coordinator" },
  data_preprocessing_agent: { name: "Data Preprocessing Agent", role: "worker" },
  data_quality_agent: { name: "Data Quality Agent", role: "worker" },
  model_training_agent: { name: "Model Training Agent", role: "worker" },
  evaluation_agent: { name: "Evaluate Agent", role: "worker" },
  report_agent: { name: "Report Agent", role: "worker" },
};

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

function titleizeAgent(agentId: string) {
  return agentId
    .replace(/_agent$/, "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function agentDisplayName(agentId: string) {
  return KNOWN_AGENT_DETAILS[agentId]?.name ?? titleizeAgent(agentId);
}

function statusBadgeClass(status: AgentStatus | StepStatus) {
  if (status === "active" || status === "completed") return "border-green-500/40 text-green-400";
  if (status === "idle" || status === "pending") return "border-slate-500/40 text-slate-300";
  if (status === "in_progress") return "border-blue-500/40 text-blue-400";
  if (status === "degraded") return "border-amber-500/40 text-amber-400";
  return "border-red-500/40 text-red-400";
}

function roleIcon(role: AgentRole) {
  if (role === "supervisor") return <Brain className="w-4 h-4 text-blue-400" />;
  if (role === "coordinator") return <Orbit className="w-4 h-4 text-violet-400" />;
  return <Wrench className="w-4 h-4 text-cyan-400" />;
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
    if (seen.has(key)) {
      continue;
    }
    merged.push(event);
    seen.add(key);
  }
  return merged;
}

function summarizeResult(result: CoordinatorExecutionResult | undefined) {
  if (!result?.result) return "No output reported yet";
  if (typeof result.result === "string") return result.result;
  if (typeof result.result !== "object") return String(result.result);

  const payload = result.result as Record<string, unknown>;
  if (typeof payload.message === "string") return payload.message;
  if (typeof payload.error === "string") return payload.error;
  if (typeof payload.chosen_model === "string") return `Trained ${payload.chosen_model}`;
  if (typeof payload.quality_score === "number") return `Quality score ${payload.quality_score.toFixed(2)}`;
  if (typeof payload.preprocessed_file_id === "string") return `Prepared ${payload.preprocessed_file_id}`;

  return "Structured result returned";
}

function artifactFromPayload(artifact: Record<string, unknown>): AgentArtifact {
  const name = artifact.name ?? artifact.file_id ?? artifact.path ?? artifact.type;
  const fileId = typeof artifact.file_id === "string" ? artifact.file_id : undefined;
  const type = typeof artifact.type === "string" ? artifact.type : undefined;

  return {
    label: typeof name === "string" ? name : "Generated artifact",
    type,
    fileId,
    downloadUrl: fileId ? artifactDownloadUrl(fileId) : undefined,
  };
}

function artifactKey(artifact: AgentArtifact) {
  return artifact.fileId ?? `${artifact.label}-${artifact.type ?? "artifact"}`;
}

function latestEventForStep(events: AgentRuntimeEvent[], stepName: string) {
  return [...events].reverse().find((event) => event.step === stepName);
}

function latestProgressEvent(events: AgentRuntimeEvent[], agentId: string) {
  return [...events].reverse().find(
    (event) => event.agent === agentId && event.type === "step_progress" && typeof event.progress_percent === "number",
  );
}

function stepStatusFromEvents(events: AgentRuntimeEvent[], step: ProjectPlanStep, snapshot: AgentRuntimeSnapshot | null) {
  const event = latestEventForStep(events, step.step);
  if (event?.type === "step_failed") return "failed";
  if (event?.type === "step_completed") return "completed";
  if (["step_started", "step_retried", "repair_started", "repair_succeeded"].includes(event?.type ?? "")) {
    return "in_progress";
  }

  const execution = snapshot?.execution;
  if (execution?.failed_step === step.step) return "failed";
  if (execution?.completed_steps.includes(step.step)) return "completed";
  return "pending";
}

function buildWorkflow(snapshot: AgentRuntimeSnapshot | null, events: AgentRuntimeEvent[]): WorkflowStep[] {
  const plan = snapshot?.plan?.plan ?? [];
  const execution = snapshot?.execution;

  return plan.map((step) => {
    const event = latestEventForStep(events, step.step);
    const result = execution?.results.find((item) => item.step === step.step);

    return {
      step: step.step,
      assignedAgent: step.agent,
      status: stepStatusFromEvents(events, step, snapshot),
      output: event?.message ?? summarizeResult(result),
    };
  });
}

function buildFlowStages(snapshot: AgentRuntimeSnapshot | null, workflowSteps: WorkflowStep[]): FlowStage[] {
  const hasSnapshot = !!snapshot;
  const hasPlan = !!snapshot?.plan;
  const hasExecution = workflowSteps.some((step) => step.status !== "pending");
  const hasFailure = workflowSteps.some((step) => step.status === "failed");
  const allDone = workflowSteps.length > 0 && workflowSteps.every((step) => step.status === "completed");

  return [
    {
      id: "upload",
      label: "Upload CSV",
      detail: "Upload API stores file and metadata.",
      status: hasSnapshot ? "completed" : "pending",
    },
    {
      id: "schema",
      label: "Schema Extraction",
      detail: "Schema profile is attached to supervisor context.",
      status: hasSnapshot ? "completed" : "pending",
    },
    {
      id: "chat",
      label: "Chat + Plan",
      detail: "Supervisor drafts structured plan JSON.",
      status: hasPlan ? "completed" : hasSnapshot ? "in_progress" : "pending",
    },
    {
      id: "coordinator",
      label: "Coordinator Runtime",
      detail: "Coordinator dispatches worker agents in order.",
      status: hasFailure ? "failed" : allDone ? "completed" : hasExecution ? "in_progress" : "pending",
    },
    {
      id: "storage",
      label: "Artifacts + Storage",
      detail: "Agents save datasets, models, reports, and outputs.",
      status: allDone ? "completed" : hasExecution ? "in_progress" : "pending",
    },
    {
      id: "download",
      label: "Report / Download",
      detail: "Final report and downloadable outputs are surfaced to UI.",
      status: allDone ? "completed" : "pending",
    },
  ];
}

function buildActivity(snapshot: AgentRuntimeSnapshot | null, events: AgentRuntimeEvent[]) {
  if (events.length > 0) {
    return [...events].reverse().map((event, index) => ({
      timestamp: event.timestamp,
      event: `${agentDisplayName(event.agent ?? "coordinator")}${event.step ? ` / ${event.step}` : ""}: ${
        event.message ?? event.status ?? event.type
      }`,
      key: eventKey(event, index),
    }));
  }

  if (!snapshot) return [];

  const updates = snapshot.execution?.dashboard_updates ?? [];
  const activity = updates.map((update, index) => ({
    timestamp: snapshot.capturedAt,
    event: `${agentDisplayName(update.agent ?? "coordinator")}${update.step ? ` / ${update.step}` : ""}: ${
      update.message ?? update.status ?? "Update emitted"
    }`,
    key: `snapshot-${index}-${update.agent ?? "agent"}-${update.step ?? "step"}`,
  }));

  return [
    {
      timestamp: snapshot.capturedAt,
      event:
        snapshot.responseType === "final"
          ? `Coordinator finished with status ${snapshot.execution?.status ?? "unknown"}`
          : "Supervisor drafted a plan and is awaiting confirmation",
      key: "snapshot-captured",
    },
    ...activity,
  ];
}

function buildAgentRegistry(snapshot: AgentRuntimeSnapshot | null, events: AgentRuntimeEvent[]) {
  const registry = [...CORE_AGENT_REGISTRY];
  const seen = new Set(registry.map((agent) => agent.id));
  const planAgents = snapshot?.plan?.plan.map((step) => step.agent) ?? [];
  const eventAgents = events.map((event) => event.agent).filter((agent): agent is string => !!agent);

  for (const agentId of [...planAgents, ...eventAgents]) {
    if (seen.has(agentId)) continue;
    const details = KNOWN_AGENT_DETAILS[agentId] ?? { name: titleizeAgent(agentId), role: "worker" as const };
    registry.push({ id: agentId, ...details });
    seen.add(agentId);
  }

  return registry;
}

function buildAgents(snapshot: AgentRuntimeSnapshot | null, events: AgentRuntimeEvent[]): AgentRecord[] {
  const timestamp = events.at(-1)?.timestamp ?? snapshot?.capturedAt ?? new Date().toISOString();
  const planSteps = snapshot?.plan?.plan ?? [];
  const execution = snapshot?.execution;
  const activity = buildActivity(snapshot, events);
  const registry = buildAgentRegistry(snapshot, events);

  return registry.map((agent) => {
    const assignedSteps = planSteps.filter((step) => step.agent === agent.id);
    const agentEvents = events.filter((event) => event.agent === agent.id);
    const latestAgentEvent = agentEvents.at(-1);
    const latestProgress = latestProgressEvent(events, agent.id);
    const activeStep = [...agentEvents].reverse().find((event) => event.type === "step_started");
    const failedStep = [...agentEvents].reverse().find((event) => event.type === "step_failed");
    const completedStep = [...agentEvents].reverse().find((event) => event.type === "step_completed");
    const completedSteps = assignedSteps.filter((step) => execution?.completed_steps.includes(step.step));
    const results = execution?.results.filter((item) => item.agent === agent.id) ?? [];
    const artifacts = [
      ...(execution?.artifacts ?? []),
      ...agentEvents.flatMap((event) => event.artifacts ?? []),
    ].map(artifactFromPayload);

    let status: AgentStatus = snapshot ? "idle" : "offline";
    if (snapshot?.responseType === "proposal" && agent.id === "supervisor") status = "active";
    if (
      ["step_started", "step_retried", "repair_started", "repair_succeeded", "coordinator_started"].includes(
        latestAgentEvent?.type ?? "",
      )
    ) {
      status = "active";
    }
    if (agent.id === "coordinator" && events.some((event) => event.type === "coordinator_started")) {
      status = "active";
    }
    if (latestAgentEvent?.type === "step_completed" || latestAgentEvent?.type === "coordinator_completed") status = "idle";
    if (failedStep || latestAgentEvent?.type === "coordinator_failed" || latestAgentEvent?.type === "step_failed") {
      status = "degraded";
    }
    if (agent.id === "coordinator" && events.some((event) => event.type === "coordinator_completed")) {
      status = "idle";
    }
    if (agent.id === "coordinator" && events.some((event) => event.type === "coordinator_failed")) {
      status = "degraded";
    }

    const lastTask =
      failedStep?.step ??
      activeStep?.step ??
      completedStep?.step ??
      completedSteps.at(-1)?.step ??
      assignedSteps.at(-1)?.step;
    const outputs = [
      ...agentEvents.filter((event) => event.message).map((event) => String(event.message)),
      ...results.map(summarizeResult),
    ];

    if (agent.id === "supervisor" && snapshot?.plan?.summary) outputs.unshift(snapshot.plan.summary);
    if (agent.id === "coordinator" && execution) outputs.unshift(`${execution.completed_steps.length} step(s) completed`);

    return {
      id: agent.id,
      name: agent.name,
      role: agent.role,
      status,
      lastTask: lastTask ?? (snapshot ? "Waiting for assignment" : "No runtime snapshot"),
      lastUpdated: latestAgentEvent?.timestamp ?? timestamp,
      progressPercent: latestProgress?.progress_percent,
      progressMessage: latestProgress?.message,
      outputs: outputs.length > 0 ? outputs : ["No output reported yet"],
      artifacts: Array.from(new Map(artifacts.map((artifact) => [artifactKey(artifact), artifact])).values()),
      logs: activity
        .filter((item) => item.event.includes(agent.name) || (agent.id === "coordinator" && item.event.includes("Coordinator")))
        .map((item) => ({ timestamp: item.timestamp, message: item.event })),
    };
  });
}

function planFromEvents(events: AgentRuntimeEvent[], snapshot: AgentRuntimeSnapshot | null): ProjectPlanResponse | null {
  const eventPlan = [...events].reverse().find((event) => event.plan)?.plan;
  return eventPlan ?? snapshot?.plan ?? null;
}

export function AgentsPage() {
  const [statusFilter, setStatusFilter] = useState<"all" | AgentStatus>("all");
  const [selectedAgent, setSelectedAgent] = useState<AgentRecord | null>(null);
  const [snapshot, setSnapshot] = useState<AgentRuntimeSnapshot | null>(() => loadAgentRuntimeSnapshot());
  const [events, setEvents] = useState<AgentRuntimeEvent[]>(() => loadAgentRuntimeSnapshot()?.events ?? []);
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const [stoppingRun, setStoppingRun] = useState(false);

  function refreshSnapshot() {
    const next = loadAgentRuntimeSnapshot();
    setSnapshot(next);
    setEvents(next?.events ?? []);
  }

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === AGENT_RUNTIME_STORAGE_KEY) refreshSnapshot();
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener("agent-runtime-updated", refreshSnapshot);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("agent-runtime-updated", refreshSnapshot);
    };
  }, []);

  useEffect(() => {
    if (!snapshot?.sessionId) {
      setConnectionState("disconnected");
      return;
    }

    setConnectionState("connecting");
    let cancelled = false;
    let socket: WebSocket | null = null;

    const connect = async () => {
      const url = authorizedWebsocketUrl(snapshot.sessionId);
      if (cancelled) return;

      socket = new WebSocket(url);
      socket.onopen = () => setConnectionState("live");
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as AgentRuntimeEvent;
        setEvents((current) => {
          const next = [...current, event];
          saveAgentRuntimeEvents(snapshot.sessionId, next);
          return next;
        });
      };
      socket.onclose = () => setConnectionState("disconnected");
      socket.onerror = () => setConnectionState("disconnected");
    };

    void connect();

    return () => {
      cancelled = true;
      socket?.close();
    };
  }, [snapshot?.sessionId]);

  useEffect(() => {
    if (!snapshot?.sessionId || connectionState === "live") {
      return;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const [status, response] = await Promise.all([
          fetchSupervisorExecutionStatus(snapshot.sessionId),
          fetchSupervisorExecutionEvents(snapshot.sessionId, 500),
        ]);
        if (cancelled) {
          return;
        }

        const current = loadAgentRuntimeSnapshot();
        if (current && current.sessionId === snapshot.sessionId) {
          localStorage.setItem(
            AGENT_RUNTIME_STORAGE_KEY,
            JSON.stringify({
              ...current,
              datasetId: status.dataset_id,
              capturedAt: status.updated_at,
              plan: status.plan,
              events: mergeEvents(current.events ?? [], response.events),
            }),
          );
          window.dispatchEvent(new Event("agent-runtime-updated"));
        }

        setEvents((existing) => mergeEvents(existing, response.events));
      } catch {
        // Best-effort fallback polling should not disrupt live UI.
      }
    };

    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 4000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [snapshot?.sessionId, connectionState]);

  async function handleStopRun() {
    setStoppingRun(true);
    try {
      await resetSupervisorRuntime();
      clearAgentRuntimeSnapshot();
      setSnapshot(null);
      setEvents([]);
      setSelectedAgent(null);
    } finally {
      setStoppingRun(false);
    }
  }

  const livePlan = useMemo(() => planFromEvents(events, snapshot), [events, snapshot]);
  const runtimeSnapshot = useMemo(
    () => (snapshot && livePlan ? { ...snapshot, plan: livePlan } : snapshot),
    [livePlan, snapshot],
  );
  const agents = useMemo(() => buildAgents(runtimeSnapshot, events), [runtimeSnapshot, events]);
  const workflowSteps = useMemo(() => buildWorkflow(runtimeSnapshot, events), [runtimeSnapshot, events]);
  const flowStages = useMemo(() => buildFlowStages(runtimeSnapshot, workflowSteps), [runtimeSnapshot, workflowSteps]);
  const activityFeed = useMemo(() => buildActivity(runtimeSnapshot, events), [runtimeSnapshot, events]);

  const filteredAgents = useMemo(() => {
    if (statusFilter === "all") return agents;
    return agents.filter((agent) => agent.status === statusFilter);
  }, [agents, statusFilter]);

  useEffect(() => {
    if (!selectedAgent) return;
    const updatedAgent = agents.find((agent) => agent.id === selectedAgent.id);
    if (!updatedAgent) {
      setSelectedAgent(null);
      return;
    }
    if (updatedAgent !== selectedAgent) {
      setSelectedAgent(updatedAgent);
    }
  }, [agents, selectedAgent]);

  const metrics = useMemo(() => {
    const failedSteps = workflowSteps.filter((step) => step.status === "failed").length;
    return {
      totalAgents: agents.length,
      activeAgents: agents.filter((agent) => agent.status === "active").length,
      completedTasks: workflowSteps.filter((step) => step.status === "completed").length,
      failedTasks: failedSteps,
      artifactsGenerated: new Set(agents.flatMap((agent) => agent.artifacts.map(artifactKey))).size,
    };
  }, [agents, workflowSteps]);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-foreground">Agent Control Center</h1>
            <Badge variant="outline" className="gap-1.5 capitalize">
              <Radio className="w-3 h-3 text-cyan-400" />
              {connectionState === "live" ? "Live Runtime" : connectionState}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Observe Supervisor, Coordinator, Data Quality, Model Training, Evaluate, and Report agents as a plan runs.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="gap-1.5 bg-emerald-500/10 text-emerald-300 border-emerald-500/30">
            <ShieldCheck className="w-3 h-3" />
            {runtimeSnapshot?.sessionId ? `Session ${runtimeSnapshot.sessionId}` : "No session selected"}
          </Badge>
          {runtimeSnapshot?.sessionId && (
            <Button variant="outline" className="gap-2" onClick={() => void handleStopRun()} disabled={stoppingRun}>
              <AlertTriangle className="w-4 h-4" />
              {stoppingRun ? "Stopping Run..." : "Stop Current Run"}
            </Button>
          )}
          <Button variant="outline" className="gap-2" onClick={refreshSnapshot}>
            <RefreshCw className="w-4 h-4" />
            Refresh Runtime
          </Button>
        </div>
      </div>

      {runtimeSnapshot && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Current Run</CardTitle>
            <CardDescription>
              Dataset {runtimeSnapshot.datasetId} captured {formatDate(runtimeSnapshot.capturedAt)}
            </CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {runtimeSnapshot.plan?.summary ?? "Supervisor has not produced a plan yet."}
          </CardContent>
        </Card>
      )}

      {!runtimeSnapshot && (
        <Card className="border-dashed">
          <CardHeader>
            <CardTitle>No Agent Run Yet</CardTitle>
            <CardDescription>
              Start a supervisor session on Projects, then open this page before confirming the plan to watch progress live.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Agents</CardDescription>
            <CardTitle className="text-2xl">{metrics.totalAgents}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <Bot className="w-3.5 h-3.5" /> Runtime registry
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active Agents</CardDescription>
            <CardTitle className="text-2xl">{metrics.activeAgents}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <Activity className="w-3.5 h-3.5" /> Streaming now
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completed Steps</CardDescription>
            <CardTitle className="text-2xl">{metrics.completedTasks}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5" /> Coordinator-confirmed
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Failed Steps</CardDescription>
            <CardTitle className="text-2xl">{metrics.failedTasks}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5" /> Needs attention
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Artifacts</CardDescription>
            <CardTitle className="text-2xl">{metrics.artifactsGenerated}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <FileBarChart className="w-3.5 h-3.5" /> Produced outputs
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="w-4 h-4" /> Filter Agents
          </CardTitle>
          <CardDescription>Filter cards by current runtime status.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {(["all", "active", "idle", "degraded", "offline"] as const).map((status) => (
              <Button
                key={status}
                size="sm"
                variant={statusFilter === status ? "default" : "outline"}
                onClick={() => setStatusFilter(status)}
                className="capitalize"
              >
                {status}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Running Agents</CardTitle>
          <CardDescription>Click any agent to inspect live outputs, artifacts, and event logs.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredAgents.map((agent) => (
              <button
                key={agent.id}
                type="button"
                onClick={() => setSelectedAgent(agent)}
                className="text-left rounded-lg border border-border bg-card p-4 hover:border-blue-500/40 hover:bg-muted/20 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{agent.name}</p>
                    <p className="text-xs text-muted-foreground capitalize">Role: {agent.role}</p>
                  </div>
                  {roleIcon(agent.role)}
                </div>

                <div className="mt-3 flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className={`capitalize ${statusBadgeClass(agent.status)}`}>
                    {agent.status}
                  </Badge>
                </div>

                {typeof agent.progressPercent === "number" && agent.status !== "idle" && (
                  <div className="mt-3 space-y-1.5">
                    <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                      <span className="truncate">{agent.progressMessage ?? "In progress"}</span>
                      <span>{agent.progressPercent}%</span>
                    </div>
                    <Progress value={agent.progressPercent} className="h-1.5" />
                  </div>
                )}

                <div className="mt-3 space-y-1.5 text-xs text-muted-foreground">
                  <p className="truncate">Last task: {agent.lastTask}</p>
                  <p>Last updated: {formatDate(agent.lastUpdated)}</p>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="w-4 h-4" /> Runtime Flow
          </CardTitle>
          <CardDescription>
            This mirrors the upload, schema, supervisor, coordinator, agent execution, storage, and download path.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-3">
            {flowStages.map((stage, index) => {
              const Icon =
                stage.id === "upload" ? Upload :
                stage.id === "schema" ? Database :
                stage.id === "chat" ? Brain :
                stage.id === "coordinator" ? Orbit :
                stage.id === "storage" ? HardDrive :
                FileBarChart;

              return (
                <div key={stage.id} className="rounded-lg border border-border bg-background p-3">
                  <div className="flex items-start justify-between gap-2">
                    <Icon className="w-4 h-4 text-muted-foreground" />
                    <Badge variant="outline" className={`capitalize ${statusBadgeClass(stage.status)}`}>
                      {stage.status.replaceAll("_", " ")}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm font-medium text-foreground">{index + 1}. {stage.label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{stage.detail}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="w-4 h-4" /> Workflow Tracker
            </CardTitle>
            <CardDescription>Plan steps update as websocket events arrive.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              {workflowSteps.length === 0 && (
                <div className="rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground">
                  No plan steps to supervise yet.
                </div>
              )}
              {workflowSteps.map((item, index) => (
                <div key={`${item.step}-${index}`} className="rounded-lg border border-border bg-background p-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <p className="text-sm text-foreground">{index + 1}. {item.step}</p>
                    <Badge variant="outline" className={`capitalize ${statusBadgeClass(item.status)}`}>
                      {item.status.replaceAll("_", " ")}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Assigned: {agentDisplayName(item.assignedAgent)}</p>
                  <p className="text-xs text-muted-foreground">Output: {item.output}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock3 className="w-4 h-4" /> Activity Feed
            </CardTitle>
            <CardDescription>Live orchestration events from the coordinator stream.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[420px] overflow-auto pr-1">
              {activityFeed.length === 0 && (
                <div className="rounded-md border border-dashed border-border p-2.5 text-sm text-muted-foreground">
                  No activity emitted yet.
                </div>
              )}
              {activityFeed.map((item) => (
                <div key={item.key} className="rounded-md border border-border bg-background p-2.5">
                  <p className="text-xs text-muted-foreground">{formatDate(item.timestamp)}</p>
                  <p className="text-sm text-foreground mt-1">{item.event}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Delegation Table</CardTitle>
          <CardDescription>Coordinator step assignments and current outputs.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Step</TableHead>
                <TableHead>Assigned Agent</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Output</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {workflowSteps.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-muted-foreground">
                    No coordinator delegation available yet.
                  </TableCell>
                </TableRow>
              )}
              {workflowSteps.map((row) => (
                <TableRow key={row.step}>
                  <TableCell className="font-medium">{row.step}</TableCell>
                  <TableCell>{agentDisplayName(row.assignedAgent)}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`capitalize ${statusBadgeClass(row.status)}`}>
                      {row.status.replaceAll("_", " ")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{row.output}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={!!selectedAgent} onOpenChange={(open) => !open && setSelectedAgent(null)}>
        <DialogContent className="max-w-3xl">
          {selectedAgent && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {roleIcon(selectedAgent.role)}
                  {selectedAgent.name}
                </DialogTitle>
                <DialogDescription>Live runtime snapshot including outputs, artifacts, and event logs.</DialogDescription>
              </DialogHeader>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Card className="md:col-span-1">
                  <CardHeader className="pb-2">
                    <CardDescription>Status</CardDescription>
                    <CardTitle className="text-base capitalize">{selectedAgent.status}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-xs text-muted-foreground">Role: {selectedAgent.role}</CardContent>
                </Card>

                <Card className="md:col-span-2">
                  <CardHeader className="pb-2">
                    <CardDescription>Last Task</CardDescription>
                    <CardTitle className="text-base">{selectedAgent.lastTask}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-xs text-muted-foreground">
                    Last updated: {formatDate(selectedAgent.lastUpdated)}
                    {typeof selectedAgent.progressPercent === "number" && (
                      <div className="mt-3 space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <span>{selectedAgent.progressMessage ?? "In progress"}</span>
                          <span>{selectedAgent.progressPercent}%</span>
                        </div>
                        <Progress value={selectedAgent.progressPercent} className="h-2" />
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2"><Database className="w-4 h-4" /> Outputs</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {selectedAgent.outputs.map((out, idx) => (
                      <p key={idx} className="text-sm text-muted-foreground rounded border border-border p-2">{out}</p>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2"><FlaskConical className="w-4 h-4" /> Artifacts</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {selectedAgent.artifacts.length === 0 && <p className="text-sm text-muted-foreground">No artifacts generated.</p>}
                    {selectedAgent.artifacts.map((artifact, idx) => (
                      <div key={artifactKey(artifact) || idx} className="rounded border border-border p-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm text-muted-foreground truncate">{artifact.label}</p>
                            <p className="text-[11px] text-muted-foreground">
                              {artifact.fileId ? artifact.fileId : artifact.type ?? "Inline artifact"}
                            </p>
                          </div>
                          {artifact.downloadUrl && (
                            <a href={artifact.downloadUrl} download={artifact.fileId} onClick={(event) => event.stopPropagation()}>
                              <Button variant="outline" size="sm" className="gap-1.5 text-xs">
                                <Download className="w-3.5 h-3.5" />
                                Download
                              </Button>
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Recent Logs</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 max-h-44 overflow-auto pr-1">
                  {selectedAgent.logs.length === 0 && <p className="text-sm text-muted-foreground">No logs for this agent yet.</p>}
                  {selectedAgent.logs.map((log, idx) => (
                    <div key={idx} className="rounded border border-border p-2">
                      <p className="text-xs text-muted-foreground">{formatDate(log.timestamp)}</p>
                      <p className="text-sm text-foreground mt-1">{log.message}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
