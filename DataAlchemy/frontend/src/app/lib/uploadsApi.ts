export const API_BASE_URL = "http://127.0.0.1:8000";

export interface RecentUploadItem {
  file_id: string;
  original_filename: string;
  file_size_bytes: number;
  created_at: string;
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
}

async function parseJsonOrThrow<T>(response: Response, context: string): Promise<T> {
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
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

export async function sendSupervisorMessage(
  sessionId: string,
  userMessage: string,
): Promise<SupervisorResponse> {
  const response = await fetch(`${API_BASE_URL}/api/supervisor/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, user_message: userMessage }),
  });
  return parseJsonOrThrow<SupervisorResponse>(response, "Send supervisor message");
}
