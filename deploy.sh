#!/bin/bash
set -e

echo "=== Деплой SplitHome ==="

docker compose pull
docker compose build

docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py collectstatic --noinput

docker compose up -d

docker compose run --rm web python manage.py sync_all

echo "Создать суперпользователя? (y/n)"
read CREATE_SU
if [ "$CREATE_SU" = "y" ]; then
    docker compose run --rm web python manage.py createsuperuser
fi

echo "=== Деплой завершён. Сайт доступен на https://splithome.ru ==="
