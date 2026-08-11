#!/usr/bin/env bash
# Run the email-triage agent as its own process, consuming its bus stream.
# Needs the Gmail MCP server authorized (npx @gongrzhe/server-gmail-autoauth-mcp
# auth) for live Gmail; classification falls back to heuristics without Ollama.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
[ -f infra/.env ] && . infra/.env
set +a

exec uv run python -m yohan_agents.email_triage.agent
