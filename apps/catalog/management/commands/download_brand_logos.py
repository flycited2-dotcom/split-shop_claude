"""Скачивает логотипы брендов в static/images/brands/{slug}.{ext}.

Источник URL: либо `Brand.logo_url` из БД, либо публичное API
`b2b.rusklimat.com/api/v1/brands/` (357 брендов с лого на rkcdn.ru, по
name matching case-insensitive). API не требует авторизации.

Usage:
    python manage.py download_brand_logos                # featured-бренды, источник = БД
    python manage.py download_brand_logos --slug daichi  # один бренд
    python manage.py download_brand_logos --all-brands   # все бренды из БД
    python manage.py download_brand_logos --from-rusklimat  # подтянуть logo_url
                                                            # с rusklimat API
                                                            # для featured-брендов
                                                            # без logo_url, и сразу качать
    python manage.py download_brand_logos --from-rusklimat --all-brands
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

_RUSKLIMAT_BRANDS_URL = 'https://b2b.rusklimat.com/api/v1/brands/?limit=200&page={page}'


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


def _fetch_rusklimat_brand_index():
    """Скачивает 357 брендов с b2b.rusklimat.com и возвращает {name_lower: image_url}."""
    index = {}
    for page in (1, 2):
        resp = requests.get(_RUSKLIMAT_BRANDS_URL.format(page=page), timeout=30)
        resp.raise_for_status()
        for item in resp.json().get('data', {}).get('items') or []:
            name = (item.get('name') or '').strip()
            image = (item.get('image') or '').strip()
            if name and image:
                index[name.lower()] = image
    return index


class Command(BaseCommand):
    help = 'Скачивает логотипы брендов в static/images/brands/'

    def add_arguments(self, parser):
        parser.add_argument('--slug', type=str, default='',
                            help='Скачать только один бренд по slug')
        parser.add_argument('--all-brands', action='store_true',
                            help='Все бренды (не только featured_in_quiz=True)')
        parser.add_argument('--from-rusklimat', action='store_true',
                            help='Перед скачиванием подтянуть Brand.logo_url из '
                                 'b2b.rusklimat.com/api/v1/brands/ для брендов с пустым logo_url')

    def handle(self, *args, **opts):
        out_dir = os.path.join(settings.BASE_DIR, 'static', 'images', 'brands')
        os.makedirs(out_dir, exist_ok=True)

        # Стартовый queryset — featured-бренды или все.
        base_qs = Brand.objects.all()
        if opts['slug']:
            base_qs = base_qs.filter(slug=opts['slug'])
        elif not opts['all_brands']:
            base_qs = base_qs.filter(featured_in_quiz=True)

        # Шаг 1 (опционально): заполнить logo_url из rusklimat API для тех,
        # у кого пусто. Matching: точное → substring (поймает «Mitsubishi» =
        # «MITSUBISHI ELECTRIC»).
        if opts['from_rusklimat']:
            self.stdout.write('Тяну rusklimat brand index...')
            index = _fetch_rusklimat_brand_index()
            self.stdout.write(f'  получено {len(index)} брендов с лого')
            updated = 0
            for brand in base_qs.filter(logo_url=''):
                key = brand.title.lower()
                api_url = index.get(key)
                if not api_url:
                    # fuzzy: либо наш title содержится в API name, либо наоборот
                    for api_name, url in index.items():
                        if key in api_name or api_name in key:
                            api_url = url
                            break
                if api_url:
                    brand.logo_url = api_url
                    brand.save(update_fields=['logo_url'])
                    updated += 1
                    self.stdout.write(f'  → {brand.slug}: {api_url}')
            self.stdout.write(self.style.SUCCESS(
                f'logo_url обновлён у {updated} брендов.'
            ))

        # Шаг 2: скачивание.
        ok = err = skipped = 0
        for brand in base_qs.exclude(logo_url='').order_by('order', 'title'):
            try:
                resp = requests.get(brand.logo_url, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as exc:
                err += 1
                self.stderr.write(f'ERR {brand.slug}: {exc}')
                continue

            ctype = (resp.headers.get('Content-Type') or '').split(';')[0].strip().lower()
            if not ctype.startswith('image/'):
                # Сервер вернул HTML/JSON — обычно 404-страницу. Не сохраняем.
                skipped += 1
                self.stderr.write(
                    f'SKIP {brand.slug}: not an image (Content-Type={ctype}, url={brand.logo_url})'
                )
                continue

            ext = _ext_from_response(resp, brand.logo_url)
            path = os.path.join(out_dir, f'{brand.slug}{ext}')
            with open(path, 'wb') as f:
                f.write(resp.content)
            ok += 1
            self.stdout.write(f'OK  {brand.slug}{ext} ({len(resp.content)} bytes)')

        self.stdout.write(self.style.SUCCESS(
            f'Готово: {ok} скачано, {skipped} пропущено (не image), {err} ошибок.'
        ))
