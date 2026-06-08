# Авто-восстановление splithome.ru

Три слоя защиты, чтобы сайт поднимался сам и владелец узнавал о сбоях.

| Слой | Что | Где |
|---|---|---|
| 1. Политика перезапуска | `restart: always` у всех сервисов | `docker-compose.yml` |
| 2. Старт при загрузке | systemd-юнит `docker compose up -d` на boot | `deploy/oasis.service` |
| 3. Монитор + алерт | таймер каждые 2 мин: проверка → авто-подъём → Telegram | `deploy/oasis-health.*` |

## Почему так

Инцидент 08.06.2026: у `db/redis/web/celery/beat` не было политики `restart` (= `no`),
поэтому после ребута сервера (апгрейд ядра 05.06) стек не поднялся и сайт лежал 3 дня.

- `restart: always` (а не `unless-stopped`) поднимает контейнеры после ребута,
  **даже если их перед этим остановили вручную** — ровно тот сценарий, что был.
- systemd-юнит покрывает случай `docker compose down` (контейнеры удалены — политике
  restart нечего перезапускать).
- Монитор — на случай, если самовосстановление не сработает, и чтобы не лежать
  3 дня незаметно.

## Установка на сервере (однократно)

```bash
cd /opt/oasis && git pull --ff-only origin develop

# Слой 1: применить restart-политику к уже запущенным контейнерам без пересоздания
docker update --restart=always \
  oasis-db-1 oasis-redis-1 oasis-web-1 oasis-celery-1 oasis-beat-1 oasis-tg_proxy-1

# Слой 3: креды Telegram для алертов (НЕ в git!)
cat > /opt/oasis/.watchdog.env <<'EOF'
TG_TOKEN=<токен живого бота>
TG_CHAT=1264067528
TG_API=https://api.telegram.org:9443
EOF
chmod 600 /opt/oasis/.watchdog.env
chmod +x /opt/oasis/deploy/oasis-health.sh

# Слои 2 и 3: установить systemd-юниты
cp /opt/oasis/deploy/oasis.service          /etc/systemd/system/
cp /opt/oasis/deploy/oasis-health.service   /etc/systemd/system/
cp /opt/oasis/deploy/oasis-health.timer     /etc/systemd/system/
systemctl daemon-reload
systemctl enable oasis.service          # старт стека при загрузке
systemctl enable --now oasis-health.timer   # монитор каждые 2 мин
```

## Проверка

```bash
systemctl status oasis-health.timer --no-pager
/opt/oasis/deploy/oasis-health.sh && echo OK   # ручной прогон, ждём тест-алерт «recovered» только если был down
docker inspect -f '{{.Name}} {{.HostConfig.RestartPolicy.Name}}' \
  oasis-db-1 oasis-web-1 oasis-redis-1 oasis-celery-1 oasis-beat-1   # все = always
journalctl -t oasis-health -n 20 --no-pager
```

Тест боевого сценария: `docker compose stop web` → в течение 2 минут монитор должен
поднять стек и прислать алерт в Telegram.
