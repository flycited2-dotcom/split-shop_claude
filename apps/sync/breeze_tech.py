"""Sync технических характеристик товаров Breez (api.breez.ru/v1/tech/).

Bryeez API отдаёт характеристики только через `/v1/tech/?id=N`, где N —
внутренний id товара (НЕ nc_code). Поэтому шаги:
1. Загрузить `/v1/products/` → mapping nc_code → breez_id.
2. Для каждого активного Бриз-товара GET /tech/?id=breez_id → распарсить
   поле `techs` (dict id_char → spec-объект с `value`).
3. Создать/обновить TechSpec по breez_id и записать ProductTech.

Объём: ~1137 HTTP-запросов, ~3 минуты с rate-limit 0.15с.
"""
import logging
import time

import requests
from django.conf import settings
from django.db import transaction

from apps.catalog.models import Product, TechSpec, ProductTech

logger = logging.getLogger(__name__)

BREEZ_SOURCE = 'breeze'
_REQUEST_DELAY = 0.15  # сек между запросами /tech/?id=


def _request(path, params=None, timeout=60):
    url = settings.BREEZ_BASE_URL.rstrip('/') + path
    headers = {
        'Authorization': settings.BREEZ_AUTH_HEADER,
        'Accept': 'application/json',
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and 'error' in data:
            logger.debug('Breez %s %s → error=%s', path, params, data['error'])
            return None
        return data
    except Exception as exc:
        logger.error('Breez %s %s failed: %s', path, params, exc)
        return None


def _fetch_nc_to_id():
    """{nc_code: breez_id} из /v1/products/."""
    data = _request('/products/', timeout=120)
    if not isinstance(data, dict):
        return {}
    mapping = {}
    for breez_id, prod in data.items():
        if isinstance(prod, dict) and prod.get('nc'):
            try:
                mapping[prod['nc']] = int(breez_id)
            except (TypeError, ValueError):
                continue
    return mapping


def _upsert_spec(id_char, tech_data, cache):
    """update_or_create TechSpec по breez_id (id_char)."""
    if id_char in cache:
        return cache[id_char]
    title = (tech_data.get('title') or '').strip()
    if not title:
        return None
    try:
        order = int(tech_data.get('order') or 0)
    except (TypeError, ValueError):
        order = 0
    spec, _ = TechSpec.objects.update_or_create(
        breez_id=id_char,
        defaults={
            'title': title,
            'unit': (tech_data.get('unit') or '').strip(),
            'data_type': (tech_data.get('type') or '').strip(),
            'group': (tech_data.get('group') or '').strip(),
            'order': order,
            'is_filter': str(tech_data.get('filter') or '0') == '1',
        },
    )
    cache[id_char] = spec
    return spec


def _sync_product_tech(product, breez_id, cache):
    """GET /tech/?id=breez_id, перезаписать ProductTech.
    Возвращает кол-во записанных пар или 0 если nothing."""
    data = _request('/tech/', params={'id': breez_id})
    if not isinstance(data, dict):
        return 0
    entry = data.get(str(breez_id)) or (next(iter(data.values()), None) if data else None)
    if not isinstance(entry, dict):
        return 0
    techs = entry.get('techs')
    if not isinstance(techs, dict) or not techs:
        return 0

    to_create = []
    seen = set()
    for spec_key, tech_data in techs.items():
        if not isinstance(tech_data, dict):
            continue
        try:
            id_char = int(tech_data.get('id_char') or spec_key)
        except (TypeError, ValueError):
            continue
        value = tech_data.get('value')
        if value is None or str(value).strip() == '':
            continue
        spec = _upsert_spec(id_char, tech_data, cache)
        if not spec or spec.pk in seen:
            continue
        seen.add(spec.pk)
        to_create.append(ProductTech(product=product, spec=spec, value=str(value).strip()))

    if not to_create:
        return 0
    with transaction.atomic():
        ProductTech.objects.filter(product=product).delete()
        ProductTech.objects.bulk_create(to_create)
    return len(to_create)


def sync_breez_tech():
    """Полный sync характеристик Бриз — все активные товары."""
    nc_to_id = _fetch_nc_to_id()
    logger.info('Breez nc→id mapping: %d entries', len(nc_to_id))
    if not nc_to_id:
        return {'total': 0, 'synced_products': 0, 'no_id': 0, 'no_techs': 0,
                'pt_total': 0, 'specs_total': 0}

    products = list(Product.objects.filter(source=BREEZ_SOURCE, is_active=True))
    total = len(products)
    cache = {}
    synced_products = 0
    no_id = 0
    no_techs = 0
    pt_total = 0

    for idx, product in enumerate(products, 1):
        breez_id = nc_to_id.get(product.nc_code)
        if not breez_id:
            no_id += 1
            continue
        count = _sync_product_tech(product, breez_id, cache)
        if count:
            pt_total += count
            synced_products += 1
        else:
            no_techs += 1
        if idx % 100 == 0:
            logger.info('Breez tech sync progress: %d/%d (synced=%d)',
                        idx, total, synced_products)
        time.sleep(_REQUEST_DELAY)

    logger.info(
        'Breez tech sync done: total=%d synced=%d no_id=%d no_techs=%d pt=%d specs=%d',
        total, synced_products, no_id, no_techs, pt_total, len(cache),
    )
    return {
        'total': total,
        'synced_products': synced_products,
        'no_id': no_id,
        'no_techs': no_techs,
        'pt_total': pt_total,
        'specs_total': len(cache),
    }
