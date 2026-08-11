"use client";

import { colorFor } from "@/lib/eventStyle";

export interface FeedEvent {
  trace_id: string;
  agent_id: string;
  event_type: string;
  timestamp: string;
}

export function LiveFeed({ events }: { events: FeedEvent[] }) {
  if (!events.length) {
    return <div className="text-sm text-gray-500">Waiting for events…</div>;
  }
  return (
    <div className="max-h-[280px] space-y-1 overflow-auto font-mono text-xs">
      {events.map((e, i) => (
        <div key={i} className="flex gap-2">
          <span style={{ color: colorFor(e.event_type) }}>●</span>
          <span className="text-gray-500">
            {new Date(e.timestamp).toLocaleTimeString()}
          </span>
          <span className="text-gray-200">{e.event_type}</span>
          <span className="truncate text-gray-500">{e.agent_id}</span>
        </div>
      ))}
    </div>
  );
}
