#!/usr/bin/env bash
# Run the cron-on-bus scheduler: fires infra/schedules.yaml jobs onto the bus.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
[ -f infra/.env ] && . infra/.env
set +a

exec uv run python -m yohan_scheduler.scheduler
