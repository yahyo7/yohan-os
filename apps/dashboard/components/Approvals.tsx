"use client";

import { Approval, decideApproval } from "@/lib/api";

export function Approvals({
  items,
  onDecide,
}: {
  items: Approval[];
  onDecide: () => void;
}) {
  if (!items.length) return null;
  return (
    <section className="mb-6">
      <h2 className="mb-3 text-lg font-semibold">
        ⏳ Pending approvals ({items.length})
      </h2>
      <div className="space-y-3">
        {items.map((a) => {
          const args = (a.arguments ?? {}) as Record<string, unknown>;
          return (
            <div
              key={a.request_id}
              className="rounded-lg border border-edge bg-panel p-4"
            >
              <div className="font-mono text-sm text-amber-400">{a.action}</div>
              {a.action === "gmail.send_email" ? (
                <div className="mt-1 text-sm">
                  <div className="text-gray-400">
                    To: {String(args.to ?? "")} · Subject:{" "}
                    {String(args.subject ?? "")}
                  </div>
                  <div className="mt-2 whitespace-pre-wrap text-gray-200">
                    {String(args.body ?? "").slice(0, 400)}
                  </div>
                </div>
              ) : (
                <pre className="mt-1 text-xs text-gray-400">
                  {JSON.stringify(args, null, 2)}
                </pre>
              )}
              <div className="mt-3 flex gap-2">
                <button
                  onClick={async () => {
                    await decideApproval(a.request_id, true);
                    onDecide();
                  }}
                  className="rounded bg-green-600 px-3 py-1 text-sm hover:bg-green-500"
                >
                  ✅ Approve
                </button>
                <button
                  onClick={async () => {
                    await decideApproval(a.request_id, false);
                    onDecide();
                  }}
                  className="rounded bg-red-600 px-3 py-1 text-sm hover:bg-red-500"
                >
                  ❌ Reject
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
