"""JWT auto-refresh для b2b.rusklimat.com.

Спецификация (владелец, 2026-05-24):
  POST https://b2b.rusklimat.com/api/v1/auth/jwt/
  Headers: User-Agent: catalog-ip, Content-Type: application/json
  Body:    {"login": <...>, "password": <...>}
  Response: {"data": {"jwtToken": "..."}}

Ключевые нюансы:
- Токен сбрасывается строго в 00:00 МСК (НЕ +24 часа от выпуска). Поэтому
  cron-обновление через Celery Beat настроено на 23:50 Europe/Moscow.
- Заголовок User-Agent: catalog-ip ОБЯЗАТЕЛЕН — без него auth-эндпоинт
  отвечает 401 / «Invalid user/password» даже при правильных кредах.
- Кэш токена — Django cache (Redis). Между процессами gunicorn/celery
  безопасно: read-modify-write race не критичен (худший случай — два
  процесса дёрнут refresh параллельно, последний выиграет, оба токена
  валидны до 00:00).
- Locking — threading.Lock внутри процесса, чтобы конкурентные запросы из
  одного web-воркера не плодили refresh.
"""
import logging
import threading

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

AUTH_URL = 'https://b2b.rusklimat.com/api/v1/auth/jwt/'
USER_AGENT = 'catalog-ip'
CACHE_KEY = 'rusklimat:jwt'
# TTL — верхняя граница; реальный сброс в 00:00 МСК делает Celery cron.
CACHE_TTL = 24 * 60 * 60

_lock = threading.Lock()


class RusklimatAuthError(RuntimeError):
    """Не удалось получить/обновить JWT."""


def _credentials_configured():
    return bool(settings.RUSKLIMAT_LOGIN and settings.RUSKLIMAT_PASSWORD)


def fetch_jwt():
    """Запрашивает свежий JWT у b2b.rusklimat.com и кладёт в cache.

    Возвращает токен (str). Бросает RusklimatAuthError при отсутствии
    кредов или сетевой/HTTP ошибке.
    """
    if not _credentials_configured():
        raise RusklimatAuthError(
            'RUSKLIMAT_LOGIN / RUSKLIMAT_PASSWORD не заданы в .env — '
            'нельзя автообновить JWT.'
        )
    try:
        resp = requests.post(
            AUTH_URL,
            json={
                'login': settings.RUSKLIMAT_LOGIN,
                'password': settings.RUSKLIMAT_PASSWORD,
            },
            headers={
                'User-Agent': USER_AGENT,
                'Content-Type': 'application/json',
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.error('Rusklimat JWT refresh: network error: %s', exc)
        raise RusklimatAuthError(f'network error: {exc}') from exc

    if resp.status_code != 200:
        logger.error('Rusklimat JWT refresh: HTTP %s: %s',
                     resp.status_code, resp.text[:300])
        raise RusklimatAuthError(
            f'auth-эндпоинт вернул {resp.status_code}: {resp.text[:200]}'
        )

    try:
        token = resp.json()['data']['jwtToken']
    except (ValueError, KeyError) as exc:
        logger.error('Rusklimat JWT refresh: unexpected payload: %s', resp.text[:300])
        raise RusklimatAuthError(f'unexpected response shape: {exc}') from exc

    cache.set(CACHE_KEY, token, timeout=CACHE_TTL)
    logger.info('Rusklimat JWT refreshed (length=%d)', len(token))
    return token


def get_jwt():
    """Возвращает текущий JWT.

    1) cache.get(CACHE_KEY) — если есть, возвращаем.
    2) если LOGIN/PASSWORD заданы — fetch_jwt() (под lock'ом).
    3) legacy fallback: settings.RUSKLIMAT_JWT_TOKEN, если задан.
    4) иначе — RusklimatAuthError.
    """
    token = cache.get(CACHE_KEY)
    if token:
        return token

    with _lock:
        # Double-checked locking: пока ждали — мог обновить другой поток.
        token = cache.get(CACHE_KEY)
        if token:
            return token

        if _credentials_configured():
            try:
                return fetch_jwt()
            except RusklimatAuthError as exc:
                # Auth-эндпоинт упал (сменили пароль, временный 401, network).
                # Чтобы не ронять весь sync — fallback на статичный токен.
                if settings.RUSKLIMAT_JWT_TOKEN:
                    logger.warning(
                        'fetch_jwt failed (%s) — fallback на статичный RUSKLIMAT_JWT_TOKEN.',
                        exc,
                    )
                    return settings.RUSKLIMAT_JWT_TOKEN
                raise

        legacy = settings.RUSKLIMAT_JWT_TOKEN
        if legacy:
            logger.warning(
                'RUSKLIMAT_LOGIN/PASSWORD не заданы — используем статический '
                'RUSKLIMAT_JWT_TOKEN из .env (legacy fallback).'
            )
            return legacy

        raise RusklimatAuthError(
            'JWT недоступен: нет ни LOGIN/PASSWORD, ни статичного RUSKLIMAT_JWT_TOKEN.'
        )


def invalidate_jwt():
    """Сбрасывает кэш — вызывается при 401 перед retry."""
    cache.delete(CACHE_KEY)
