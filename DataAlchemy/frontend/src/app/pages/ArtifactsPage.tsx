import { useEffect, useMemo, useState } from "react";
import { Download, HardDrive, RefreshCw, Search } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { artifactDownloadUrl, fetchArtifacts, type ArtifactListItem } from "../lib/uploadsApi";

function formatBytes(bytes?: number | null) {
  if (bytes === undefined || bytes === null) return "-";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const idx = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, idx)).toFixed(2)} ${units[idx]}`;
}

function formatDate(iso?: string | null) {
  if (!iso) return "Unknown";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "Unknown" : date.toLocaleString();
}

function labelForArtifact(item: ArtifactListItem) {
  return item.label?.trim() || item.file_id;
}

export function ArtifactsPage() {
  const [artifacts, setArtifacts] = useState<ArtifactListItem[]>([]);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"all" | "execution" | "report" | "derived">("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadArtifacts() {
    setLoading(true);
    setError(null);
    try {
      setArtifacts(await fetchArtifacts());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load artifacts");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadArtifacts();
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return artifacts.filter((item) => {
      if (sourceFilter !== "all" && item.source !== sourceFilter) return false;
      if (!needle) return true;
      return [
        item.file_id,
        item.label,
        item.dataset_id,
        item.dataset_name,
        item.agent,
        item.step,
        item.type,
        item.source,
      ]
        .filter((value): value is string => typeof value === "string" && value.length > 0)
        .some((value) => value.toLowerCase().includes(needle));
    });
  }, [artifacts, query, sourceFilter]);

  const counts = useMemo(
    () => ({
      total: artifacts.length,
      downloadable: artifacts.filter((item) => item.downloadable).length,
      reports: artifacts.filter((item) => item.source === "report").length,
      execution: artifacts.filter((item) => item.source === "execution").length,
    }),
    [artifacts],
  );

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-foreground">Artifacts</h1>
            <Badge variant="outline" className="gap-1.5">
              <HardDrive className="w-3 h-3 text-cyan-400" />
              Download Library
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Browse generated outputs from preprocessing, training, evaluation, and reporting.
          </p>
        </div>
        <Button variant="outline" className="gap-2" onClick={() => void loadArtifacts()} disabled={loading}>
          <RefreshCw className="w-4 h-4" />
          {loading ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Artifacts</CardDescription>
            <CardTitle className="text-2xl">{counts.total}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Downloadable</CardDescription>
            <CardTitle className="text-2xl">{counts.downloadable}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Report Files</CardDescription>
            <CardTitle className="text-2xl">{counts.reports}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Execution Outputs</CardDescription>
            <CardTitle className="text-2xl">{counts.execution}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Browse</CardTitle>
          <CardDescription>Search by filename, dataset, agent, step, or artifact type.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col lg:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search artifacts..."
                className="pl-9"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {(["all", "execution", "report", "derived"] as const).map((value) => (
                <Button
                  key={value}
                  size="sm"
                  variant={sourceFilter === value ? "default" : "outline"}
                  onClick={() => setSourceFilter(value)}
                  className="capitalize"
                >
                  {value}
                </Button>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="space-y-3">
            {!loading && filtered.length === 0 && (
              <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                No artifacts matched the current filters.
              </div>
            )}

            {filtered.map((item) => (
              <div key={item.file_id} className="rounded-lg border border-border bg-background p-4">
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                  <div className="min-w-0 space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium text-foreground truncate">{labelForArtifact(item)}</p>
                      <Badge variant="outline" className="capitalize">{item.source ?? "artifact"}</Badge>
                      {item.type && <Badge variant="secondary">{item.type}</Badge>}
                      {!item.exists && <Badge variant="destructive">Missing</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground break-all">{item.file_id}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>Dataset: {item.dataset_name ?? item.dataset_id ?? "Unknown"}</span>
                      <span>Agent: {item.agent ?? "Unknown"}</span>
                      <span>Step: {item.step ?? "Unknown"}</span>
                      <span>Created: {formatDate(item.created_at)}</span>
                      <span>Size: {formatBytes(item.file_size_bytes)}</span>
                    </div>
                  </div>

                  {item.downloadable ? (
                    <a href={artifactDownloadUrl(item.file_id)} download={item.file_id}>
                      <Button variant="outline" className="gap-2">
                        <Download className="w-4 h-4" />
                        Download
                      </Button>
                    </a>
                  ) : (
                    <Button variant="outline" disabled>
                      Unavailable
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
