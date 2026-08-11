#!/usr/bin/env bash
# Run the Next.js dashboard on :3000. It reads the gateway's SSE + REST API
# (NEXT_PUBLIC_API_BASE, default http://localhost:8000), so run the gateway too.
set -euo pipefail
cd "$(dirname "$0")/../apps/dashboard"

if [ ! -d node_modules ]; then
  echo "-> installing dashboard deps (first run)"
  pnpm install
fi

exec pnpm dev
