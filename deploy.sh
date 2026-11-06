#!/usr/bin/env bash
# Выкладка splithome.ru на прод (/opt/oasis, 212.116.115.150).
#
#   ./deploy.sh                  # код берётся через git fetch origin
#   ./deploy.sh /path/x.bundle   # у прода нет доступа к GitHub: коммиты привозят
#                                # bundle'ом (git bundle create x.bundle <было>..origin/develop)
#
# Пересобирает и пересоздаёт ТОЛЬКО web, celery и beat. db, redis и tg_proxy не
# трогает: сервер общий, на db (172.30.0.20) завязаны соседние стеки.
# Ничего не спрашивает. Не делает compose pull, sync_all и createsuperuser.
#
# Порядок: проверки → fast-forward до origin/develop → пауза сторожевого таймера →
# сборка (старые образы сохраняются с тегом :prev) → migrate → collectstatic →
# копирование статики в хостовую папку nginx → up --no-deps → проверка.
#
# Откат на прошлый образ (код в git откатывать отдельно):
#   for s in web celery beat; do docker tag oasis-$s:prev oasis-$s:latest; done
#   docker compose up -d --no-deps web celery beat
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

BRANCH=develop
SERVICES=(web celery beat)
PROJECT="$(basename "$PWD")"          # имя compose-проекта = имя каталога (oasis)
MIN_FREE_GB=3
URL=https://splithome.ru/
HEALTH_TIMER=oasis-health.timer       # при ошибке сайта сам делает docker compose up -d

say() { printf '\n=== %s\n' "$*"; }
die() { printf '\nОШИБКА: %s\n' "$*" >&2; exit 1; }

# --- 1. Проверки -------------------------------------------------------------
say "Проверки"
[ "$(git rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || die "сервер не на ветке $BRANCH"
if ! git diff --quiet || ! git diff --cached --quiet; then
  die "в рабочем дереве незакоммиченные правки (git status). Прод собирается только из git"
fi
free_gb=$(df -BG --output=avail . | tail -1 | tr -dc '0-9')
[ "$free_gb" -ge "$MIN_FREE_GB" ] || die "свободно ${free_gb} ГБ, нужно не меньше ${MIN_FREE_GB} (сервер общий)"
[ -f .dockerignore ] || die "нет .dockerignore: в образ уйдут staticfiles/ (3 ГБ) и .env"
echo "ветка $BRANCH, дерево чистое, свободно ${free_gb} ГБ"

# --- 2. Код ------------------------------------------------------------------
say "Код"
if [ $# -ge 1 ]; then
  bundle="$1"
  git bundle verify -q "$bundle"
  ref=$(git bundle list-heads "$bundle" | awk 'NR==1 {print $2}')
  [ -n "$ref" ] || die "в bundle нет ссылок"
  git fetch "$bundle" "$ref:refs/remotes/origin/$BRANCH"
else
  timeout 60 git fetch origin "$BRANCH" \
    || die "git fetch не прошёл (у прода нет доступа к GitHub?). Привезите bundle: ./deploy.sh x.bundle"
fi
old=$(git rev-parse --short HEAD)
git merge --ff-only "origin/$BRANCH"
new=$(git rev-parse --short HEAD)
echo "код: $old -> $new"

# --- 3. Пауза сторожевого таймера ---------------------------------------------
# Пока web пересоздаётся, сайт несколько секунд отдаёт 502. Таймер в это окно
# сделал бы полный docker compose up -d. Возвращаем его при любом выходе.
if systemctl is-active -q "$HEALTH_TIMER" 2>/dev/null; then
  systemctl stop "$HEALTH_TIMER"
  trap 'systemctl start "$HEALTH_TIMER"; echo "($HEALTH_TIMER снова включён)"' EXIT
  echo "$HEALTH_TIMER приостановлен на время выкладки"
fi

# --- 4. Сборка ---------------------------------------------------------------
say "Сборка ${SERVICES[*]}"
for s in "${SERVICES[@]}"; do
  if docker image inspect "$PROJECT-$s:latest" >/dev/null 2>&1; then
    docker tag "$PROJECT-$s:latest" "$PROJECT-$s:prev"
  fi
done
docker compose build "${SERVICES[@]}"

# --- 5. Миграции и статика (новым образом, до переключения) -------------------
say "Миграции"
docker compose run --rm --no-deps web python manage.py migrate --noinput

say "Статика"
docker compose run --rm --no-deps web python manage.py collectstatic --noinput
# collectstatic пишет в docker-том, а nginx раздаёт /static/ из хостовой папки
# /opt/oasis/staticfiles. Без копирования сайт отдаёт старый CSS.
vol=$(docker volume inspect -f '{{.Mountpoint}}' "${PROJECT}_static_files")
rsync -a "$vol/" staticfiles/

# --- 6. Переключение ---------------------------------------------------------
say "Запуск ${SERVICES[*]}"
docker compose up -d --no-deps "${SERVICES[@]}"

# --- 7. Проверка -------------------------------------------------------------
say "Проверка"
ok=""
for _ in $(seq 1 30); do
  if curl -fsS -m 10 -o /dev/null "$URL"; then ok=1; break; fi
  sleep 2
done
[ -n "$ok" ] || die "$URL не отвечает после выкладки. Откат: см. шапку скрипта"
echo "сайт отвечает"

docker compose exec -T web python -c "
import django; django.setup()
from celery import current_app as app
with app.connection_for_write() as c:
    c.ensure_connection(max_retries=1)
print('web -> брокер: ok')
" || die "web не достаёт до брокера celery (заявки не поставят задачи в очередь)"

docker compose exec -T celery celery -A splithome inspect ping -t 15 >/dev/null \
  || die "celery-воркер не отвечает на ping"
echo "celery-воркер: ok"

say "Готово: $old -> $new"
