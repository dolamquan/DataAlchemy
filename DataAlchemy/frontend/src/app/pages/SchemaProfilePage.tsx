import { useEffect, useMemo, useState } from "react";
import { AlertCircle, BarChart3, CheckCircle2, Columns3, Database, Hash, RefreshCw, Type } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import {
  fetchRecentUploads,
  fetchSchemaInsights,
  fetchSchemaProfile,
  type RecentUploadItem,
  type SchemaInsights,
  type SchemaProfile,
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

function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export function SchemaProfilePage() {
  const [uploads, setUploads] = useState<RecentUploadItem[]>([]);
  const [uploadsLoading, setUploadsLoading] = useState(false);
  const [uploadsError, setUploadsError] = useState<string | null>(null);

  const [selectedFileId, setSelectedFileId] = useState<string>("");
  const [schemaProfile, setSchemaProfile] = useState<SchemaProfile | null>(null);
  const [insights, setInsights] = useState<SchemaInsights | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [selectedNumericColumn, setSelectedNumericColumn] = useState<string>("");
  const [selectedCategoricalColumn, setSelectedCategoricalColumn] = useState<string>("");

  const selectedUpload = useMemo(
    () => uploads.find((item) => item.file_id === selectedFileId) ?? null,
    [uploads, selectedFileId],
  );

  const selectedNumericDistribution = useMemo(
    () => insights?.numeric_distributions.find((item) => item.column === selectedNumericColumn) ?? null,
    [insights, selectedNumericColumn],
  );

  const selectedCategoricalFrequency = useMemo(
    () => insights?.categorical_frequencies.find((item) => item.column === selectedCategoricalColumn) ?? null,
    [insights, selectedCategoricalColumn],
  );

  useEffect(() => {
    void loadUploads();
  }, []);

  useEffect(() => {
    if (!selectedFileId) return;
    void loadDetails(selectedFileId);
  }, [selectedFileId]);

  useEffect(() => {
    const firstNumeric = insights?.numeric_distributions[0]?.column ?? "";
    setSelectedNumericColumn((current) => current || firstNumeric);

    const firstCategorical = insights?.categorical_frequencies[0]?.column ?? "";
    setSelectedCategoricalColumn((current) => current || firstCategorical);
  }, [insights]);

  async function loadUploads() {
    setUploadsLoading(true);
    setUploadsError(null);

    try {
      const items = await fetchRecentUploads(50);
      setUploads(items);

      if (items.length > 0) {
        setSelectedFileId((current) => current || items[0].file_id);
      } else {
        setSelectedFileId("");
        setSchemaProfile(null);
        setInsights(null);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load uploads.";
      setUploadsError(message);
    } finally {
      setUploadsLoading(false);
    }
  }

  async function loadDetails(fileId: string) {
    setDetailLoading(true);
    setDetailError(null);

    try {
      const [schemaPayload, insightsPayload] = await Promise.all([
        fetchSchemaProfile(fileId),
        fetchSchemaInsights(fileId),
      ]);
      setSchemaProfile(schemaPayload);
      setInsights(insightsPayload);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load dataset details.";
      setDetailError(message);
      setSchemaProfile(null);
      setInsights(null);
    } finally {
      setDetailLoading(false);
    }
  }

  const previewRows = schemaProfile?.preview_rows ?? [];
  const previewColumns = previewRows.length > 0 ? Array.from(new Set(previewRows.flatMap((row) => Object.keys(row)))) : [];

  const typeCountsData = insights
    ? [
        { label: "Numeric", count: insights.column_type_counts.numeric },
        { label: "Categorical", count: insights.column_type_counts.categorical },
        { label: "Boolean", count: insights.column_type_counts.boolean },
      ]
    : [];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-foreground">Schema Profile</h1>
            <Badge variant="outline" className="gap-1.5">
              <CheckCircle2 className="w-3 h-3 text-green-500" />
              Live Data
            </Badge>
          </div>
          <p className="text-muted-foreground text-sm">
            Select an uploaded CSV to inspect schema, preview rows, and generated insights.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => void loadUploads()} disabled={uploadsLoading || detailLoading}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Dataset Selection</CardTitle>
          <CardDescription>Pick one uploaded dataset to load profile and insights.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 max-w-xl">
            <label className="text-sm text-muted-foreground">Uploaded files</label>
            <select
              className="h-10 rounded-md border border-border bg-background px-3 text-sm"
              disabled={uploadsLoading || uploads.length === 0}
              value={selectedFileId}
              onChange={(event) => setSelectedFileId(event.target.value)}
            >
              {uploads.length === 0 && <option value="">No uploaded files available</option>}
              {uploads.map((item) => (
                <option key={item.file_id} value={item.file_id}>
                  {item.original_filename} ({formatBytes(item.file_size_bytes)})
                </option>
              ))}
            </select>
          </div>

          {uploadsLoading && <p className="text-sm text-muted-foreground">Loading uploaded files...</p>}
          {uploadsError && <p className="text-sm text-red-600">{uploadsError}</p>}
          {!uploadsLoading && uploads.length === 0 && !uploadsError && (
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              No datasets found yet. Upload a CSV from the Upload page to begin schema profiling.
            </div>
          )}
        </CardContent>
      </Card>

      {selectedUpload && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Selected File</CardDescription>
              <CardTitle className="text-base truncate">{selectedUpload.original_filename}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{selectedUpload.file_id}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>File Size</CardDescription>
              <CardTitle className="text-base">{formatBytes(selectedUpload.file_size_bytes)}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">Stored in upload history</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Uploaded At</CardDescription>
              <CardTitle className="text-base">{formatDate(selectedUpload.created_at)}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">UTC timestamp from backend</CardContent>
          </Card>
        </div>
      )}

      {detailLoading && (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">Loading schema profile and insights...</CardContent>
        </Card>
      )}

      {detailError && (
        <Card>
          <CardContent className="pt-6 text-sm text-red-600">{detailError}</CardContent>
        </Card>
      )}

      {!detailLoading && !detailError && selectedFileId && !schemaProfile && (
        <Card>
          <CardHeader>
            <CardTitle>Schema Unavailable</CardTitle>
            <CardDescription>This file has no saved schema profile yet.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Re-upload this CSV to regenerate profiling metadata and insights.
          </CardContent>
        </Card>
      )}

      {!detailLoading && !detailError && schemaProfile && insights && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardDescription>Total Columns</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <Columns3 className="w-5 h-5 text-blue-500" />
                </div>
                <div className="text-3xl text-foreground">{insights.summary.total_columns}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardDescription>Numeric Columns</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                  <Hash className="w-5 h-5 text-green-500" />
                </div>
                <div className="text-3xl text-foreground">{insights.summary.numeric_columns}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardDescription>Categorical Columns</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
                  <Type className="w-5 h-5 text-amber-500" />
                </div>
                <div className="text-3xl text-foreground">{insights.summary.categorical_columns}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardDescription>Columns With Missing</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
                  <AlertCircle className="w-5 h-5 text-orange-500" />
                </div>
                <div className="text-3xl text-foreground">{insights.summary.columns_with_missing_values}</div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Column Type Distribution</CardTitle>
                <CardDescription>Numeric vs categorical vs boolean column counts</CardDescription>
              </CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={typeCountsData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="var(--color-chart-1)" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top Null Columns</CardTitle>
                <CardDescription>Columns with highest missing value counts</CardDescription>
              </CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={insights.columns_by_null_ratio}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" interval={0} angle={-25} textAnchor="end" height={75} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="null_count" fill="var(--color-chart-5)" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Top Unique Columns</CardTitle>
              <CardDescription>Columns with highest unique value counts</CardDescription>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={insights.columns_by_unique_count}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" interval={0} angle={-25} textAnchor="end" height={75} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="unique_count" fill="var(--color-chart-2)" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Numeric Distribution
                </CardTitle>
                <CardDescription>Histogram-style distribution for selected numeric column</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <select
                  className="h-10 rounded-md border border-border bg-background px-3 text-sm w-full"
                  value={selectedNumericColumn}
                  onChange={(event) => setSelectedNumericColumn(event.target.value)}
                  disabled={(insights.numeric_distributions?.length ?? 0) === 0}
                >
                  {(insights.numeric_distributions ?? []).length === 0 && (
                    <option value="">No numeric columns available</option>
                  )}
                  {(insights.numeric_distributions ?? []).map((item) => (
                    <option key={item.column} value={item.column}>{item.column}</option>
                  ))}
                </select>

                {selectedNumericDistribution ? (
                  <>
                    <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                      <div>Min: {selectedNumericDistribution.stats?.min ?? "-"}</div>
                      <div>Max: {selectedNumericDistribution.stats?.max ?? "-"}</div>
                      <div>Mean: {selectedNumericDistribution.stats?.mean ?? "-"}</div>
                      <div>Median: {selectedNumericDistribution.stats?.median ?? "-"}</div>
                    </div>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={selectedNumericDistribution.bins}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="label" interval={1} tick={{ fontSize: 10 }} />
                          <YAxis allowDecimals={false} />
                          <Tooltip />
                          <Bar dataKey="count" fill="var(--color-chart-3)" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">No numeric distribution data available.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="w-4 h-4" />
                  Categorical Frequency
                </CardTitle>
                <CardDescription>Top category frequencies for selected categorical column</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <select
                  className="h-10 rounded-md border border-border bg-background px-3 text-sm w-full"
                  value={selectedCategoricalColumn}
                  onChange={(event) => setSelectedCategoricalColumn(event.target.value)}
                  disabled={(insights.categorical_frequencies?.length ?? 0) === 0}
                >
                  {(insights.categorical_frequencies ?? []).length === 0 && (
                    <option value="">No categorical columns available</option>
                  )}
                  {(insights.categorical_frequencies ?? []).map((item) => (
                    <option key={item.column} value={item.column}>{item.column}</option>
                  ))}
                </select>

                {selectedCategoricalFrequency ? (
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={selectedCategoricalFrequency.values}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="value" interval={0} angle={-25} textAnchor="end" height={75} />
                        <YAxis allowDecimals={false} />
                        <Tooltip />
                        <Bar dataKey="count" fill="var(--color-chart-4)" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No categorical frequency data available.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Schema Table</CardTitle>
              <CardDescription>Detailed per-column profile metrics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Column</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Null Count</TableHead>
                      <TableHead>Null Ratio</TableHead>
                      <TableHead>Unique Count</TableHead>
                      <TableHead>Sample Values</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {schemaProfile.columns.map((column) => (
                      <TableRow key={column.name}>
                        <TableCell className="font-mono text-xs">{column.name}</TableCell>
                        <TableCell>{column.inferred_dtype}</TableCell>
                        <TableCell>{column.null_count}</TableCell>
                        <TableCell>{formatPercent(column.null_ratio ?? 0)}</TableCell>
                        <TableCell>{column.unique_count}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {(column.sample_values ?? []).slice(0, 5).join(", ") || "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Preview Rows</CardTitle>
              <CardDescription>Quick sample of uploaded data</CardDescription>
            </CardHeader>
            <CardContent>
              {previewRows.length === 0 ? (
                <p className="text-sm text-muted-foreground">No preview rows available for this dataset.</p>
              ) : (
                <div className="rounded-lg border border-border overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {previewColumns.map((name) => (
                          <TableHead key={name} className="font-mono text-xs">{name}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {previewRows.map((row, idx) => (
                        <TableRow key={idx}>
                          {previewColumns.map((name) => (
                            <TableCell key={name} className="text-xs text-muted-foreground">
                              {String(row[name] ?? "-")}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
