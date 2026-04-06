import { useEffect, useMemo, useState } from "react";
import { Bot, Calendar, FolderKanban, Send, Sparkles } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Textarea } from "../components/ui/textarea";
import {
  createProjectPlan,
  fetchRecentUploads,
  type ProjectPlanResponse,
  type RecentUploadItem,
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

export function ProjectsPage() {
  const [uploads, setUploads] = useState<RecentUploadItem[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [userMessage, setUserMessage] = useState("Preprocess this dataset first, then train a model");
  const [planResponse, setPlanResponse] = useState<ProjectPlanResponse | null>(null);

  const [uploadsLoading, setUploadsLoading] = useState(false);
  const [planLoading, setPlanLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedDataset = useMemo(
    () => uploads.find((item) => item.file_id === selectedDatasetId) ?? null,
    [uploads, selectedDatasetId],
  );

  useEffect(() => {
    void loadDatasets();
  }, []);

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

  async function submitPlanRequest() {
    if (!selectedDatasetId) {
      setError("Select a dataset before sending a planning request.");
      return;
    }

    if (!userMessage.trim()) {
      setError("Enter your request for the Supervisor Agent.");
      return;
    }

    setPlanLoading(true);
    setError(null);

    try {
      const response = await createProjectPlan(selectedDatasetId, userMessage.trim());
      setPlanResponse(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate plan");
      setPlanResponse(null);
    } finally {
      setPlanLoading(false);
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-foreground">Projects</h1>
            <Badge variant="outline" className="gap-1.5">
              <Sparkles className="w-3 h-3 text-blue-500" />
              Supervisor Planning
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Select a dataset and describe what you want. The Supervisor Agent returns a structured workflow plan.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadDatasets()} disabled={uploadsLoading || planLoading}>
          Refresh Datasets
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Dataset Selection</CardTitle>
          <CardDescription>Choose one uploaded dataset from your database-backed upload history.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <select
            className="h-10 rounded-md border border-border bg-background px-3 text-sm w-full max-w-2xl"
            value={selectedDatasetId}
            onChange={(event) => setSelectedDatasetId(event.target.value)}
            disabled={uploadsLoading || uploads.length === 0}
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

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="w-4 h-4" />
            Supervisor Agent Chat
          </CardTitle>
          <CardDescription>
            Example requests: clean this dataset, do preprocessing first, train a model on this, generate insights and charts.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            value={userMessage}
            onChange={(event) => setUserMessage(event.target.value)}
            className="min-h-28"
            placeholder="Describe your project goal for this dataset..."
          />

          <div className="flex items-center gap-3">
            <Button onClick={() => void submitPlanRequest()} disabled={planLoading || uploadsLoading || !selectedDatasetId}>
              <Send className="w-4 h-4 mr-2" />
              {planLoading ? "Planning..." : "Generate Plan"}
            </Button>
            {!selectedDatasetId && <p className="text-xs text-muted-foreground">Select a dataset first.</p>}
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
        </CardContent>
      </Card>

      {planResponse && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Supervisor Summary</CardTitle>
              <CardDescription>Interpreted user goal and high-level intent.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="secondary" className="capitalize">
                  Goal: {prettyGoal(planResponse.user_goal)}
                </Badge>
                <Badge variant="outline">Dataset: {planResponse.dataset_id}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{planResponse.summary}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FolderKanban className="w-4 h-4" />
                Structured Workflow Plan
              </CardTitle>
              <CardDescription>Returned by backend Supervisor planning service.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {planResponse.plan.map((item, index) => (
                  <div key={`${item.step}-${index}`} className="rounded-lg border border-border p-4 bg-card">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div>
                        <p className="text-sm text-foreground">{index + 1}. {item.step}</p>
                        <p className="text-xs text-muted-foreground mt-1">Agent: {item.agent}</p>
                      </div>
                      <Badge variant="outline" className="capitalize">{item.status}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
