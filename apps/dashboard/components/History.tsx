"use client";

import { TraceSummary } from "@/lib/api";

export function History({
  traces,
  selected,
  onSelect,
}: {
  traces: TraceSummary[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="space-y-1">
      {traces.map((t) => {
        const status = t.errored ? "❌" : t.completed ? "✅" : "…";
        const label = t.command ?? t.reply ?? t.trace_id.slice(0, 16);
        return (
          <button
            key={t.trace_id}
            onClick={() => onSelect(t.trace_id)}
            className={`w-full rounded border px-3 py-2 text-left text-sm ${
              selected === t.trace_id
                ? "border-blue-500 bg-panel"
                : "border-edge hover:bg-panel"
            }`}
          >
            <div className="flex justify-between gap-2">
              <span className="truncate">{label}</span>
              <span>{status}</span>
            </div>
            <div className="text-xs text-gray-500">
              {new Date(t.started_at).toLocaleTimeString()} · {t.events} events
            </div>
          </button>
        );
      })}
      {!traces.length && (
        <div className="text-sm text-gray-500">No commands yet.</div>
      )}
    </div>
  );
}
