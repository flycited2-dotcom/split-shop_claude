from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
]

THIRD_PARTY_APPS = [
    'django_htmx',
    'django_filters',
    'django_celery_beat',
]

LOCAL_APPS = [
    'apps.catalog',
    'apps.stock',
    'apps.accounts',
    'apps.orders',
    'apps.export',
    'apps.sync',
    'apps.leads',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'oasis.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'apps.orders.context_processors.cart_count',
            'apps.catalog.context_processors.yandex_metrika',
        ],
    },
}]

WSGI_APPLICATION = 'oasis.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_USER_MODEL = 'accounts.CustomUser'
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/account/'
LOGOUT_REDIRECT_URL = '/'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL'),
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}

CELERY_BROKER_URL = config('REDIS_URL')
CELERY_RESULT_BACKEND = config('REDIS_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Moscow'

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'sync-stock-hourly': {
        'task': 'sync.sync_stock',
        'schedule': crontab(minute=5),
    },
    'sync-catalog-4h': {
        'task': 'sync.sync_catalog',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    'sync-rusklimat-stock-hourly': {
        'task': 'sync.sync_rusklimat_stock',
        'schedule': crontab(minute=15),
    },
    'sync-rusklimat-catalog-daily': {
        'task': 'sync.sync_rusklimat_catalog',
        'schedule': crontab(minute=30, hour=3),
    },
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

BREEZ_AUTH_HEADER = config('BREEZ_AUTH_HEADER')
BREEZ_BASE_URL = config('BREEZ_BASE_URL', default='https://api.breez.ru/v1/')

RUSKLIMAT_JWT_TOKEN = config('RUSKLIMAT_JWT_TOKEN', default='')
RUSKLIMAT_CONTRACTOR_GUID = config('RUSKLIMAT_CONTRACTOR_GUID', default='')
RUSKLIMAT_LOGIN = config('RUSKLIMAT_LOGIN', default='')
RUSKLIMAT_PASSWORD = config('RUSKLIMAT_PASSWORD', default='')
RUSKLIMAT_AC_CATALOG_URL = config(
    'RUSKLIMAT_AC_CATALOG_URL',
    default='https://b2b.rusklimat.com/catalog/1162450-konditsionery-bytovye/',
)

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@oasis.com.ru')
MANAGER_EMAIL = config('MANAGER_EMAIL', default='')
TELEGRAM_BOT_TOKEN = config('TELEGRAM_BOT_TOKEN', default='')
TELEGRAM_CHAT_ID = config('TELEGRAM_CHAT_ID', default='')
YANDEX_METRIKA_ID = config('YANDEX_METRIKA_ID', default='')
