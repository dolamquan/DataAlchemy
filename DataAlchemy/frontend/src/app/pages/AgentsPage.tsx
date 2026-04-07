import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Brain,
  CheckCircle2,
  Clock3,
  Database,
  FileBarChart,
  Filter,
  FlaskConical,
  GitBranch,
  Orbit,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Wrench,
} from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { agents, activityFeed, metrics, type AgentRecord, type AgentStatus, workflowSteps } from "../mock/agentsControlCenterData";

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString();
}

function statusBadgeClass(status: AgentStatus | "completed" | "in_progress" | "pending" | "failed") {
  if (status === "active" || status === "completed") return "border-green-500/40 text-green-400";
  if (status === "idle" || status === "pending") return "border-slate-500/40 text-slate-300";
  if (status === "in_progress") return "border-blue-500/40 text-blue-400";
  if (status === "degraded") return "border-amber-500/40 text-amber-400";
  return "border-red-500/40 text-red-400";
}

function roleIcon(role: AgentRecord["role"]) {
  if (role === "supervisor") return <Brain className="w-4 h-4 text-blue-400" />;
  if (role === "coordinator") return <Orbit className="w-4 h-4 text-violet-400" />;
  return <Wrench className="w-4 h-4 text-cyan-400" />;
}

export function AgentsPage() {
  const [statusFilter, setStatusFilter] = useState<"all" | AgentStatus>("all");
  const [selectedAgent, setSelectedAgent] = useState<AgentRecord | null>(null);

  const filteredAgents = useMemo(() => {
    if (statusFilter === "all") return agents;
    return agents.filter((agent) => agent.status === statusFilter);
  }, [statusFilter]);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-foreground">Agent Control Center</h1>
            <Badge variant="outline" className="gap-1.5">
              <Sparkles className="w-3 h-3 text-cyan-400" />
              Mocked Runtime View
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Monitor agent orchestration, delegation, and execution health across Supervisor, Coordinator, and worker agents.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="gap-1.5 bg-emerald-500/10 text-emerald-300 border-emerald-500/30">
            <ShieldCheck className="w-3 h-3" />
            Placeholder worker mode
          </Badge>
          <Button variant="outline" className="gap-2">
            <RefreshCw className="w-4 h-4" />
            Refresh Mock State
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Agents</CardDescription>
            <CardTitle className="text-2xl">{metrics.totalAgents}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <Bot className="w-3.5 h-3.5" /> Registry size
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active Agents</CardDescription>
            <CardTitle className="text-2xl">{metrics.activeAgents}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <Activity className="w-3.5 h-3.5" /> Currently processing
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completed Tasks</CardDescription>
            <CardTitle className="text-2xl">{metrics.completedTasks}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5" /> Successful execution
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Failed Tasks</CardDescription>
            <CardTitle className="text-2xl">{metrics.failedTasks}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5" /> Needs handler/retry
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Artifacts Generated</CardDescription>
            <CardTitle className="text-2xl">{metrics.artifactsGenerated}</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground flex items-center gap-2">
            <FileBarChart className="w-3.5 h-3.5" /> Produced outputs
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="w-4 h-4" /> Filter Agents
          </CardTitle>
          <CardDescription>Filter cards by current runtime status.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {(["all", "active", "idle", "degraded", "offline"] as const).map((status) => (
              <Button
                key={status}
                size="sm"
                variant={statusFilter === status ? "default" : "outline"}
                onClick={() => setStatusFilter(status)}
                className="capitalize"
              >
                {status}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Agents Grid</CardTitle>
          <CardDescription>Click any card to inspect outputs, artifacts, and logs.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredAgents.map((agent) => (
              <button
                key={agent.id}
                type="button"
                onClick={() => setSelectedAgent(agent)}
                className="text-left rounded-xl border border-border bg-card p-4 hover:border-blue-500/40 hover:bg-muted/20 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-foreground">{agent.name}</p>
                    <p className="text-xs text-muted-foreground capitalize">Role: {agent.role}</p>
                  </div>
                  {roleIcon(agent.role)}
                </div>

                <div className="mt-3 flex items-center gap-2 flex-wrap">
                  <Badge variant="outline" className={`capitalize ${statusBadgeClass(agent.status)}`}>
                    {agent.status}
                  </Badge>
                </div>

                <div className="mt-3 space-y-1.5 text-xs text-muted-foreground">
                  <p>Last task: {agent.lastTask}</p>
                  <p>Last updated: {formatDate(agent.lastUpdated)}</p>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="w-4 h-4" /> Workflow Tracker
            </CardTitle>
            <CardDescription>
              Supervisor {"->"} Coordinator {"->"} Worker Agents
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="outline" className="border-blue-500/40 text-blue-300">Supervisor</Badge>
              <span className="text-muted-foreground">{"->"}</span>
              <Badge variant="outline" className="border-violet-500/40 text-violet-300">Coordinator</Badge>
              <span className="text-muted-foreground">{"->"}</span>
              <Badge variant="outline" className="border-cyan-500/40 text-cyan-300">Worker Agents</Badge>
            </div>

            <div className="space-y-2">
              {workflowSteps.map((item, index) => (
                <div key={`${item.step}-${index}`} className="rounded-lg border border-border bg-background p-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <p className="text-sm text-foreground">{index + 1}. {item.step}</p>
                    <Badge variant="outline" className={`capitalize ${statusBadgeClass(item.status)}`}>
                      {item.status.replaceAll("_", " ")}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">Assigned: {item.assignedAgent}</p>
                  <p className="text-xs text-muted-foreground">Output: {item.output}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock3 className="w-4 h-4" /> Live Activity Feed
            </CardTitle>
            <CardDescription>Recent orchestration events with timestamps.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[420px] overflow-auto pr-1">
              {activityFeed.map((item, idx) => (
                <div key={idx} className="rounded-md border border-border bg-background p-2.5">
                  <p className="text-xs text-muted-foreground">{formatDate(item.timestamp)}</p>
                  <p className="text-sm text-foreground mt-1">{item.event}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Delegation Table</CardTitle>
          <CardDescription>Coordinator step assignments and outputs.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Step</TableHead>
                <TableHead>Assigned Agent</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Output</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {workflowSteps.map((row) => (
                <TableRow key={row.step}>
                  <TableCell className="font-medium">{row.step}</TableCell>
                  <TableCell>{row.assignedAgent}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`capitalize ${statusBadgeClass(row.status)}`}>
                      {row.status.replaceAll("_", " ")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{row.output}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={!!selectedAgent} onOpenChange={(open) => !open && setSelectedAgent(null)}>
        <DialogContent className="max-w-3xl">
          {selectedAgent && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {roleIcon(selectedAgent.role)}
                  {selectedAgent.name}
                </DialogTitle>
                <DialogDescription>
                  Detailed runtime snapshot including outputs, artifacts, and logs.
                </DialogDescription>
              </DialogHeader>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Card className="md:col-span-1">
                  <CardHeader className="pb-2">
                    <CardDescription>Status</CardDescription>
                    <CardTitle className="text-base capitalize">{selectedAgent.status}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-xs text-muted-foreground">Role: {selectedAgent.role}</CardContent>
                </Card>

                <Card className="md:col-span-2">
                  <CardHeader className="pb-2">
                    <CardDescription>Last Task</CardDescription>
                    <CardTitle className="text-base">{selectedAgent.lastTask}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-xs text-muted-foreground">
                    Last updated: {formatDate(selectedAgent.lastUpdated)}
                  </CardContent>
                </Card>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2"><Database className="w-4 h-4" /> Outputs</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {selectedAgent.outputs.map((out, idx) => (
                      <p key={idx} className="text-sm text-muted-foreground rounded border border-border p-2">{out}</p>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2"><FlaskConical className="w-4 h-4" /> Artifacts</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {selectedAgent.artifacts.length === 0 && <p className="text-sm text-muted-foreground">No artifacts generated.</p>}
                    {selectedAgent.artifacts.map((artifact, idx) => (
                      <p key={idx} className="text-sm text-muted-foreground rounded border border-border p-2">{artifact}</p>
                    ))}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Recent Logs</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 max-h-44 overflow-auto pr-1">
                  {selectedAgent.logs.map((log, idx) => (
                    <div key={idx} className="rounded border border-border p-2">
                      <p className="text-xs text-muted-foreground">{formatDate(log.timestamp)}</p>
                      <p className="text-sm text-foreground mt-1">{log.message}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
