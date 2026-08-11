#!/usr/bin/env bash
# Run the supervisor agent as its own process, consuming its bus stream.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
[ -f infra/.env ] && . infra/.env
set +a
exec uv run python -m yohan_agents.supervisor.agent
