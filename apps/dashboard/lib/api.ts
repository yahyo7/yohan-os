export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface TraceSummary {
  trace_id: string;
  started_at: string;
  last_at: string;
  events: number;
  command: string | null;
  reply: string | null;
  completed: boolean;
  errored: boolean;
}

export interface TraceEvent {
  id: number;
  event_ts: string;
  event_type: string;
  agent_id: string;
  payload: Record<string, unknown>;
}

export interface Approval {
  trace_id: string;
  request_id: string;
  action: string;
  arguments: Record<string, unknown> | null;
  event_ts: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

export const fetchTraces = () => getJSON<TraceSummary[]>("/api/traces?limit=50");
export const fetchTraceEvents = (id: string) =>
  getJSON<TraceEvent[]>(`/api/traces/${id}`);
export const fetchApprovals = () => getJSON<Approval[]>("/api/approvals");

export async function decideApproval(requestId: string, granted: boolean) {
  await fetch(`${API_BASE}/api/approvals/${requestId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ granted }),
  });
}
