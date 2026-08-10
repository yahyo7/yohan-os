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

## What's next

- **Phase 1 (remaining)** — Streamlit dashboard subscribing to the bus,
  structured logging, LangGraph Postgres checkpointer.
- **Phase 2** — email-triage agent + approval gates.

See `PROJECT_BRIEF.md` for the full plan.
