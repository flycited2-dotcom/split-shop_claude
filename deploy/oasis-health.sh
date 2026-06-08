#!/usr/bin/env bash
# Слой 3: монитор splithome.ru.
# Проверяет публичную доступность сайта. Если сайт не отвечает — пытается
# поднять Docker-стек (docker compose up -d) и шлёт Telegram-алерт.
# Алерты — только на СМЕНУ состояния (нет спама каждые 2 минуты).
#
# Креды Telegram читаются из /opt/oasis/.watchdog.env (НЕ в git):
#   TG_TOKEN=<токен живого бота>
#   TG_CHAT=<chat_id>
#   TG_API=https://api.telegram.org:9443   # через socat-proxy на хосте
set -uo pipefail

PROJECT_DIR=/opt/oasis
URL="https://splithome.ru/"
STATE_FILE=/var/lib/oasis-health/state
ENV_FILE=/opt/oasis/.watchdog.env
LOG_TAG=oasis-health

mkdir -p "$(dirname "$STATE_FILE")"
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

log() { logger -t "$LOG_TAG" -- "$1"; }

notify() {
  # $1 = текст. Отправляем только при наличии кредов.
  [ -n "${TG_TOKEN:-}" ] && [ -n "${TG_CHAT:-}" ] || return 0
  local api="${TG_API:-https://api.telegram.org:9443}"
  curl -s -m 12 --resolve api.telegram.org:9443:172.30.0.1 \
    "${api}/bot${TG_TOKEN}/sendMessage" \
    -d chat_id="${TG_CHAT}" \
    --data-urlencode text="$1" \
    -d parse_mode=HTML >/dev/null 2>&1 || true
}

# Сайт жив, если публичный URL отвечает без ошибки (строгая проверка цепочки
# nginx → gunicorn → БД; строгий TLS ловит и протухший сертификат).
check() { curl -fsS -m 10 -o /dev/null "$URL"; }

prev="up"
[ -f "$STATE_FILE" ] && prev="$(cat "$STATE_FILE")"

if check; then
  if [ "$prev" = "down" ]; then
    log "site recovered"
    notify "✅ splithome.ru снова доступен."
  fi
  echo up > "$STATE_FILE"
  exit 0
fi

# Сайт не отвечает — попытка авто-восстановления стека.
log "site DOWN — attempting docker compose up -d"
( cd "$PROJECT_DIR" && /usr/bin/docker compose up -d ) >/dev/null 2>&1
sleep 20

if check; then
  log "recovered after up -d"
  notify "♻️ splithome.ru падал — автоматически поднят (docker compose up -d). Сейчас доступен."
  echo up > "$STATE_FILE"
else
  log "still DOWN after recovery attempt"
  if [ "$prev" != "down" ]; then
    notify "🔴 splithome.ru НЕ доступен и не поднялся автоматически. Нужно вмешательство.
Сервер 213.109.202.45, каталог /opt/oasis."
  fi
  echo down > "$STATE_FILE"
fi
