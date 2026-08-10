#!/usr/bin/env bash
# Register the Telegram webhook so updates flow to your gateway via the tunnel.
#
# Prereqs (in infra/.env):
#   YOHAN_TELEGRAM_BOT_TOKEN       from @BotFather
#   YOHAN_TELEGRAM_WEBHOOK_SECRET  any random string (also read by the gateway)
#   YOHAN_PUBLIC_URL               your Cloudflare tunnel URL, e.g.
#                                  https://agent.yourdomain.com
#
# The tunnel itself is a separate long-running process, e.g.:
#   cloudflared tunnel --url http://localhost:8000
# (or a named tunnel mapped to a subdomain — see README).
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
[ -f infra/.env ] && . infra/.env
set +a

: "${YOHAN_TELEGRAM_BOT_TOKEN:?set YOHAN_TELEGRAM_BOT_TOKEN in infra/.env}"
: "${YOHAN_PUBLIC_URL:?set YOHAN_PUBLIC_URL in infra/.env}"

curl -fsS -X POST \
  "https://api.telegram.org/bot${YOHAN_TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{
    \"url\": \"${YOHAN_PUBLIC_URL}/telegram/webhook\",
    \"secret_token\": \"${YOHAN_TELEGRAM_WEBHOOK_SECRET}\",
    \"allowed_updates\": [\"message\"]
  }"
echo
echo "-> webhook set to ${YOHAN_PUBLIC_URL}/telegram/webhook"
