import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Brand, Category, Product
from apps.stock.models import Stock
from apps.sync.daichi_client import DaichiClient

logger = logging.getLogger(__name__)

DAICHI_SOURCE = 'daichi'

# В .env / settings DAICHI_STORE_ID может быть 'default' (партнёр одного склада)
# или конкретный XML_ID (если несколько складов).

# Карта группы товара Daichi → title нашей мастер-категории.
# Если нашей категории с таким title нет — товар пропускается (sync_enabled управляется в admin).
_GOODGROUP_TO_TITLE = {
    'Бытовые сплит-системы': 'Бытовые сплит-системы',
}

# В каталог попадают только готовые комплекты (внутренний + наружный блок продаются вместе).
# Отдельные внутренние/наружные блоки скрываем — конечному покупателю не нужны.
_ALLOWED_GOODTYPES = {'Комплект', 'Сплит-система'}

# Карта валют Daichi → код в нашей БД.
_CURRENCY_MAP = {
    'RUR': 'RUB',
    'RUB': 'RUB',
    'USD': 'USD',
    'EUR': 'EUR',
    'KZT': 'KZT',
}


def _to_decimal(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _get_or_create_brand(title):
    if not title:
        return None
    brand = Brand.objects.filter(title__iexact=title).first()
    if brand:
        return brand
    slug = slugify(title, allow_unicode=True) or f'brand-daichi-{title[:30]}'
    if Brand.objects.filter(slug=slug).exists():
        slug = f'{slug}-daichi'
    return Brand.objects.create(title=title, slug=slug)


def _resolve_category(params):
    """Map Daichi PARAMS to our master Category by title.

    Returns Category or None. None means «нет нашей категории под этот goodgroup —
    товар не показываем».
    """
    goodgroup = (params.get('ATTR_L_GOODGROUP') or '').strip()
    target_title = _GOODGROUP_TO_TITLE.get(goodgroup)
    if not target_title:
        return None
    return Category.objects.filter(title__iexact=target_title, sync_enabled=True).first()


def _is_kit(params):
    goodtype = (params.get('ATTR_L_GOODTYPE') or '').strip()
    return goodtype in _ALLOWED_GOODTYPES


def _extract_prices(prices_obj):
    """Daichi PRICES — это dict {XML_ID-key: {XML_ID, NAME, PRICE, CURRENCY}}.

    BASE = розничная партнёрская (со скидкой), это наш price_wholesale.
    mprc = МПРЦ (рекомендуемая розничная), это наш ric для показа клиенту.
    """
    if not isinstance(prices_obj, dict):
        return None, None, 'RUB'

    base_price = ric_price = None
    currency = 'RUB'

    for entry in prices_obj.values():
        if not isinstance(entry, dict):
            continue
        xml_id = entry.get('XML_ID') or ''
        name = entry.get('NAME') or ''
        price = _to_decimal(entry.get('PRICE'))
        cur = _CURRENCY_MAP.get(entry.get('CURRENCY', 'RUR'), 'RUB')

        if xml_id == 'BASE' or name == 'Розничная цена':
            base_price = price
            currency = cur
        elif name == 'МПРЦ' or 'mprc' in (xml_id or '').lower():
            ric_price = price

    return base_price, ric_price, currency


def _build_slug(brand, articul, xml_id):
    brand_part = slugify(brand.title, allow_unicode=True) if brand else ''
    art_part = slugify(articul, allow_unicode=True) if articul else ''
    short_uuid = (xml_id or '').replace('-', '')[:12]
    parts = [p for p in (brand_part, art_part, short_uuid) if p]
    slug = '-'.join(parts) or f'daichi-{short_uuid}'
    return slug[:500]


def sync_catalog():
    """Pull /products/get for the configured store, upsert Products + Stock."""
    from django.conf import settings as dj_settings

    client = DaichiClient()
    if not client.access_token:
        logger.warning('Daichi sync: DAICHI_ACCESS_TOKEN not configured')
        return {'created': 0, 'updated': 0, 'skipped': 0, 'deactivated': 0}

    store_id = dj_settings.DAICHI_STORE_ID
    products = client.get_products(store_id=store_id)
    if not products:
        logger.warning('Daichi sync: empty /products/get response')
        return {'created': 0, 'updated': 0, 'skipped': 0, 'deactivated': 0}

    seen_xml_ids = set()
    created = updated = skipped_no_category = skipped_not_kit = 0

    with transaction.atomic():
        for entry in products.values():
            if not isinstance(entry, dict):
                continue

            xml_id = entry.get('XML_ID')
            if not xml_id:
                continue

            params = entry.get('PARAMS') or {}
            # API в реальности отдаёт ключи с двоеточием ("PARAMS:") — пробуем оба
            if not params:
                params = entry.get('PARAMS:') or {}

            if not _is_kit(params):
                skipped_not_kit += 1
                continue

            category = _resolve_category(params)
            if not category:
                skipped_no_category += 1
                continue

            brand = _get_or_create_brand(params.get('BRAND'))

            articul = entry.get('NAME') or ''
            title = (params.get('ATTR_RUS_NAME_AX') or articul or xml_id).strip()
            series = (params.get('ATTR_L_SERIA') or '').strip()

            prices_obj = entry.get('PRICES') or entry.get('PRICES:') or {}
            wholesale, ric, currency = _extract_prices(prices_obj)

            slug = _build_slug(brand, articul, xml_id)
            # уникальность slug по таблице (на случай коллизии с Breeze/Rusklimat)
            base_slug = slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(nc_code=xml_id).exists():
                counter += 1
                slug = f'{base_slug}-{counter}'

            product, is_new = Product.objects.update_or_create(
                nc_code=xml_id,
                defaults={
                    'articul': articul,
                    'category': category,
                    'brand': brand,
                    'series': series,
                    'title': title,
                    'slug': slug,
                    'price_wholesale': wholesale,
                    'ric': ric,
                    'ric_currency': currency,
                    'source': DAICHI_SOURCE,
                    'is_active': True,
                },
            )
            seen_xml_ids.add(xml_id)

            store = entry.get('STORE') or entry.get('STORE:') or {}
            if isinstance(store, dict):
                qty = store.get('STORE_AMOUNT')
                warehouse = store.get('NAME') or ''
                try:
                    qty_int = int(qty) if qty is not None else 0
                except (TypeError, ValueError):
                    qty_int = 0
                Stock.objects.update_or_create(
                    product=product,
                    defaults={
                        'quantity': qty_int,
                        'warehouse': warehouse,
                        'price_base': wholesale,
                    },
                )

            if is_new:
                created += 1
            else:
                updated += 1

        deactivated = (
            Product.objects.filter(source=DAICHI_SOURCE)
            .exclude(nc_code__in=seen_xml_ids)
            .update(is_active=False)
        )

    logger.info(
        'Daichi sync: created=%d updated=%d skipped_not_kit=%d skipped_no_cat=%d deactivated=%d',
        created, updated, skipped_not_kit, skipped_no_category, deactivated,
    )
    return {
        'created': created,
        'updated': updated,
        'skipped_not_kit': skipped_not_kit,
        'skipped_no_category': skipped_no_category,
        'deactivated': deactivated,
    }
