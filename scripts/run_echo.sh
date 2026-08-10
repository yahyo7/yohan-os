#!/usr/bin/env bash
# Run the echo agent as its own process, consuming the echo stream off the bus.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
[ -f infra/.env ] && . infra/.env
set +a

exec uv run python -m yohan_agents.echo.agent
