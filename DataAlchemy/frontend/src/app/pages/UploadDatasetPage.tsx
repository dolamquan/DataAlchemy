import { useState } from "react";
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
    handleFileUpload();
  };

  const handleFileUpload = () => {
    setUploadProgress(0);
    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev === null) return 0;
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(() => setUploadProgress(null), 1000);
          return 100;
        }
        return prev + 10;
      });
    }, 200);
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
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
              <Button onClick={handleFileUpload}>Browse Files</Button>
              <p className="text-xs text-muted-foreground">
                CSV files only • Maximum 500 MB • Secure encrypted upload
              </p>
            </div>
          </div>

          {uploadProgress !== null && (
            <div className="mt-6 space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Uploading...</span>
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
        </CardContent>
      </Card>

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
