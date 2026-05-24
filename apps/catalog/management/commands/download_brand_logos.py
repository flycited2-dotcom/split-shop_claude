"""Скачивает логотипы брендов в static/images/brands/{slug}.{ext}.

Берёт все Brand с featured_in_quiz=True и непустым logo_url, тянет файл,
сохраняет с расширением по Content-Type. Используется шагом «Бренд» в квизе:
`apps/leads/views.py:_brand_logo_static` ищет файл `images/brands/{slug}.*`.

Usage:
    python manage.py download_brand_logos                  # все featured-бренды
    python manage.py download_brand_logos --slug daichi    # один бренд
    python manage.py download_brand_logos --all-brands     # все, не только featured
"""
import mimetypes
import os

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Brand


_CONTENT_TYPE_TO_EXT = {
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/webp': '.webp',
    'image/svg+xml': '.svg',
    'image/gif': '.gif',
}


def _ext_from_response(resp, fallback_url):
    """Определяет расширение по Content-Type или по URL."""
    ctype = (resp.headers.get('Content-Type') or '').split(';')[0].strip().lower()
    if ctype in _CONTENT_TYPE_TO_EXT:
        return _CONTENT_TYPE_TO_EXT[ctype]
    guess = mimetypes.guess_extension(ctype) if ctype else None
    if guess:
        return guess if guess != '.jpe' else '.jpg'
    url_ext = os.path.splitext(fallback_url.split('?')[0])[1].lower()
    if url_ext in {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif'}:
        return '.jpg' if url_ext == '.jpeg' else url_ext
    return '.png'


class Command(BaseCommand):
    help = 'Скачивает логотипы featured-брендов в static/images/brands/'

    def add_arguments(self, parser):
        parser.add_argument('--slug', type=str, default='',
                            help='Скачать только один бренд по slug')
        parser.add_argument('--all-brands', action='store_true',
                            help='Все бренды (не только featured_in_quiz=True)')

    def handle(self, *args, **opts):
        out_dir = os.path.join(settings.BASE_DIR, 'static', 'images', 'brands')
        os.makedirs(out_dir, exist_ok=True)

        qs = Brand.objects.exclude(logo_url='')
        if opts['slug']:
            qs = qs.filter(slug=opts['slug'])
        elif not opts['all_brands']:
            qs = qs.filter(featured_in_quiz=True)

        ok = skip = err = 0
        for brand in qs.order_by('order', 'title'):
            try:
                resp = requests.get(brand.logo_url, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as exc:
                err += 1
                self.stderr.write(f'ERR {brand.slug}: {exc}')
                continue

            ext = _ext_from_response(resp, brand.logo_url)
            path = os.path.join(out_dir, f'{brand.slug}{ext}')
            with open(path, 'wb') as f:
                f.write(resp.content)
            ok += 1
            self.stdout.write(f'OK  {brand.slug}{ext} ({len(resp.content)} bytes)')

        self.stdout.write(self.style.SUCCESS(
            f'Готово: {ok} скачано, {err} ошибок, пропущено без logo_url: {skip}'
        ))
