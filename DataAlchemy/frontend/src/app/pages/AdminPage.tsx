import { useState } from "react";
import {
  Users,
  Upload,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  Filter,
  Download,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Input } from "../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";

interface UserAnalytics {
  id: string;
  name: string;
  email: string;
  datasets: number;
  lastActivity: string;
  status: "active" | "inactive";
  taskCount: number;
}

interface TaskLog {
  taskId: string;
  user: string;
  taskType: string;
  fileName: string;
  status: "completed" | "processing" | "failed";
  startedAt: string;
  duration: string;
  result?: string;
}

interface SystemEvent {
  id: string;
  timestamp: string;
  type: string;
  message: string;
  level: "info" | "warning" | "error";
}

const users: UserAnalytics[] = [
  {
    id: "usr_001",
    name: "John Doe",
    email: "john.doe@company.com",
    datasets: 12,
    lastActivity: "2 minutes ago",
    status: "active",
    taskCount: 24,
  },
  {
    id: "usr_002",
    name: "Sarah Chen",
    email: "sarah.chen@company.com",
    datasets: 8,
    lastActivity: "15 minutes ago",
    status: "active",
    taskCount: 16,
  },
  {
    id: "usr_003",
    name: "Michael Smith",
    email: "michael.smith@company.com",
    datasets: 5,
    lastActivity: "2 hours ago",
    status: "inactive",
    taskCount: 10,
  },
  {
    id: "usr_004",
    name: "Emily Rodriguez",
    email: "emily.r@company.com",
    datasets: 15,
    lastActivity: "5 minutes ago",
    status: "active",
    taskCount: 32,
  },
];

const tasks: TaskLog[] = [
  {
    taskId: "task_1042",
    user: "John Doe",
    taskType: "schema_profile_extraction",
    fileName: "customer_churn.csv",
    status: "completed",
    startedAt: "Apr 5, 2026 10:32:15",
    duration: "3.2s",
    result: "24 columns profiled",
  },
  {
    taskId: "task_1041",
    user: "Sarah Chen",
    taskType: "csv_upload",
    fileName: "sales_data_q1.csv",
    status: "completed",
    startedAt: "Apr 5, 2026 10:28:42",
    duration: "1.8s",
    result: "8.7 MB uploaded",
  },
  {
    taskId: "task_1040",
    user: "Emily Rodriguez",
    taskType: "schema_validation",
    fileName: "inventory_report.csv",
    status: "processing",
    startedAt: "Apr 5, 2026 10:31:05",
    duration: "—",
  },
  {
    taskId: "task_1039",
    user: "Michael Smith",
    taskType: "csv_upload",
    fileName: "large_dataset.csv",
    status: "failed",
    startedAt: "Apr 5, 2026 09:45:22",
    duration: "0.5s",
    result: "File size exceeds limit",
  },
  {
    taskId: "task_1038",
    user: "John Doe",
    taskType: "schema_profile_extraction",
    fileName: "product_catalog.csv",
    status: "completed",
    startedAt: "Apr 5, 2026 09:12:33",
    duration: "2.1s",
    result: "18 columns profiled",
  },
];

const events: SystemEvent[] = [
  {
    id: "evt_501",
    timestamp: "10:32:18",
    type: "schema_extraction",
    message: "Schema extraction completed for customer_churn.csv",
    level: "info",
  },
  {
    id: "evt_502",
    timestamp: "10:32:15",
    type: "schema_extraction",
    message: "Schema extraction started for customer_churn.csv",
    level: "info",
  },
  {
    id: "evt_503",
    timestamp: "10:31:42",
    type: "file_upload",
    message: "File uploaded: customer_churn.csv (12.4 MB)",
    level: "info",
  },
  {
    id: "evt_504",
    timestamp: "10:28:45",
    type: "validation",
    message: "CSV validation passed for sales_data_q1.csv",
    level: "info",
  },
  {
    id: "evt_505",
    timestamp: "10:15:22",
    type: "api_request",
    message: "API request received: POST /api/upload",
    level: "info",
  },
  {
    id: "evt_506",
    timestamp: "09:45:23",
    type: "error",
    message: "Upload failed: File size exceeds 500 MB limit",
    level: "error",
  },
  {
    id: "evt_507",
    timestamp: "09:30:15",
    type: "validation",
    message: "Schema validation warning: Missing values detected in column 'total_charges'",
    level: "warning",
  },
];

export function AdminPage() {
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const filteredTasks =
    filterStatus === "all" ? tasks : tasks.filter((task) => task.status === filterStatus);

  return (
    <div className="p-8 max-w-[1600px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-foreground mb-2">Admin Dashboard</h1>
          <p className="text-muted-foreground">
            System analytics, user activity, and operational logs
          </p>
        </div>
        <Button variant="outline" className="gap-2">
          <Download className="w-4 h-4" />
          Export Report
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total Users</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-blue-500" />
              <div className="text-3xl text-foreground">127</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Total Uploads</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Upload className="w-5 h-5 text-purple-500" />
              <div className="text-3xl text-foreground">1,042</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Successful</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-500" />
              <div className="text-3xl text-foreground">987</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Failed</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <XCircle className="w-5 h-5 text-red-500" />
              <div className="text-3xl text-foreground">55</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Active Tasks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-orange-500" />
              <div className="text-3xl text-foreground">12</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Avg Duration</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-cyan-500" />
              <div className="text-3xl text-foreground">2.8s</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="users" className="space-y-6">
        <TabsList>
          <TabsTrigger value="users">User Analytics</TabsTrigger>
          <TabsTrigger value="tasks">Task History</TabsTrigger>
          <TabsTrigger value="events">System Events</TabsTrigger>
        </TabsList>

        {/* User Analytics */}
        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>User Activity</CardTitle>
              <CardDescription>Active users and their dataset upload statistics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User ID</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Datasets</TableHead>
                      <TableHead>Last Activity</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Tasks</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell>
                          <code className="text-xs bg-muted px-2 py-0.5 rounded">
                            {user.id}
                          </code>
                        </TableCell>
                        <TableCell className="text-foreground">{user.name}</TableCell>
                        <TableCell className="text-muted-foreground">{user.email}</TableCell>
                        <TableCell className="text-foreground">{user.datasets}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {user.lastActivity}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={user.status === "active" ? "default" : "secondary"}
                            className="gap-1"
                          >
                            {user.status === "active" ? (
                              <CheckCircle2 className="w-3 h-3" />
                            ) : (
                              <XCircle className="w-3 h-3" />
                            )}
                            {user.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{user.taskCount}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Task History */}
        <TabsContent value="tasks" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Task & Job Log</CardTitle>
                  <CardDescription>Recent task execution history and status</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Select value={filterStatus} onValueChange={setFilterStatus}>
                    <SelectTrigger className="w-[180px]">
                      <Filter className="w-4 h-4 mr-2" />
                      <SelectValue placeholder="Filter by status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                      <SelectItem value="processing">Processing</SelectItem>
                      <SelectItem value="failed">Failed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Task ID</TableHead>
                      <TableHead>User</TableHead>
                      <TableHead>Task Type</TableHead>
                      <TableHead>File Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Started At</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Result</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredTasks.map((task) => (
                      <TableRow key={task.taskId}>
                        <TableCell>
                          <code className="text-xs bg-muted px-2 py-0.5 rounded">
                            {task.taskId}
                          </code>
                        </TableCell>
                        <TableCell className="text-foreground">{task.user}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-xs">
                            {task.taskType}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{task.fileName}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              task.status === "completed"
                                ? "default"
                                : task.status === "processing"
                                ? "secondary"
                                : "destructive"
                            }
                            className="gap-1"
                          >
                            {task.status === "completed" && (
                              <CheckCircle2 className="w-3 h-3" />
                            )}
                            {task.status === "processing" && <Clock className="w-3 h-3" />}
                            {task.status === "failed" && <XCircle className="w-3 h-3" />}
                            {task.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{task.startedAt}</TableCell>
                        <TableCell className="text-muted-foreground">{task.duration}</TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {task.result || "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* System Events */}
        <TabsContent value="events" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Event Log</CardTitle>
              <CardDescription>Real-time system events and operational logs</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {events.map((event) => (
                  <div
                    key={event.id}
                    className={`
                      flex items-start gap-3 p-3 rounded-lg border
                      ${
                        event.level === "error"
                          ? "bg-red-500/10 border-red-500/20"
                          : event.level === "warning"
                          ? "bg-orange-500/10 border-orange-500/20"
                          : "bg-card border-border"
                      }
                    `}
                  >
                    <div
                      className={`
                      w-1.5 h-1.5 rounded-full mt-2 flex-shrink-0
                      ${
                        event.level === "error"
                          ? "bg-red-500"
                          : event.level === "warning"
                          ? "bg-orange-500"
                          : "bg-green-500"
                      }
                    `}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs text-muted-foreground font-mono">
                          {event.timestamp}
                        </span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                          {event.type}
                        </Badge>
                      </div>
                      <p className="text-sm text-foreground">{event.message}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
