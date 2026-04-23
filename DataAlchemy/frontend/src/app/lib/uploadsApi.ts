export const API_BASE_URL = "http://127.0.0.1:8000";

export interface RecentUploadItem {
  file_id: string;
  original_filename: string;
  file_size_bytes: number;
  created_at: string;
  is_available?: boolean;
  storage_source?: "db" | "disk" | "missing";
}

export interface NumericStats {
  min: number;
  max: number;
  mean: number;
  median: number;
}

export interface DistributionBin {
  label: string;
  start?: number;
  end?: number;
  count: number;
}

export interface CategoricalValueCount {
  value: string;
  count: number;
}

export interface SchemaColumn {
  name: string;
  inferred_dtype: string;
  column_family?: "numeric" | "categorical" | "boolean" | "other";
  non_null_count: number;
  null_count: number;
  null_ratio: number;
  unique_count: number;
  sample_values: string[];
  numeric_stats?: NumericStats | null;
  numeric_distribution?: DistributionBin[];
  categorical_top_values?: CategoricalValueCount[];
}

export interface SchemaProfile {
  file_name: string;
  stored_file_name?: string;
  file_size_bytes?: number;
  rows_sampled: number;
  total_columns: number;
  columns: SchemaColumn[];
  preview_rows: Array<Record<string, string>>;
  notes?: string[];
}

export interface SchemaInsights {
  summary: {
    total_columns: number;
    rows_sampled: number;
    numeric_columns: number;
    categorical_columns: number;
    boolean_columns: number;
    columns_with_missing_values: number;
  };
  column_type_counts: {
    numeric: number;
    categorical: number;
    boolean: number;
    other: number;
  };
  columns_by_null_ratio: Array<{
    name: string;
    null_count: number;
    null_ratio: number;
  }>;
  columns_by_unique_count: Array<{
    name: string;
    unique_count: number;
  }>;
  numeric_distributions: Array<{
    column: string;
    stats: NumericStats;
    bins: DistributionBin[];
  }>;
  categorical_frequencies: Array<{
    column: string;
    values: CategoricalValueCount[];
  }>;
}

export type ProjectPlanStatus = "pending" | "in_progress" | "completed" | "blocked";

export interface ProjectPlanStep {
  step: string;
  agent: string;
  status: ProjectPlanStatus;
  config?: Record<string, unknown> | null;
}

export interface ProjectPlanResponse {
  dataset_id: string;
  user_goal:
    | "preprocess_only"
    | "visualize_data"
    | "schema_analysis"
    | "train_model"
    | "evaluate_model"
    | "full_pipeline"
    | "preprocess_and_train";
  summary: string;
  plan: ProjectPlanStep[];
}

export interface SupervisorResponse {
  session_id: string;
  type: "proposal" | "final";
  message: string | null;
  plan: ProjectPlanResponse | null;
  execution?: CoordinatorExecution | null;
}

export interface CoordinatorExecutionResult {
  step: string;
  agent: string;
  result?: unknown;
}

export interface CoordinatorDashboardUpdate {
  step?: string;
  agent?: string;
  status?: string;
  message?: string;
}

export interface CoordinatorExecution {
  status: "success" | "failed";
  completed_steps: string[];
  failed_step: string | null;
  results: CoordinatorExecutionResult[];
  artifacts: Array<Record<string, unknown>>;
  dashboard_updates: CoordinatorDashboardUpdate[];
}

export interface ReportSection {
  title: string;
  summary: string;
  bullets: string[];
  data: Record<string, unknown>;
}

export interface ReportDocument {
  dataset_id: string;
  title: string;
  audience?: string;
  style?: string;
  tone?: string;
  generated_at?: string;
  executive_summary: string;
  next_steps: string[];
  draft_markdown: string;
  sections: ReportSection[];
  artifacts: Array<Record<string, unknown>>;
  assistant_context?: Record<string, unknown>;
}

export interface SavedReportRecord {
  dataset_id: string;
  file_id: string;
  content: ReportDocument;
  created_at: string;
  updated_at: string;
}

export interface AgentRuntimeEvent {
  session_id: string;
  timestamp: string;
  type:
    | "coordinator_started"
    | "repair_started"
    | "repair_succeeded"
    | "repair_failed"
    | "step_started"
    | "step_retried"
    | "step_completed"
    | "step_failed"
    | "coordinator_completed"
    | "coordinator_failed";
  agent?: string;
  step?: string;
  status?: string;
  message?: string;
  plan?: ProjectPlanResponse;
  result?: unknown;
  artifacts?: Array<Record<string, unknown>>;
  dashboard_updates?: CoordinatorDashboardUpdate[];
  completed_steps?: string[];
}

async function parseJsonOrThrow<T>(response: Response, context: string): Promise<T> {
  if (!response.ok) {
    let detail = await response.text().catch(() => "");

    if (detail) {
      try {
        const payload = JSON.parse(detail) as { detail?: unknown };
        if (typeof payload.detail === "string") {
          detail = payload.detail;
        }
      } catch {
        // Keep the plain response body if it is not JSON.
      }
    }

    throw new Error(`${context} failed (${response.status})${detail ? `: ${detail}` : ""}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchRecentUploads(limit = 50): Promise<RecentUploadItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/uploads/recent?limit=${limit}`);
  const payload = await parseJsonOrThrow<{ items?: RecentUploadItem[] }>(response, "Fetch uploads");
  return Array.isArray(payload.items) ? payload.items : [];
}

export async function fetchSchemaProfile(fileId: string): Promise<SchemaProfile | null> {
  const response = await fetch(`${API_BASE_URL}/api/uploads/${encodeURIComponent(fileId)}/schema`);

  if (response.status === 404) {
    return null;
  }

  const payload = await parseJsonOrThrow<{ file_id: string; schema_profile?: SchemaProfile }>(response, "Fetch schema");
  return payload.schema_profile ?? null;
}

export async function fetchSchemaInsights(fileId: string): Promise<SchemaInsights | null> {
  const response = await fetch(`${API_BASE_URL}/api/uploads/${encodeURIComponent(fileId)}/insights`);

  if (response.status === 404) {
    return null;
  }

  const payload = await parseJsonOrThrow<{ file_id: string; insights?: SchemaInsights }>(response, "Fetch insights");
  return payload.insights ?? null;
}

export async function createProjectPlan(datasetId: string, userMessage: string): Promise<ProjectPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/projects/plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dataset_id: datasetId,
      user_message: userMessage,
    }),
  });

  return parseJsonOrThrow<ProjectPlanResponse>(response, "Create project plan");
}

export async function startSupervisorSession(
  datasetId: string,
  userMessage: string,
): Promise<SupervisorResponse> {
  const response = await fetch(`${API_BASE_URL}/api/supervisor/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, user_message: userMessage }),
  });
  return parseJsonOrThrow<SupervisorResponse>(response, "Start supervisor session");
}

export function artifactDownloadUrl(fileId: string): string {
  return `${API_BASE_URL}/api/artifacts/${encodeURIComponent(fileId)}`;
}

export async function sendSupervisorMessage(
  sessionId: string,
  userMessage: string,
  datasetId?: string,
): Promise<SupervisorResponse> {
  const response = await fetch(`${API_BASE_URL}/api/supervisor/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, user_message: userMessage, dataset_id: datasetId }),
  });
  return parseJsonOrThrow<SupervisorResponse>(response, "Send supervisor message");
}

export async function fetchSavedReport(datasetId: string): Promise<SavedReportRecord | null> {
  const response = await fetch(`${API_BASE_URL}/api/reports/${encodeURIComponent(datasetId)}`);
  if (response.status === 404) {
    return null;
  }
  return parseJsonOrThrow<SavedReportRecord>(response, "Fetch report");
}

export async function generateReport(
  datasetId: string,
  priorResults: CoordinatorExecutionResult[],
  config?: Record<string, unknown>,
): Promise<{ result: ReportDocument; artifacts: Array<Record<string, unknown>> }> {
  const response = await fetch(`${API_BASE_URL}/api/reports/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      prior_results: priorResults,
      config: config ?? {},
    }),
  });
  return parseJsonOrThrow<{ result: ReportDocument; artifacts: Array<Record<string, unknown>> }>(
    response,
    "Generate report",
  );
}

export async function saveReport(datasetId: string, content: ReportDocument): Promise<SavedReportRecord> {
  const response = await fetch(`${API_BASE_URL}/api/reports/${encodeURIComponent(datasetId)}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  const payload = await parseJsonOrThrow<{ dataset_id: string; file_id: string; content: ReportDocument }>(
    response,
    "Save report",
  );
  return {
    dataset_id: payload.dataset_id,
    file_id: payload.file_id,
    content: payload.content,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export async function assistWithReport(
  datasetId: string,
  message: string,
  currentDraft: string,
): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/reports/assist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      message,
      current_draft: currentDraft,
    }),
  });
  const payload = await parseJsonOrThrow<{ reply: string }>(response, "Assist with report");
  return payload.reply;
}
