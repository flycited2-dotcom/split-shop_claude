"""Принудительно обновляет JWT для Rusklimat REST API.

Использование:
  python manage.py refresh_rusklimat_jwt          # тихо
  python manage.py refresh_rusklimat_jwt --show   # вывести первые символы токена

Обычно вызов не нужен — обновлением занимается Celery Beat в 23:50 МСК
(см. sync.refresh_rusklimat_jwt). Команда нужна для:
  - первого запуска после деплоя (когда кэш пуст и cron ещё не отработал);
  - дебага auth-эндпоинта;
  - принудительного обновления при подозрении на ротацию.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.sync.rusklimat_auth import RusklimatAuthError, fetch_jwt


class Command(BaseCommand):
    help = 'Запрашивает свежий Rusklimat JWT и кладёт в Django cache.'

    def add_arguments(self, parser):
        parser.add_argument('--show', action='store_true',
                            help='Показать первые 40 символов полученного токена')

    def handle(self, *args, **opts):
        try:
            token = fetch_jwt()
        except RusklimatAuthError as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS(
            f'JWT обновлён (длина {len(token)} символов)'
        ))
        if opts['show']:
            self.stdout.write(f'  токен: {token[:40]}…')
