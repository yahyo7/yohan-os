#!/usr/bin/env bash
# Run the FastAPI gateway on :8000. Loads infra/.env so tokens/DSNs are present.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
[ -f infra/.env ] && . infra/.env
set +a

exec uv run uvicorn yohan_gateway.main:app --host 0.0.0.0 --port 8000 --reload
