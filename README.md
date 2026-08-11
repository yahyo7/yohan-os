# Yohan

A personal agent control plane. Commands enter through a **gateway** (Telegram
now, dashboard later), get published to a **bus** (Redis Streams), and are picked
up by **agents** running as their own processes that publish results back. The
gateway relays results to the originating channel.

> Status: **Phase 0 — skeleton.** One trivial agent (`echo`) proving the
> end-to-end loop: text → Telegram → bus → agent → reply. No persistence, no
> real agents, no dashboard yet — those are Phases 1+.

## Layout

```
apps/gateway         FastAPI: Telegram webhook, dispatcher, results relay
apps/trace_writer    persists every bus event to Postgres (Phase 1)
apps/dashboard-mvp   throwaway Streamlit view over traces (Phase 1, retired in Phase 5)
packages/core        the contract — event schema, bus client, db + traces store
packages/agents      worker agents; Phase 0 ships `echo`
infra                docker-compose (redis + postgres), migrations, .env.example
scripts              bootstrap / run / webhook helpers
```

`packages/core` is the base of the dependency graph: the gateway and agents both
depend on it, never on each other. Agents talk only via bus events.

## The contract

Every event on the bus is a `yohan_core.Event`:

| field        | meaning                                             |
|--------------|-----------------------------------------------------|
| `trace_id`   | stitches one command's whole causal chain together  |
| `agent_id`   | who emitted it (`gateway`, `echo-1a2b3c4d`, …)       |
| `event_type` | one of the `EventType` enum values                  |
| `timestamp`  | UTC, set at creation                                |
| `payload`    | open dict — per-event-type detail                   |

## Run it (Phase 0)

Prereqs: `uv`, Docker, a Telegram bot token from **@BotFather**, and
`cloudflared` for the tunnel.

```bash
# 1. install workspace + start redis/postgres
scripts/bootstrap.sh

# 2. put your token in infra/.env
#    YOHAN_TELEGRAM_BOT_TOKEN=...
#    YOHAN_TELEGRAM_WEBHOOK_SECRET=<any random string>

# 3. expose the gateway. Quick tunnel:
cloudflared tunnel --url http://localhost:8000
#    (or a named tunnel mapped to agent.yourdomain.com — recommended, stable URL)
#    put the resulting https URL in infra/.env as YOHAN_PUBLIC_URL

# 4. two processes, two terminals:
scripts/run_gateway.sh      # FastAPI on :8000
scripts/run_echo.sh         # echo agent consuming the bus

# 5. register the webhook, then message your bot
scripts/set_webhook.sh
```

Text your bot **"hello"** → you get **"echo: hello"** back. That round-trip is
the whole Phase 0 acceptance test.

### Without Telegram

To exercise the loop with no bot/tunnel, run Redis (`scripts/bootstrap.sh`), the
echo agent, then the smoke script — it publishes a command straight onto the bus
and prints the reply:

```bash
scripts/run_echo.sh                    # in one terminal
uv run python scripts/smoke_echo.py    # in another
```

## Cloudflare Tunnel (do this first)

Set the tunnel up before anything else — without it Telegram can't reach your
laptop. A named tunnel gives you a stable subdomain:

```bash
cloudflared tunnel login
cloudflared tunnel create yohan
# map agent.yourdomain.com -> http://localhost:8000 in your tunnel config,
# then run:  cloudflared tunnel run yohan
```

## Traces (Phase 1)

Every event on the bus is persisted to the Postgres `traces` table by a single
subscriber, `apps/trace_writer` — which joins the results stream as its own
consumer group (`grp:tracewriter`), independent of the gateway relay. Both see
every event; neither disturbs the other. Adding it required no change to the
gateway or agents.

```bash
scripts/run_trace_writer.sh    # applies the schema on startup, then persists events
```

Inspect a run's full causal chain:

```bash
docker exec yohan-postgres psql -U yohan -d yohan -c \
  "SELECT event_type, agent_id, payload->>'reply' FROM traces \
   WHERE trace_id = '<trace_id>' ORDER BY id;"
```

Inserts are idempotent on `(stream, entry_id)`, so the bus's at-least-once
delivery yields exactly-once rows.

## Dashboard (Phase 1 MVP)

A read-only Streamlit view over the traces table — live totals, an event-type
breakdown, recent commands, and a per-command event timeline. It reads Postgres
only (never the bus), so it can't perturb what it observes. Disposable; the
Next.js + React Flow dashboard replaces it in Phase 5.

```bash
scripts/run_dashboard.sh       # http://127.0.0.1:8501, auto-refreshes every 2s
```

## Structured logging (Phase 1)

Every process configures JSON logging via `configure_logging(service)`. Each line
is one JSON object — `service`, `level`, `logger`, `msg`, `ts` — enriched with
`trace_id` whenever one is bound. The trace id rides a `ContextVar`, so the
consume loop / webhook handler binds it once per command and every log line
beneath inherits it (third-party logs like `httpx` included). This is the log
half of the brief's rule that `trace_id` propagates through every event, log,
and DB row.

```json
{"ts":"…","level":"INFO","service":"agent:echo","logger":"yohan_agents.base","msg":"task completed","trace_id":"trc_…","elapsed_seconds":0.001}
```

Grep one command across every process with its `trace_id`.

## Email triage + approvals (Phase 2)

The first real agent. `apps/gateway` routes email/inbox/triage/unread commands to
the email-triage agent, which runs a fixed workflow — search unread → read →
classify → draft → send. `gmail.send_email` is gated in `infra/mcp_registry.yaml`,
so a send parks on an approval event; the drafted reply is shown and only a grant
lets it through.

Approve/reject from either channel:
- **Telegram** — inline ✅/❌ buttons on the prompt; a tap publishes the decision.
- **Streamlit** — a "Pending approvals" panel at the top of the dashboard.

Both publish to the approvals stream; the parked agent resolves and continues.

```bash
scripts/run_email_triage.sh    # the agent (needs Gmail MCP OAuth for live Gmail)
```

Going live needs two things this repo can't do for you: authorize the Gmail MCP
server (`npx @gongrzhe/server-gmail-autoauth-mcp auth`) and run Ollama (or set
`ANTHROPIC_API_KEY`) for real classification. Without them the pipeline still
runs — classification falls back to heuristics.

## Multi-agent dispatch (Phase 3)

- **Supervisor** (`yohan_agents.supervisor`) plans a command into parallel tasks
  and fans them out via `yohan_core.dispatch`, aggregating results into one reply.
  `morning`/`briefing`/`fanout` route here.
- **Daily briefing** (`yohan_agents.daily_briefing`) gathers email/GitHub/calendar
  sections concurrently, each degrading gracefully when its source isn't connected.
- **Scheduler** (`apps/scheduler`, cron-on-bus) publishes scheduled commands onto
  the bus — same path as interactive commands. `infra/schedules.yaml` drives it
  (07:00 KST briefing by default; set your `chat_id`).

```bash
scripts/run_supervisor.sh
scripts/run_daily_briefing.sh
scripts/run_scheduler.sh
```

Dispatch shares the parent `trace_id` across the fan-out, with a `task_id` per
branch, so a multi-agent command stays one causal chain.

## Skills (Phase 4)

Agent prompts aren't hardcoded — they're **skills** loaded at runtime from
`packages/skills/<name>/SKILL.md` (YAML frontmatter: name, description,
model_role; body is a `{placeholder}` prompt template). Edit or version a prompt
without touching Python.

- `triage_classify`, `triage_draft` — used by the email-triage agent.
- `morning_briefing` — used by the daily-briefing agent to compose sections.

`yohan_core.load_skill(name)` loads one; `available_skills()` discovers them.
Combined with the MCP registry (tools) from Phase 2, both tools and skills are
loaded dynamically — no agent ships a hardcoded list.

## What's next

- **Phase 5** — Next.js + React Flow dashboard (retires Streamlit).
- **Phase 6** — voice (Whisper) + devops / code-review agents.
- Deferred: LangGraph Postgres checkpointer (lands with the first agent whose path
  isn't predictable); a pinned long-lived MCP session (tool layer is per-call now).

See `PROJECT_BRIEF.md` for the full plan.
