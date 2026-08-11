export const EVENT_COLORS: Record<string, string> = {
  command_received: "#3b82f6",
  plan_created: "#8b5cf6",
  task_assigned: "#8b5cf6",
  task_started: "#0ea5e9",
  tool_called: "#f59e0b",
  tool_returned: "#f59e0b",
  approval_requested: "#eab308",
  approval_granted: "#22c55e",
  approval_denied: "#ef4444",
  output_produced: "#14b8a6",
  task_completed: "#22c55e",
  task_failed: "#ef4444",
  budget_exceeded: "#ef4444",
};

export const colorFor = (t: string): string => EVENT_COLORS[t] ?? "#6b7280";
