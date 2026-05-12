from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']  # WARNING: for local dev only — never set DJANGO_SETTINGS_MODULE=local on servers
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
