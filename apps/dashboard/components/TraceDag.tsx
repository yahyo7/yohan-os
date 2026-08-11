"use client";

import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { useMemo } from "react";

import { TraceEvent } from "@/lib/api";
import { colorFor } from "@/lib/eventStyle";

const mkEdge = (s: string, t: string): Edge => ({
  id: `${s}-${t}`,
  source: s,
  target: t,
  animated: true,
  style: { stroke: "#374151" },
});

/** Lay the trace's events out as a DAG: a root spine (events with no task_id)
 *  that fans out into one lane per task_id. */
function buildGraph(events: TraceEvent[]): { nodes: Node[]; edges: Edge[] } {
  const laneIndex = new Map<string, number>();
  const laneRow = new Map<string, number>();
  const laneHead = new Set<string>();
  const lanePrev = new Map<string, string>();
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  let rootPrev: string | null = null;

  for (const e of events) {
    const key = (e.payload?.task_id as string | undefined) ?? "root";
    if (!laneIndex.has(key)) {
      laneIndex.set(key, laneIndex.size);
      laneRow.set(key, 0);
    }
    const lane = laneIndex.get(key)!;
    const row = laneRow.get(key)!;
    laneRow.set(key, row + 1);
    const id = String(e.id);

    nodes.push({
      id,
      position: { x: lane * 240, y: row * 92 },
      data: { label: `${e.event_type}\n${e.agent_id}` },
      style: {
        background: "#0b0f19",
        color: "#e5e7eb",
        border: `1px solid ${colorFor(e.event_type)}`,
        borderLeft: `4px solid ${colorFor(e.event_type)}`,
        borderRadius: 8,
        fontSize: 11,
        width: 200,
        padding: 6,
        whiteSpace: "pre-line",
        textAlign: "left",
      },
    });

    if (key === "root") {
      if (rootPrev) edges.push(mkEdge(rootPrev, id));
      rootPrev = id;
    } else {
      if (!laneHead.has(key)) {
        laneHead.add(key);
        if (rootPrev) edges.push(mkEdge(rootPrev, id)); // fan out from the spine
      }
      const prev = lanePrev.get(key);
      if (prev) edges.push(mkEdge(prev, id));
      lanePrev.set(key, id);
    }
  }
  return { nodes, edges };
}

export function TraceDag({ events }: { events: TraceEvent[] }) {
  const { nodes, edges } = useMemo(() => buildGraph(events), [events]);

  if (!events.length) {
    return (
      <div className="flex h-[520px] items-center justify-center rounded-lg border border-edge bg-panel text-gray-500">
        Select a command to see its event graph.
      </div>
    );
  }
  return (
    <div className="h-[520px] rounded-lg border border-edge bg-panel">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background color="#1f2937" gap={16} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
