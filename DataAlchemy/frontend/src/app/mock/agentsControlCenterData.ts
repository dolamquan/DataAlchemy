export type AgentStatus = "active" | "idle" | "degraded" | "offline";
export type StepStatus = "completed" | "in_progress" | "pending" | "failed";

export interface AgentRecord {
  id: string;
  name: string;
  role: "supervisor" | "coordinator" | "worker";
  status: AgentStatus;
  lastTask: string;
  lastUpdated: string;
  outputs: string[];
  artifacts: string[];
  logs: Array<{ timestamp: string; message: string }>;
}

export interface WorkflowStep {
  step: string;
  assignedAgent: string;
  status: StepStatus;
  output: string;
}

export const metrics = {
  totalAgents: 9,
  activeAgents: 5,
  completedTasks: 42,
  failedTasks: 3,
  artifactsGenerated: 27,
};

export const agents: AgentRecord[] = [
  {
    id: "supervisor",
    name: "Supervisor",
    role: "supervisor",
    status: "active",
    lastTask: "Finalize plan for churn modeling",
    lastUpdated: "2026-04-06T19:10:00Z",
    outputs: ["Plan finalized", "Clarification delivered"],
    artifacts: ["plan_v12.json"],
    logs: [
      { timestamp: "2026-04-06T19:08:22Z", message: "Drafted initial plan with 5 steps" },
      { timestamp: "2026-04-06T19:09:01Z", message: "Applied user revision to training stage" },
      { timestamp: "2026-04-06T19:10:00Z", message: "Finalized plan and delegated to coordinator" },
    ],
  },
  {
    id: "coordinator",
    name: "Coordinator",
    role: "coordinator",
    status: "active",
    lastTask: "Execute finalized pipeline",
    lastUpdated: "2026-04-06T19:10:02Z",
    outputs: ["Execution started", "Step status updates emitted"],
    artifacts: ["execution_trace_9012.json"],
    logs: [
      { timestamp: "2026-04-06T19:10:02Z", message: "Received finalized plan from supervisor" },
      { timestamp: "2026-04-06T19:10:05Z", message: "Delegated inspect_schema to supervisor" },
      { timestamp: "2026-04-06T19:10:09Z", message: "Delegated clean_missing_values to data_preprocessing_agent" },
    ],
  },
  {
    id: "data-preprocessing",
    name: "Data Preprocessing Agent",
    role: "worker",
    status: "idle",
    lastTask: "Clean missing values",
    lastUpdated: "2026-04-06T19:10:09Z",
    outputs: ["Placeholder worker output"],
    artifacts: ["cleaning_plan.txt"],
    logs: [{ timestamp: "2026-04-06T19:10:09Z", message: "Placeholder handler executed clean_missing_values" }],
  },
  {
    id: "data-quality",
    name: "Data Quality Agent",
    role: "worker",
    status: "idle",
    lastTask: "Validate null ratio thresholds",
    lastUpdated: "2026-04-06T18:55:12Z",
    outputs: ["No active run"],
    artifacts: [],
    logs: [{ timestamp: "2026-04-06T18:55:12Z", message: "Awaiting assignment" }],
  },
  {
    id: "visualization",
    name: "Visualization Agent",
    role: "worker",
    status: "active",
    lastTask: "Generate charts",
    lastUpdated: "2026-04-06T19:10:15Z",
    outputs: ["3 chart specs generated"],
    artifacts: ["dist_histogram.json", "corr_heatmap.json", "target_balance.json"],
    logs: [{ timestamp: "2026-04-06T19:10:15Z", message: "Generated placeholder chart specs" }],
  },
  {
    id: "schema",
    name: "Schema Agent",
    role: "worker",
    status: "active",
    lastTask: "Inspect schema",
    lastUpdated: "2026-04-06T19:10:06Z",
    outputs: ["Column profile summary emitted"],
    artifacts: ["schema_summary.md"],
    logs: [{ timestamp: "2026-04-06T19:10:06Z", message: "Schema profile parsed for 23 columns" }],
  },
  {
    id: "model-training",
    name: "Model Training Agent",
    role: "worker",
    status: "degraded",
    lastTask: "Train model",
    lastUpdated: "2026-04-06T19:10:21Z",
    outputs: ["Missing handler fallback engaged"],
    artifacts: [],
    logs: [{ timestamp: "2026-04-06T19:10:21Z", message: "Execution blocked by missing runtime handler" }],
  },
  {
    id: "evaluation",
    name: "Evaluation Agent",
    role: "worker",
    status: "idle",
    lastTask: "Awaiting trained model",
    lastUpdated: "2026-04-06T19:02:48Z",
    outputs: ["No evaluation run yet"],
    artifacts: [],
    logs: [{ timestamp: "2026-04-06T19:02:48Z", message: "Waiting for model artifact" }],
  },
  {
    id: "report",
    name: "Report Agent",
    role: "worker",
    status: "offline",
    lastTask: "Build report",
    lastUpdated: "2026-04-06T18:40:10Z",
    outputs: ["Agent paused"],
    artifacts: [],
    logs: [{ timestamp: "2026-04-06T18:40:10Z", message: "Report generation disabled in current stage" }],
  },
];

export const workflowSteps: WorkflowStep[] = [
  {
    step: "Inspect schema",
    assignedAgent: "Schema Agent",
    status: "completed",
    output: "Schema profile parsed and summarized",
  },
  {
    step: "Clean missing values",
    assignedAgent: "Data Preprocessing Agent",
    status: "completed",
    output: "Placeholder cleaning strategy returned",
  },
  {
    step: "Generate charts",
    assignedAgent: "Visualization Agent",
    status: "in_progress",
    output: "Generating chart configs",
  },
  {
    step: "Train model",
    assignedAgent: "Model Training Agent",
    status: "failed",
    output: "Missing runtime handler",
  },
  {
    step: "Build report",
    assignedAgent: "Report Agent",
    status: "pending",
    output: "Blocked until training succeeds",
  },
];

export const activityFeed = [
  { timestamp: "2026-04-06T19:10:24Z", event: "Coordinator halted run after train_model failure" },
  { timestamp: "2026-04-06T19:10:21Z", event: "Model Training Agent reported missing handler" },
  { timestamp: "2026-04-06T19:10:15Z", event: "Visualization Agent started chart generation" },
  { timestamp: "2026-04-06T19:10:09Z", event: "Data Preprocessing Agent completed clean_missing_values" },
  { timestamp: "2026-04-06T19:10:06Z", event: "Schema Agent completed inspect_schema" },
  { timestamp: "2026-04-06T19:10:02Z", event: "Coordinator accepted finalized plan" },
];
