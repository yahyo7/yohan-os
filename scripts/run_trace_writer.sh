#!/usr/bin/env bash
# Run the trace writer: consumes the results stream and persists every event to
# Postgres. Applies the traces schema on startup.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
[ -f infra/.env ] && . infra/.env
set +a

exec uv run python -m yohan_trace_writer.writer
