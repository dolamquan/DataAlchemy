// TypeScript
import { useState, useRef } from "react";
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import { Badge } from "../components/ui/badge";

interface UploadedFile {
  name: string;
  size: string;
  uploadedAt: string;
  status: "success" | "processing" | "failed";
  rows?: number;
  columns?: number;
}

interface ColumnProfile {
  name: string;
  inferred_dtype: string;
  non_null_count: number;
  null_count: number;
  null_ratio: number;
  unique_count: number;
  sample_values?: string[];
}

interface SchemaProfile {
  file_name: string;
  stored_file_name?: string;
  file_size_bytes?: number;
  rows_sampled?: number;
  total_columns?: number;
  columns?: ColumnProfile[];
  preview_rows?: Record<string, any>[];
  notes?: string[];
}

export function UploadDatasetPage() {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [recentUploads] = useState<UploadedFile[]>([
    {
      name: "customer_churn.csv",
      size: "12.4 MB",
      uploadedAt: "Apr 5, 2026 10:32 AM",
      status: "success",
      rows: 50000,
      columns: 24,
    },
    {
      name: "sales_data_q1.csv",
      size: "8.7 MB",
      uploadedAt: "Apr 4, 2026 3:15 PM",
      status: "success",
      rows: 35000,
      columns: 18,
    },
    {
      name: "product_inventory.csv",
      size: "2.1 MB",
      uploadedAt: "Apr 3, 2026 9:45 AM",
      status: "success",
      rows: 12000,
      columns: 15,
    },
  ]);

  // Upload state
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Schema profile state
  const [schemaProfile, setSchemaProfile] = useState<SchemaProfile | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = () => {
    setIsDragging(false);
  };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) {
      setSelectedFile(f);
      uploadFile(f);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    if (f) {
      setSelectedFile(f);
      uploadFile(f);
    }
  };

  async function uploadFile(file: File) {
    setError(null);
    setLoading(true);
    setUploadProgress(10);

    try {
      const fd = new FormData();
      fd.append("file", file);

      // send to backend
      const res = await fetch("http://127.0.0.1:8000/api/upload", {
        method: "POST",
        body: fd,
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `Upload failed (${res.status})`);
      }

      const data = await res.json();
      // store schema_profile and file_id as requested
      if (data?.schema_profile) {
        setSchemaProfile(data.schema_profile);
      } else {
        // some backends return profile under different key; store full response as fallback
        setSchemaProfile((data as any) ?? null);
      }
      if (data?.file_id) {
        setFileId(data.file_id);
      }

      // progress complete
      setUploadProgress(100);
      setTimeout(() => setUploadProgress(null), 800);
    } catch (err: any) {
      console.error("Upload error", err);
      setError(err?.message ?? "Upload failed");
      setUploadProgress(null);
    } finally {
      setLoading(false);
    }
  }

  // helpers
  function formatBytes(bytes?: number) {
    if (!bytes && bytes !== 0) return "—";
    const b = Number(bytes);
    if (b === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return parseFloat((b / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  // render preview rows table
  function renderPreviewRows(rows?: Record<string, any>[]) {
    if (!rows || rows.length === 0) return <div className="text-sm text-muted-foreground">No preview available</div>;
    const cols = Array.from(
      new Set(rows.flatMap((r) => Object.keys(r)))
    );
    return (
      <div className="overflow-auto border border-border rounded mt-2">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              {cols.map((c) => (
                <th key={c} className="px-3 py-2 text-left">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="odd:bg-muted/10">
                {cols.map((c) => (
                  <td key={c} className="px-3 py-2 align-top text-muted-foreground">
                    {String(r[c] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={handleFileInputChange}
      />

      {/* Header */}
      <div>
        <h1 className="text-foreground mb-2">Upload Dataset</h1>
        <p className="text-muted-foreground">
          Upload CSV files for schema profiling, validation, and AI-powered analysis. Your data is
          securely processed and validated in real-time.
        </p>
      </div>

      {/* Upload Area */}
      <Card>
        <CardContent className="pt-6">
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              border-2 border-dashed rounded-xl p-12 transition-all
              ${
                isDragging
                  ? "border-primary bg-primary/5"
                  : "border-border bg-muted/30 hover:bg-muted/50"
              }
            `}
          >
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                <Upload className="w-8 h-8 text-primary" />
              </div>
              <div>
                <h3 className="text-foreground mb-1">Drop your CSV file here</h3>
                <p className="text-sm text-muted-foreground">
                  or click to browse from your computer
                </p>
              </div>
              <Button onClick={handleBrowseClick} disabled={loading}>
                Browse Files
              </Button>
              <p className="text-xs text-muted-foreground">
                CSV files only • Maximum 500 MB • Secure encrypted upload
              </p>
            </div>

            {uploadProgress !== null && (
              <div className="mt-6 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{loading ? "Uploading..." : "Uploading..."}</span>
                  <span className="text-muted-foreground">{uploadProgress}%</span>
                </div>
                <Progress value={uploadProgress} />
                {uploadProgress === 100 && (
                  <div className="flex items-center gap-2 text-sm text-green-500">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Upload complete! Processing schema...</span>
                  </div>
                )}
              </div>
            )}

            {error && (
              <div className="mt-4 text-sm text-red-600">
                {error}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Schema summary - rendered after successful upload */}
      {schemaProfile && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Dataset Summary</CardTitle>
                <CardDescription>Overview extracted from the uploaded CSV</CardDescription>
              </div>
              <div className="text-right text-sm text-muted-foreground">
                {fileId && <div>File ID: <code className="bg-muted px-2 py-0.5 rounded text-xs">{fileId}</code></div>}
                <div className="mt-1">{schemaProfile.stored_file_name ?? schemaProfile.file_name}</div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-4 gap-4 mb-4">
              <div className="p-3 rounded-lg border border-border bg-muted/20">
                <div className="text-xs text-muted-foreground">File name</div>
                <div className="text-sm text-foreground">{schemaProfile.file_name || "—"}</div>
              </div>
              <div className="p-3 rounded-lg border border-border bg-muted/20">
                <div className="text-xs text-muted-foreground">File size</div>
                <div className="text-sm text-foreground">{formatBytes(schemaProfile.file_size_bytes)}</div>
              </div>
              <div className="p-3 rounded-lg border border-border bg-muted/20">
                <div className="text-xs text-muted-foreground">Rows sampled</div>
                <div className="text-sm text-foreground">{schemaProfile.rows_sampled ?? "—"}</div>
              </div>
              <div className="p-3 rounded-lg border border-border bg-muted/20">
                <div className="text-xs text-muted-foreground">Total columns</div>
                <div className="text-sm text-foreground">{schemaProfile.total_columns ?? (schemaProfile.columns ? schemaProfile.columns.length : "—")}</div>
              </div>
            </div>

            {/* Columns table */}
            <div className="mb-4">
              <div className="text-sm font-medium mb-2">Column Summary</div>
              {schemaProfile.columns && schemaProfile.columns.length > 0 ? (
                <div className="overflow-auto border border-border rounded">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="px-3 py-2 text-left">Name</th>
                        <th className="px-3 py-2 text-left">Inferred Type</th>
                        <th className="px-3 py-2 text-left">Null Count</th>
                        <th className="px-3 py-2 text-left">Unique Count</th>
                        <th className="px-3 py-2 text-left">Sample Values</th>
                      </tr>
                    </thead>
                    <tbody>
                      {schemaProfile.columns.map((col, idx) => (
                        <tr key={col.name + idx} className="odd:bg-muted/10">
                          <td className="px-3 py-2 align-top text-foreground">{col.name}</td>
                          <td className="px-3 py-2 align-top text-muted-foreground">{col.inferred_dtype}</td>
                          <td className="px-3 py-2 align-top text-muted-foreground">{col.null_count ?? "—"}</td>
                          <td className="px-3 py-2 align-top text-muted-foreground">{col.unique_count ?? "—"}</td>
                          <td className="px-3 py-2 align-top text-muted-foreground">
                            {(col.sample_values && col.sample_values.length > 0) ? (
                              <div className="flex flex-wrap gap-2">
                                {col.sample_values.slice(0, 6).map((v, i) => (
                                  <span key={i} className="text-xs bg-muted px-2 py-0.5 rounded">{String(v)}</span>
                                ))}
                                {col.sample_values.length > 6 && <span className="text-xs text-muted-foreground">…</span>}
                              </div>
                            ) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">No column information available.</div>
              )}
            </div>

            {/* Preview rows */}
            <div className="mb-4">
              <div className="text-sm font-medium mb-2">Preview Rows</div>
              {renderPreviewRows(schemaProfile.preview_rows)}
            </div>

            {/* Notes */}
            {schemaProfile.notes && schemaProfile.notes.length > 0 && (
              <div>
                <div className="text-sm font-medium mb-2">Notes</div>
                <ul className="list-disc list-inside text-sm text-muted-foreground">
                  {schemaProfile.notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Uploads */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent Uploads</CardTitle>
            <CardDescription>Your recently uploaded datasets</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recentUploads.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center gap-4 p-4 rounded-lg border border-border hover:bg-accent/50 transition-colors"
                >
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <FileSpreadsheet className="w-5 h-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-foreground truncate">{file.name}</h4>
                      {file.status === "success" && (
                        <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {file.size} • {file.uploadedAt}
                      {file.rows && ` • ${file.rows.toLocaleString()} rows, ${file.columns} columns`}
                    </p>
                  </div>
                  <Button variant="outline" size="sm">
                    View
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        {/* Guidance Card */}
        <Card>
          <CardHeader>
            <CardTitle>What Happens Next?</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="space-y-2">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs text-primary">1</span>
                </div>
                <div>
                  <p className="text-foreground mb-1">Schema Extraction</p>
                  <p className="text-muted-foreground text-xs">
                    We analyze your CSV structure, data types, and quality
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs text-primary">2</span>
                </div>
                <div>
                  <p className="text-foreground mb-1">Validation</p>
                  <p className="text-muted-foreground text-xs">
                    Check for missing values, inconsistencies, and format issues
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs text-primary">3</span>
                </div>
                <div>
                  <p className="text-foreground mb-1">Profile Ready</p>
                  <p className="text-muted-foreground text-xs">
                    View your schema profile and data quality insights
                  </p>
                </div>
              </div>
            </div>
            <div className="pt-4 border-t border-border">
              <div className="flex items-start gap-2 text-xs text-muted-foreground">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <p>
                  Your data is processed securely and never shared. We use enterprise-grade
                  encryption and validation.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}