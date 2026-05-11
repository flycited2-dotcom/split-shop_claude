import csv
import logging
import os
import re
import tempfile
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Brand, Category, Product, ProductImage

logger = logging.getLogger(__name__)

_BASE_URL = 'https://b2b.rusklimat.com'
_CSV_URL = (
    _BASE_URL
    + '/personal/internet_partner/download.php'
    '?filename=catalog.csv&dirload=/personalupload/unauthorized/'
)

_AC_RE = re.compile(
    r'сплит|split|кондиционер|мультисплит|инвертор|полупромышленн|мобильн|он.офф',
    re.I | re.UNICODE,
)
_GUID_RE = re.compile(
    r'rkcdn\.ru/products/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/',
    re.I,
)
_PRICE_RE = re.compile(r'[\d]+[.,][\d]+|[\d]+')


def _extract_guid(image_field):
    m = _GUID_RE.search(image_field or '')
    return m.group(1) if m else ''


def _parse_price(price_str):
    if not price_str:
        return None
    clean = (price_str or '').replace('\xa0', '').replace(' ', '').replace(',', '.')
    m = _PRICE_RE.search(clean)
    if m:
        try:
            return Decimal(m.group())
        except InvalidOperation:
            pass
    return None


def _make_unique_slug(model, base, exclude_pk=None):
    slug = base[:490]
    qs = model.objects.filter(slug=slug)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if not qs.exists():
        return slug
    slug = f'{base[:480]}-rk'
    if not model.objects.filter(slug=slug).exclude(pk=exclude_pk or 0).exists():
        return slug
    import hashlib
    suffix = hashlib.md5(base.encode()).hexdigest()[:6]
    return f'{base[:480]}-{suffix}'


def _get_or_create_brand(title, cache):
    if not title:
        return None
    if title in cache:
        return cache[title]
    brand = Brand.objects.filter(title__iexact=title).first()
    if not brand:
        slug = _make_unique_slug(Brand, slugify(title, allow_unicode=True) or 'brand')
        brand = Brand.objects.create(title=title, slug=slug, breez_id=None)
        logger.debug('Created Rusklimat brand: %s', title)
    cache[title] = brand
    return brand


def _get_or_create_category(path, cache):
    if not path:
        return None
    if path in cache:
        return cache[path]

    parts = [p.strip() for p in path.split(' - ') if p.strip()]
    leaf = parts[-1] if parts else path
    parent_title = parts[-2] if len(parts) >= 2 else None

    cat = Category.objects.filter(title__iexact=leaf).first()
    if not cat:
        parent = None
        if parent_title:
            parent = Category.objects.filter(title__iexact=parent_title).first()
            if not parent:
                p_slug = _make_unique_slug(
                    Category,
                    slugify(parent_title, allow_unicode=True) or 'category',
                )
                parent = Category.objects.create(
                    title=parent_title, slug=p_slug,
                    breez_id=None, sync_enabled=True,
                )
        slug = _make_unique_slug(Category, slugify(leaf, allow_unicode=True) or 'category')
        cat = Category.objects.create(
            title=leaf, slug=slug,
            breez_id=None, parent=parent, sync_enabled=True,
        )
        logger.debug('Created Rusklimat category: %s', leaf)

    cache[path] = cat
    return cat


class RusklimatCatalogSync:
    """
    Downloads full product catalog CSV from b2b.rusklimat.com and imports
    AC/split-system products into the database.
    """

    def __init__(self):
        self.login_phone = getattr(settings, 'RUSKLIMAT_LOGIN', '')
        self.password = getattr(settings, 'RUSKLIMAT_PASSWORD', '')
        self.contr_guid = getattr(settings, 'RUSKLIMAT_CONTRACTOR_GUID', '')
        self._session = requests.Session()
        self._session.headers['User-Agent'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )

    def login(self):
        if not self.login_phone or not self.password:
            logger.error('RUSKLIMAT_LOGIN / RUSKLIMAT_PASSWORD not set')
            return False
        resp = self._session.get(_BASE_URL + '/auth/', timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        tag = soup.find('input', {'name': 'sessionId'})
        sessid = tag['value'] if tag else ''

        resp = self._session.post(
            _BASE_URL + '/api/v1/user/signIn/',
            data={'sessionId': sessid, 'phone': self.login_phone, 'password': self.password},
            timeout=15,
        )
        data = resp.json()
        if data.get('code') != 200:
            logger.error('Rusklimat signIn failed: %s', data)
            return False

        guid = self._session.cookies.get('RUSKLIMAT_CONTR_GUID')
        if guid:
            self.contr_guid = guid
        logger.info('Rusklimat login OK, contractor=%s', self.contr_guid)
        return True

    def _download_csv(self):
        """Download catalog CSV to a temp file. Returns temp file path."""
        logger.info('Downloading Rusklimat catalog CSV (~206 MB)...')
        resp = self._session.get(_CSV_URL, timeout=300, stream=True)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        for chunk in resp.iter_content(chunk_size=65536):
            tmp.write(chunk)
        tmp.close()
        size_mb = os.path.getsize(tmp.name) / 1024 / 1024
        logger.info('Downloaded %.1f MB to %s', size_mb, tmp.name)
        return tmp.name

    def sync_catalog(self):
        """
        Download CSV, filter AC rows, create/update products.
        Returns stats dict.
        """
        if not self.login():
            return {'error': 'login failed', 'created': 0, 'updated': 0, 'skipped': 0}

        tmp_path = self._download_csv()
        brand_cache = {}
        cat_cache = {}
        created = updated = skipped = 0

        try:
            with open(tmp_path, encoding='utf-8-sig', newline='', errors='replace') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    cat_path = (row.get('Название категории') or '').strip()
                    if not _AC_RE.search(cat_path):
                        skipped += 1
                        continue

                    nc_code = (row.get('НС-код') or '').strip()
                    if not nc_code:
                        skipped += 1
                        continue

                    brand = _get_or_create_brand((row.get('Бренд') or '').strip(), brand_cache)
                    category = _get_or_create_category(cat_path, cat_cache)

                    image_field = (row.get('Изображение') or '').strip()
                    rusklimat_guid = _extract_guid(image_field)
                    image_urls = [
                        u.strip() for u in image_field.split(',')
                        if u.strip().startswith('http')
                    ]

                    title = (row.get('Наименование') or '').strip()
                    articul = (row.get('Артикул') or '').strip()
                    price = _parse_price(row.get('Цена') or '')
                    description = (row.get('Статья') or '').strip()
                    manual_field = (row.get('Инструкции') or '').strip()
                    manual_url = manual_field.split(',')[0].strip() if manual_field else ''

                    brand_part = slugify(brand.title, allow_unicode=True) if brand else ''
                    if brand_part and articul:
                        slug_base = f'{brand_part}-{slugify(articul, allow_unicode=True)}-{nc_code}'
                    else:
                        slug_base = f'{slugify(title, allow_unicode=True)}-{nc_code}'

                    defaults = {
                        'articul': articul,
                        'title': title or articul or nc_code,
                        'brand': brand,
                        'category': category,
                        'description': description,
                        'manual_url': manual_url,
                        'price_wholesale': price,
                        'ric': price,
                        'source': 'rusklimat',
                        'is_active': True,
                    }
                    if rusklimat_guid:
                        defaults['rusklimat_guid'] = rusklimat_guid

                    # Slug: only set on create to avoid changing existing URLs
                    existing = Product.objects.filter(nc_code=nc_code).first()
                    if not existing:
                        defaults['slug'] = _make_unique_slug(Product, slug_base)

                    with transaction.atomic():
                        obj, is_new = Product.objects.update_or_create(
                            nc_code=nc_code,
                            defaults=defaults,
                        )
                        if image_urls:
                            obj.images.all().delete()
                            ProductImage.objects.bulk_create([
                                ProductImage(product=obj, url=url, order=i)
                                for i, url in enumerate(image_urls[:10])
                            ])

                    if is_new:
                        created += 1
                    else:
                        updated += 1

        finally:
            os.unlink(tmp_path)

        logger.info(
            'Rusklimat catalog sync done: created=%d updated=%d skipped=%d',
            created, updated, skipped,
        )
        return {'created': created, 'updated': updated, 'skipped': skipped}
