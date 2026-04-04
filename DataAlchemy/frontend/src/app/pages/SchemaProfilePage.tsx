import { CheckCircle2, AlertTriangle, Database, Columns3, Hash, Type, Calendar, AlertCircle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Button } from "../components/ui/button";

interface SchemaColumn {
  name: string;
  type: string;
  nullPercent: number;
  example: string;
  notes?: string;
}

const schemaData: SchemaColumn[] = [
  { name: "customer_id", type: "Integer", nullPercent: 0, example: "12345", notes: "Primary key" },
  { name: "age", type: "Integer", nullPercent: 2.3, example: "34" },
  { name: "gender", type: "String", nullPercent: 0.8, example: "Male" },
  { name: "subscription_type", type: "String", nullPercent: 0, example: "Premium" },
  { name: "monthly_charges", type: "Float", nullPercent: 1.2, example: "79.99" },
  { name: "tenure_months", type: "Integer", nullPercent: 0, example: "24" },
  { name: "total_charges", type: "Float", nullPercent: 3.5, example: "1919.76" },
  { name: "churn", type: "Boolean", nullPercent: 0, example: "false", notes: "Target variable" },
  { name: "contract_type", type: "String", nullPercent: 0, example: "Two year" },
  { name: "payment_method", type: "String", nullPercent: 1.8, example: "Credit card" },
  { name: "internet_service", type: "String", nullPercent: 0, example: "Fiber optic" },
  { name: "phone_service", type: "Boolean", nullPercent: 0, example: "true" },
];

const sampleRows = [
  {
    customer_id: "12345",
    age: "34",
    gender: "Male",
    subscription_type: "Premium",
    monthly_charges: "79.99",
    churn: "false",
  },
  {
    customer_id: "12346",
    age: "45",
    gender: "Female",
    subscription_type: "Basic",
    monthly_charges: "45.50",
    churn: "true",
  },
  {
    customer_id: "12347",
    age: "28",
    gender: "Male",
    subscription_type: "Premium",
    monthly_charges: "85.00",
    churn: "false",
  },
];

export function SchemaProfilePage() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-foreground">Schema Profile</h1>
            <Badge variant="outline" className="gap-1.5">
              <CheckCircle2 className="w-3 h-3 text-green-500" />
              Ready
            </Badge>
          </div>
          <p className="text-muted-foreground">customer_churn.csv</p>
          <p className="text-sm text-muted-foreground">
            Uploaded Apr 5, 2026 at 10:32 AM • 12.4 MB • ~50,000 rows
          </p>
        </div>
        <Button>Export Schema</Button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total Columns</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
                <Columns3 className="w-5 h-5 text-blue-500" />
              </div>
              <div>
                <div className="text-3xl text-foreground">24</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Numeric Columns</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
                <Hash className="w-5 h-5 text-green-500" />
              </div>
              <div>
                <div className="text-3xl text-foreground">11</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Categorical Columns</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center">
                <Type className="w-5 h-5 text-purple-500" />
              </div>
              <div>
                <div className="text-3xl text-foreground">9</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Missing Values</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-orange-500" />
              </div>
              <div>
                <div className="text-3xl text-foreground">4</div>
                <p className="text-xs text-muted-foreground">columns affected</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Schema Detail Table */}
      <Card>
        <CardHeader>
          <CardTitle>Schema Details</CardTitle>
          <CardDescription>Column definitions, types, and quality indicators</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Column Name</TableHead>
                  <TableHead>Inferred Type</TableHead>
                  <TableHead>Null %</TableHead>
                  <TableHead>Example Value</TableHead>
                  <TableHead>Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {schemaData.map((column, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <code className="text-sm text-foreground bg-muted px-2 py-0.5 rounded">
                        {column.name}
                      </code>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="font-mono text-xs">
                        {column.type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className={column.nullPercent > 3 ? "text-orange-500" : "text-muted-foreground"}>
                          {column.nullPercent}%
                        </span>
                        {column.nullPercent > 3 && (
                          <AlertTriangle className="w-3 h-3 text-orange-500" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {column.example}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {column.notes || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Sample Rows */}
      <Card>
        <CardHeader>
          <CardTitle>Sample Rows</CardTitle>
          <CardDescription>Preview of your dataset (first 3 rows)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {Object.keys(sampleRows[0]).map((key) => (
                    <TableHead key={key}>
                      <code className="text-xs">{key}</code>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {sampleRows.map((row, index) => (
                  <TableRow key={index}>
                    {Object.values(row).map((value, i) => (
                      <TableCell key={i} className="text-sm text-muted-foreground">
                        {value}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Warnings & Notices */}
        <Card>
          <CardHeader>
            <CardTitle>Data Quality Notices</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <AlertTriangle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-foreground mb-1">High missing values detected</p>
                <p className="text-xs text-muted-foreground">
                  Column "total_charges" has 3.5% missing values. Consider imputation or filtering.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <AlertCircle className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-foreground mb-1">Categorical encoding recommended</p>
                <p className="text-xs text-muted-foreground">
                  9 string columns detected. AI workflows may benefit from label encoding.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
              <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-foreground mb-1">Schema validation passed</p>
                <p className="text-xs text-muted-foreground">
                  All columns have consistent data types across rows.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Next Steps */}
        <Card>
          <CardHeader>
            <CardTitle>Ready for Next Step</CardTitle>
            <CardDescription>Your dataset is profiled and validated</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Schema profiling is complete. Future milestones will unlock AI-powered transformation,
              multi-agent orchestration, and automated pipeline generation.
            </p>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground" />
                <span>AI data cleaning and transformation</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground" />
                <span>Automated feature engineering</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground" />
                <span>Multi-agent workflow orchestration</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground" />
                <span>Power BI export and visualization</span>
              </div>
            </div>

            <Button className="w-full" disabled>
              Launch AI Workflow
              <Badge variant="secondary" className="ml-2 text-[10px]">
                Coming Soon
              </Badge>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
