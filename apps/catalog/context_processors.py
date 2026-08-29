import os
from pathlib import Path

from django.conf import settings


def static_version(request):
    """Метка версии CSS для ?v= в base.html.

    Nginx отдаёт /static/ с `max-age=2592000` (30 дней), а имена файлов не
    хэшируются — после деплоя вернувшийся посетитель месяц видел старую
    вёрстку (поймано 2026-08-29: правки квиза не доезжали до браузера).
    Берём mtime собранного tailwind.css: он меняется при каждой пересборке,
    и в кэше появляется новый URL. Файла нет — пустая строка, ссылка
    остаётся прежней.
    """
    candidates = [Path(settings.BASE_DIR) / 'static']
    candidates += [Path(d) for d in getattr(settings, 'STATICFILES_DIRS', [])]
    for base in candidates:
        try:
            return {'STATIC_VERSION': str(int(os.path.getmtime(base / 'css' / 'tailwind.css')))}
        except OSError:
            continue
    return {'STATIC_VERSION': ''}


def yandex_metrika(request):
    return {'YANDEX_METRIKA_ID': getattr(settings, 'YANDEX_METRIKA_ID', '')}


def seo_verification(request):
    """Токены подтверждения прав для панелей вебмастеров (Google/Yandex/Bing).
    Рендерятся в base.html как <meta> только при заполненном значении.
    """
    return {
        'GOOGLE_SITE_VERIFICATION': getattr(settings, 'GOOGLE_SITE_VERIFICATION', ''),
        'YANDEX_VERIFICATION': getattr(settings, 'YANDEX_VERIFICATION', ''),
        'BING_SITE_VERIFICATION': getattr(settings, 'BING_SITE_VERIFICATION', ''),
    }
