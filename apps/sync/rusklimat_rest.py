"""REST API клиент для internet-partner.rusklimat.com.

Заменяет старый scraping b2b.rusklimat.com (login 403 на VPS).
Документация: https://internet-partner.rusklimat.com/swagger/v1/swagger.json
Локальная копия описания: https://b2b.rusklimat.com/personal/internet_partner/catalog_api/

Endpoints:
  GET  /api/v1/InternetPartner/{partnerId}/requestKey
  GET  /api/v1/InternetPartner/categories/{requestKey}
  GET  /api/v1/InternetPartner/properties/{requestKey}
  GET  /api/v1/InternetPartner/units
  POST /api/v{1|2|3}/InternetPartner/{partnerId}/products/{requestKey}

Авторизация: JWT в Authorization header. JWT валиден ~сутки, хранится в
RUSKLIMAT_JWT_TOKEN в .env. Auto-refresh пока не реализован (требует отдельных
API-учётных данных; phone+password из user-логина отдают «Invalid user/password»
на /api/v1/auth/jwt/). При 401 — клиент бросает понятную ошибку.
"""
import logging
import re
import time

import requests
from django.conf import settings
from django.db import transaction

from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.stock.models import Stock

logger = logging.getLogger(__name__)

_RK_BASE = 'https://internet-partner.rusklimat.com'
RUSKLIMAT_SOURCE = 'rusklimat'

# Соответствие master-категорий Rusklimat (по regex по name).
_AC_CATEGORY_RE = re.compile(
    r'кондицион|сплит.?систем|мульти.?сплит|мобильн\w*\s+кондицион',
    re.IGNORECASE,
)


class RusklimatJWTExpired(RuntimeError):
    pass


class RusklimatRestClient:
    """REST-клиент internet-partner.rusklimat.com.

    Кэширует requestKey на ~55 секунд (отдаётся с expire ~60 сек).
    """

    def __init__(self):
        self.jwt = settings.RUSKLIMAT_JWT_TOKEN
        self.guid = settings.RUSKLIMAT_CONTRACTOR_GUID
        if not self.jwt:
            raise RuntimeError('RUSKLIMAT_JWT_TOKEN is not set')
        if not self.guid:
            raise RuntimeError('RUSKLIMAT_CONTRACTOR_GUID is not set')
        self._request_key = None
        self._request_key_until = 0.0
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': self.jwt,
            'Accept': 'application/json',
        })

    def _check(self, response, where):
        if response.status_code == 401:
            raise RusklimatJWTExpired(
                f'Rusklimat 401 на {where}. JWT истёк или невалиден — '
                f'обновите RUSKLIMAT_JWT_TOKEN в /opt/oasis/.env.'
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f'Rusklimat {response.status_code} на {where}: {response.text[:200]}'
            )

    def request_key(self, force=False):
        now = time.time()
        if not force and self._request_key and self._request_key_until > now + 3:
            return self._request_key
        url = f'{_RK_BASE}/api/v1/InternetPartner/{self.guid}/requestKey'
        r = self._session.get(url, timeout=30)
        self._check(r, 'requestKey')
        data = r.json()
        self._request_key = data['requestKey']
        self._request_key_until = now + 55  # запас от expire ~60 сек
        return self._request_key

    def get_units(self):
        url = f'{_RK_BASE}/api/v1/InternetPartner/units'
        r = self._session.get(url, timeout=60)
        self._check(r, '/units')
        return r.json().get('data') or []

    def get_categories(self):
        key = self.request_key()
        url = f'{_RK_BASE}/api/v1/InternetPartner/categories/{key}'
        r = self._session.get(url, timeout=120)
        self._check(r, '/categories')
        return r.json().get('data') or []

    def get_properties(self):
        key = self.request_key()
        url = f'{_RK_BASE}/api/v1/InternetPartner/properties/{key}'
        r = self._session.get(url, timeout=120)
        self._check(r, '/properties')
        return r.json().get('data') or []

    def get_products(self, *, page=1, page_size=500, version=2,
                     category_ids=None, sort=None):
        key = self.request_key()
        url = (
            f'{_RK_BASE}/api/v{version}/InternetPartner/{self.guid}'
            f'/products/{key}?pageSize={page_size}&page={page}'
        )
        body = {'filter': {}, 'sort': sort or {'nsCode': 'asc'}}
        if category_ids:
            body['filter']['categoryIds'] = list(category_ids)
        r = self._session.post(
            url,
            json=body,
            headers={'Content-Type': 'application/json'},
            timeout=180,
        )
        self._check(r, f'/products page={page}')
        return r.json()


# === Sync helpers ==========================================================


def _find_ac_categories(client):
    """UUID категорий Rusklimat с AC-товарами (по name regex)."""
    cats = client.get_categories()
    ids = set()
    for cat in cats:
        name = (cat.get('name') or '').strip()
        if _AC_CATEGORY_RE.search(name):
            ids.add(cat['id'])
    logger.info('Rusklimat REST: %d AC-категорий из %d', len(ids), len(cats))
    return ids


def _master_category_for(name):
    """Маппинг Rusklimat-name в нашу master-Category."""
    n = name.lower()
    if 'мобильн' in n:
        return Category.objects.filter(breez_id=10).first()
    if 'мульти' in n or 'мульти.?сплит' in n:
        return Category.objects.filter(breez_id=9).first()
    if 'полупромышл' in n or 'канальн' in n or 'кассетн' in n:
        return Category.objects.filter(title__iexact='Полупромышленные кондиционеры').first()
    # default: бытовые сплит-системы
    return Category.objects.filter(breez_id=2).first()


def _build_slug(brand_title, vendor_code, ns_code, slug_cache):
    from django.utils.text import slugify
    parts = []
    if brand_title:
        parts.append(slugify(brand_title, allow_unicode=True))
    if vendor_code:
        parts.append(slugify(vendor_code, allow_unicode=True))
    if ns_code:
        parts.append(ns_code)
    base = '-'.join(p for p in parts if p)[:480] or f'rk-{ns_code}'
    slug = base
    i = 1
    while slug in slug_cache:
        i += 1
        slug = f'{base}-{i}'
    slug_cache.add(slug)
    return slug


def _get_or_create_brand(title, cache):
    from django.utils.text import slugify
    if not title:
        return None
    if title in cache:
        return cache[title]
    brand = Brand.objects.filter(title__iexact=title).first()
    if not brand:
        slug = slugify(title, allow_unicode=True) or f'brand-{title[:30]}'
        if Brand.objects.filter(slug=slug).exists():
            slug = f'{slug}-rk'
        brand = Brand.objects.create(title=title, slug=slug, breez_id=None)
    cache[title] = brand
    return brand


def _sync_images(product, picture_urls):
    if not picture_urls:
        return
    product.images.all().delete()
    ProductImage.objects.bulk_create([
        ProductImage(product=product, url=url, order=i)
        for i, url in enumerate(picture_urls)
        if isinstance(url, str) and url.startswith('http')
    ])


def _sync_stock(product, remains):
    """remains = {'total': '0', 'warehouses': {...}}."""
    if not isinstance(remains, dict):
        return
    try:
        qty = int(remains.get('total') or 0)
    except (TypeError, ValueError):
        qty = 0
    warehouses = remains.get('warehouses') or {}
    warehouse_name = ''
    if isinstance(warehouses, dict) and warehouses:
        warehouse_name = ', '.join(str(k) for k in list(warehouses.keys())[:3])
    Stock.objects.update_or_create(
        product=product,
        defaults={'quantity': qty, 'warehouse': warehouse_name[:255], 'price_base': product.price_wholesale},
    )


def sync_rusklimat_rest(*, max_pages=None):
    """Полная синхронизация каталога Rusklimat через REST API.

    Качаем только товары AC-категорий, обновляем Product/Image/Stock.
    TechSpec/ProductTech синкаем отдельной командой (нужна модель TechSpec
    с поддержкой UUID, что пока не сделано).
    """
    client = RusklimatRestClient()

    ac_ids = _find_ac_categories(client)
    if not ac_ids:
        logger.warning('AC-категорий не найдено в Rusklimat REST')
        return {'created': 0, 'updated': 0, 'pages': 0}

    brand_cache = {}
    slug_cache = set(Product.objects.values_list('slug', flat=True))
    seen_ns = set()
    created = updated = imgs_synced = stock_synced = 0
    page = 1
    page_size = 500

    while True:
        if max_pages and page > max_pages:
            break
        try:
            resp = client.get_products(
                page=page, page_size=page_size, version=2, category_ids=ac_ids,
            )
        except RusklimatJWTExpired:
            raise
        except Exception as exc:
            logger.error('Rusklimat /products page=%d failed: %s', page, exc)
            break

        items = resp.get('data') or []
        total = resp.get('totalCount') or 0
        logger.info('Rusklimat REST page %d: %d items (total %d)', page, len(items), total)
        if not items:
            break

        with transaction.atomic():
            for p in items:
                ns_code = p.get('nsCode')
                if not ns_code:
                    continue
                seen_ns.add(ns_code)

                brand = _get_or_create_brand(p.get('brand'), brand_cache)
                cat = _master_category_for(p.get('categoryId', '') or '')
                vendor_code = (p.get('vendorCode') or '').strip()
                name = (p.get('name') or vendor_code or ns_code).strip()
                description = p.get('description') or ''
                ric = p.get('internetPrice')
                wholesale = p.get('clientPrice') or p.get('price')

                # Нормализуем nc_code как и старый scraper: «НС-XXXXX»
                nc_code = ns_code if ns_code.startswith('НС-') else f'НС-{ns_code}'

                existing = Product.objects.filter(nc_code=nc_code).first()
                if existing:
                    existing.brand = brand or existing.brand
                    existing.category = cat or existing.category
                    existing.articul = vendor_code or existing.articul
                    existing.title = name or existing.title
                    existing.description = description
                    existing.price_wholesale = wholesale
                    existing.ric = ric
                    existing.source = RUSKLIMAT_SOURCE
                    existing.is_active = True
                    existing.save()
                    product = existing
                    updated += 1
                else:
                    slug = _build_slug(p.get('brand', ''), vendor_code, nc_code, slug_cache)
                    product = Product.objects.create(
                        nc_code=nc_code,
                        articul=vendor_code,
                        category=cat,
                        brand=brand,
                        title=name,
                        slug=slug,
                        description=description,
                        price_wholesale=wholesale,
                        ric=ric,
                        ric_currency='RUB',
                        rusklimat_guid=p.get('id') or '',
                        source=RUSKLIMAT_SOURCE,
                        is_active=True,
                    )
                    created += 1

                pics = p.get('pictures') or []
                if pics:
                    _sync_images(product, pics)
                    imgs_synced += 1

                remains = p.get('remains') or {}
                if remains:
                    _sync_stock(product, remains)
                    stock_synced += 1

        if len(items) < page_size:
            break
        page += 1

    # Деактивация Rusklimat-товаров, которые исчезли из API.
    deactivated = (
        Product.objects.filter(source=RUSKLIMAT_SOURCE)
        .exclude(nc_code__in={
            (ns if ns.startswith('НС-') else f'НС-{ns}') for ns in seen_ns
        })
        .update(is_active=False)
    )

    summary = {
        'created': created,
        'updated': updated,
        'pages': page,
        'imgs_synced': imgs_synced,
        'stock_synced': stock_synced,
        'deactivated': deactivated,
    }
    logger.info('Rusklimat REST sync: %s', summary)
    return summary
