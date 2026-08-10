#!/usr/bin/env bash
# One-shot dev setup: install the workspace and start Redis + Postgres.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f infra/.env ]; then
  echo "-> creating infra/.env from example (fill in your Telegram token next)"
  cp infra/.env.example infra/.env
fi

echo "-> syncing uv workspace (all packages: core, agents, gateway)"
uv sync --all-packages

echo "-> starting redis + postgres"
docker compose -f infra/docker-compose.yml --env-file infra/.env up -d

echo
echo "Done. Next:"
echo "  1) put your Telegram bot token in infra/.env"
echo "  2) start the tunnel + register the webhook (see README)"
echo "  3) run the gateway and the echo agent in two terminals:"
echo "       scripts/run_gateway.sh"
echo "       scripts/run_echo.sh"
