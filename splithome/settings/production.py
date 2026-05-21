from .base import *

DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = ['https://splithome.ru', 'https://www.splithome.ru']

# Cache-busting через хешированные имена: tailwind.css → tailwind.a1b2c3d4.css.
# Браузер не отдаёт устаревший CSS после deploy, что важно после ухода с
# Tailwind CDN — раньше CSS жил на стороне Tailwind, теперь у нас в static/.
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# При DEBUG=False Django не пишет traceback'и нигде по умолчанию (AdminEmailHandler
# не сконфигурирован) — 500 уходят в /dev/null. Минимальный StreamHandler даёт
# полный traceback в `docker compose logs web`.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}
