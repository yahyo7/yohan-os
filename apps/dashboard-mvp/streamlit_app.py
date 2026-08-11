"""Yohan MVP dashboard.

Run:  uv run streamlit run apps/dashboard-mvp/streamlit_app.py

A read-only window on the traces table: live totals, an event-type breakdown, a
list of recent commands, and a drill-down into any one command's full event
timeline. No writes, no bus access — it only ever reads the source of truth.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from yohan_dashboard_mvp import queries


def _approvals_panel() -> None:
    """Pending approvals with Approve / Reject buttons."""
    pending = queries.pending_approvals()
    if not pending:
        return
    st.subheader(f"⏳ Pending approvals ({len(pending)})")
    for item in pending:
        rid = item["request_id"]
        args = item["arguments"]
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (ValueError, TypeError):
                args = {}
        args = args or {}
        with st.container(border=True):
            st.markdown(f"**{item['action']}**")
            if item["action"] == "gmail.send_email":
                st.caption(f"To: {args.get('to','')} · Subject: {args.get('subject','')}")
                st.text((args.get("body", "") or "")[:400])
            else:
                st.write(args)
            approve, reject, _ = st.columns([1, 1, 4])
            if approve.button("✅ Approve", key=f"ok_{rid}"):
                queries.decide(rid, item["trace_id"], True)
                st.rerun()
            if reject.button("❌ Reject", key=f"no_{rid}"):
                queries.decide(rid, item["trace_id"], False)
                st.rerun()

st.set_page_config(page_title="Yohan", page_icon="🛰️", layout="wide")


def _fmt_ts(value) -> str:
    return value.strftime("%H:%M:%S") if value is not None else ""


@st.fragment(run_every="2s")
def live_view() -> None:
    """Everything data-backed lives here so it refreshes on its own every 2s."""
    try:
        totals = queries.totals()
        by_type = queries.event_type_counts()
        traces = queries.recent_traces()
    except Exception as exc:  # noqa: BLE001 — surface DB issues in the UI, don't crash.
        st.error(f"Can't read traces: {exc}")
        st.caption("Is Postgres up and the trace writer running?")
        return

    # --- headline numbers ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Commands", totals["traces"])
    c2.metric("Events", totals["events"])
    c3.metric("Failed", totals["failed"])
    c4.metric("Budget exceeded", totals["budget_exceeded"])

    # Action queue first — this is where the human is in the loop.
    _approvals_panel()

    left, right = st.columns([2, 1])

    # --- recent commands ---
    with left:
        st.subheader("Recent commands")
        if traces:
            df = pd.DataFrame(traces)
            df["status"] = df.apply(
                lambda r: "❌ error" if r["errored"] else ("✅ done" if r["completed"] else "… running"),
                axis=1,
            )
            df["started"] = df["started_at"].map(_fmt_ts)
            st.dataframe(
                df[["started", "status", "command", "reply", "events", "trace_id"]],
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("No commands yet. Send one through the gateway.")

    # --- event mix ---
    with right:
        st.subheader("Event mix")
        if by_type:
            st.bar_chart(
                pd.DataFrame(by_type).set_index("event_type")["n"],
                horizontal=True,
            )

    # --- drill-down ---
    st.subheader("Inspect a command")
    if traces:
        trace_id = st.selectbox(
            "trace_id",
            [t["trace_id"] for t in traces],
            format_func=lambda tid: f"{tid[:16]}…",
        )
        if trace_id:
            events = queries.events_for_trace(trace_id)
            rows = [
                {
                    "at": _fmt_ts(e["event_ts"]),
                    "event_type": e["event_type"],
                    "agent_id": e["agent_id"],
                    "payload": json.dumps(json.loads(e["payload"]), ensure_ascii=False)
                    if isinstance(e["payload"], str)
                    else json.dumps(e["payload"], ensure_ascii=False),
                }
                for e in events
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


st.title("🛰️ Yohan — live traces")
st.caption("Read-only view of the traces table. Auto-refreshes every 2s.")
live_view()
