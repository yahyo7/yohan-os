# Personal Agent OS — Project Brief

> Project codename: **Yohan**. (`agentos` in the original draft was a placeholder.)

## What this is

A personal agent control plane that runs on my M3 Pro MacBook, accepts commands
via Telegram (text + voice notes) and a local web dashboard, dispatches work to
specialist agents that run in parallel, and shows me live what they're doing. I
approve risky actions; everything else runs autonomously. Designed for a single
user (me), but architected as a control plane — modular enough to swap any layer.

## Vision

Build a small set of well-chosen primitives — a bus, a gateway, a tool layer —
and grow capability by adding agents, MCP servers, and skills, not by rewriting
the core. Anthropic's guidance applies: workflows by default, true agentic loops
only when the path can't be predicted. One agent shipped well beats five shipped
half-broken.

## Architecture

Layered, message-driven. Every command enters the gateway regardless of channel.
The gateway publishes a plan to the bus. Worker agents consume events from the
bus, do their job, publish results back. The dashboard subscribes read-only and
renders the live DAG. Approval gates are events on the bus, not in-process calls —
Telegram and the dashboard both publish `approved` / `rejected`.

Core principles, non-negotiable:

- **Bus is the contract.** Agents never call each other directly. Everything is events.
- **Every event persisted.** Postgres `traces` table is the source of truth for the dashboard and for replay.
- **Approval is per-tool, not per-prompt.** `requires_approval: true` in the MCP registry, enforced at the tool layer, not by hoping a prompt will hold.
- **Budgets on every loop.** Token, time, and tool-call caps. Hard stops.
- **Tools and skills loaded dynamically.** No agent ships with hardcoded tool lists.
- **Agents spawn on demand.** No long-lived workers in v1.

## Tech stack

**Runtime:** Python 3.12, `uv` for deps and workspaces · FastAPI + uvicorn
(gateway) · LangGraph (agent runtime, supervisor pattern, Postgres checkpointer)
· LangChain (loaders, retrievers, output parsers only — not the loop) · LiteLLM
(model abstraction — Ollama + Anthropic now, room for others).

**Models:** Ollama `qwen2.5:14b` (default worker), `llama3.2:3b` (router/classifier)
· Anthropic Claude (hard reasoning, complex multi-tool tasks). Routing decision
lives in the gateway, not in agents.

**Infra:** Redis Streams (message bus, asyncio client, consumer groups per agent
type) · Postgres 16 + pgvector (state, traces, long-term memory, LangGraph
checkpoints) · `asyncpg` for raw queries, SQLAlchemy 2.x async where an ORM helps
· Docker Compose for Postgres + Redis locally.

**Tools:** Official `mcp` Python SDK for client · `FastMCP` for our own MCP
servers (Visaro DB, KoryoCare ops, K-beauty inventory, etc.) · Off-the-shelf MCP
servers: filesystem, git, GitHub, fetch, Gmail, sequential-thinking.

**Channels:** `python-telegram-bot` (async) · Cloudflare Tunnel for the Telegram
webhook → M3 Pro · Whisper transcription via `mlx-whisper` (Metal-accelerated)
for Telegram voice notes.

**Dashboard:** Next.js 15 (App Router) + Tailwind + shadcn/ui · SSE from FastAPI
for live event stream · React Flow for the DAG · Phase 1 ships a minimal
Streamlit dashboard, replaced once the data model stabilizes.

## Repo structure

Monorepo, single git repo, uv workspaces for Python + pnpm for the Next.js app.
(The scaffold in this repo materializes only the Phase 0 subset of the tree below.)

```
yohan-os/
  apps/
    gateway/                     # FastAPI: Telegram webhook, dispatcher, SSE
    dashboard/                   # Next.js (phase 2)
    dashboard-mvp/               # Streamlit (phase 1, deleted later)
  packages/
    core/                        # event schemas (Pydantic), bus client, types
    agents/                      # LangGraph agent definitions
      supervisor/                # orchestrator graph
      email_triage/
      daily_briefing/
      devops/
      code_review/
    skills/                      # SKILL.md + optional python helpers
    mcp_servers/                 # our own MCP servers (visaro, koryocare_ops, …)
    integrations/                # telegram, whisper, litellm config, cloudflare
  infra/
    docker-compose.yml           # postgres + redis
    .env.example
    migrations/                  # alembic
  scripts/
  evals/                         # eval harness, real task fixtures
  pyproject.toml                 # uv workspace root
  pnpm-workspace.yaml
  README.md
  PROJECT_BRIEF.md
```

## Event schema (the contract)

Every event on the bus has: `trace_id`, `agent_id`, `event_type`, `timestamp`,
`payload`. Event types: `command_received`, `plan_created`, `task_assigned`,
`task_started`, `tool_called`, `tool_returned`, `output_produced`,
`approval_requested`, `approval_granted`, `approval_denied`, `task_completed`,
`task_failed`, `budget_exceeded`. Defined as Pydantic models in
`packages/core/events.py`. Every event also written to the `traces` table by a
single subscriber.

## First agents (v1 scope)

1. **Email triage** — fetch unread Gmail, classify (needs reply / FYI / spam),
   draft replies for "needs reply", never sends without approval. Uses official
   Gmail MCP server.
2. **Daily briefing** — runs on schedule (07:00 KST), summarizes calendar +
   unread urgent emails + overnight GitHub activity + Visaro app metrics, sends
   to Telegram.
3. **DevOps** — watches KoryoCare and Visaro health, alerts to Telegram on
   anomalies, can run pre-approved diagnostic commands via SSH MCP. Deploy
   actions always gated.
4. **Code review** — triggered by GitHub webhook or manual command, reviews PR
   diffs against project conventions, posts inline comments draft for approval.

## Build phases

- **Phase 0 — Skeleton (week 1).** Repo scaffolding, docker-compose, gateway
  hello-world, Telegram webhook via Cloudflare Tunnel, event schema in
  `packages/core`, bus client wrapper, single trivial agent (echo), end-to-end
  loop working text → Telegram → bus → agent → reply.
- **Phase 1 — Persistence + observability (week 2).** Traces table + writer
  subscriber, Streamlit dashboard subscribing to bus, structured logging,
  LangGraph Postgres checkpointer wired in.
- **Phase 2 — First real agent (week 3).** Email triage end-to-end with Gmail
  MCP server, approval gates on send, approval buttons in Telegram + Streamlit.
- **Phase 3 — Multi-agent + dispatch (week 4).** Supervisor graph dispatches in
  parallel, daily briefing agent, scheduler subscriber (cron-on-bus).
- **Phase 4 — Tool layer formalized (week 5).** MCP registry config
  (`infra/mcp_registry.yaml`), skills directory with first 3 skills, dynamic
  loading. Refactor existing agents to use the registry.
- **Phase 5 — Production-shape dashboard (week 6).** Next.js dashboard with
  React Flow DAG, SSE event stream, approval UI, history view. Retire Streamlit.
- **Phase 6 — Voice + remaining agents (week 7+).** Whisper transcription for
  Telegram voice notes, devops agent, code review agent.

Ongoing: eval harness with 20-30 real tasks, budget enforcement, sandbox
hardening, MCP server expansion.

## Hard requirements baked in from day one

- Every model call goes through LiteLLM. No direct `ollama.chat` or
  `anthropic.messages.create` anywhere except the LiteLLM config.
- Every tool call goes through an MCP client. No direct API calls from agent code.
- Every side-effectful tool declares `requires_approval`. Enforced at the tool layer.
- Every agent run has a budget. Default: 50k tokens, 5 min, 30 tool calls.
- `trace_id` propagates through every event, log, and DB row.

## Out of scope for v1

Multi-user, auth, RBAC · real-time / streaming voice (push-to-talk and voice
notes only) · inter-agent natural-language conversation (agents communicate via
bus events, period) · cloud deployment (M3 Pro is the runtime) · A2A protocol
(Redis Streams is sufficient for single-user).
