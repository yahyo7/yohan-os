#!/usr/bin/env bash
# Run the Streamlit MVP dashboard on :8501 (read-only view of the traces table).
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
[ -f infra/.env ] && . infra/.env
set +a

exec uv run streamlit run apps/dashboard-mvp/streamlit_app.py \
  --server.address 127.0.0.1 --server.port 8501 --server.headless true
