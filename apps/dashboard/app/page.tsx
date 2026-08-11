"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Approvals } from "@/components/Approvals";
import { History } from "@/components/History";
import { LiveFeed, type FeedEvent } from "@/components/LiveFeed";
import { TraceDag } from "@/components/TraceDag";
import {
  API_BASE,
  Approval,
  TraceEvent,
  TraceSummary,
  fetchApprovals,
  fetchTraceEvents,
  fetchTraces,
} from "@/lib/api";

export default function Page() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const selectedRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([fetchTraces(), fetchApprovals()]);
      setTraces(t);
      setApprovals(a);
    } catch {
      /* gateway not up yet */
    }
  }, []);

  const select = useCallback((id: string) => {
    setSelected(id);
    selectedRef.current = id;
    fetchTraceEvents(id).then(setEvents).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Live event stream (SSE). Independent of selection (uses a ref) so it doesn't
  // reconnect when you click a different trace.
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/events`);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (m) => {
      try {
        const ev = JSON.parse(m.data) as FeedEvent;
        setFeed((f) => [ev, ...f].slice(0, 50));
        refresh();
        if (selectedRef.current && ev.trace_id === selectedRef.current) {
          fetchTraceEvents(selectedRef.current).then(setEvents).catch(() => {});
        }
      } catch {
        /* ignore keepalive comments */
      }
    };
    return () => es.close();
  }, [refresh]);

  return (
    <main className="mx-auto max-w-7xl p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">🛰️ Yohan — live traces</h1>
        <span
          className={`text-xs ${connected ? "text-green-400" : "text-gray-500"}`}
        >
          {connected ? "● live" : "○ offline"}
        </span>
      </header>

      <Approvals items={approvals} onDecide={refresh} />

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-3">
          <h2 className="mb-2 text-xs uppercase tracking-wide text-gray-500">
            History
          </h2>
          <History traces={traces} selected={selected} onSelect={select} />
        </div>
        <div className="col-span-9 space-y-4">
          <TraceDag events={events} />
          <div>
            <h2 className="mb-2 text-xs uppercase tracking-wide text-gray-500">
              Live events
            </h2>
            <LiveFeed events={feed} />
          </div>
        </div>
      </div>
    </main>
  );
}
