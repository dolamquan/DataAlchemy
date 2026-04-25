import type { AgentRuntimeEvent, CoordinatorExecution, ProjectPlanResponse, SupervisorResponse } from "./uploadsApi";

export const AGENT_RUNTIME_STORAGE_KEY = "dataalchemy.latestAgentRuntime";

export interface AgentRuntimeSnapshot {
  sessionId: string;
  datasetId: string;
  capturedAt: string;
  responseType: SupervisorResponse["type"];
  plan: ProjectPlanResponse | null;
  execution: CoordinatorExecution | null;
  events?: AgentRuntimeEvent[];
}

export function saveAgentRuntimeSnapshot(response: SupervisorResponse, datasetId: string) {
  const current = loadAgentRuntimeSnapshot();
  const events = current?.sessionId === response.session_id ? current.events ?? [] : [];
  const snapshot: AgentRuntimeSnapshot = {
    sessionId: response.session_id,
    datasetId,
    capturedAt: new Date().toISOString(),
    responseType: response.type,
    plan: response.plan ?? null,
    execution: response.execution ?? null,
    events,
  };

  localStorage.setItem(AGENT_RUNTIME_STORAGE_KEY, JSON.stringify(snapshot));
  window.dispatchEvent(new Event("agent-runtime-updated"));
}

export function saveAgentRuntimeEvents(sessionId: string, events: AgentRuntimeEvent[]) {
  const current = loadAgentRuntimeSnapshot();
  if (!current || current.sessionId !== sessionId) return;

  localStorage.setItem(
    AGENT_RUNTIME_STORAGE_KEY,
    JSON.stringify({
      ...current,
      events,
    }),
  );
  window.dispatchEvent(new Event("agent-runtime-updated"));
}

export function loadAgentRuntimeSnapshot(): AgentRuntimeSnapshot | null {
  const raw = localStorage.getItem(AGENT_RUNTIME_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as AgentRuntimeSnapshot;
    if (!parsed || typeof parsed !== "object" || !parsed.sessionId) return null;
    return parsed;
  } catch {
    return null;
  }
}


export function clearAgentRuntimeSnapshot() {
  localStorage.removeItem(AGENT_RUNTIME_STORAGE_KEY);
  window.dispatchEvent(new Event("agent-runtime-updated"));
}
