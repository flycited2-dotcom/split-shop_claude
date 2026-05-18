import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Brand, Category, Product, ProductImage
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


def _fetch_all_productparams(client, page_size=500):
    """Собирает все productparams Daichi постранично. Возвращает dict XML_ID → pp_dict."""
    pp_map = {}
    page = 1
    while True:
        resp = client.get_productparams(page_size=page_size, page=page)
        data = resp.get('data') if isinstance(resp, dict) else None
        if not data:
            break
        for pp in data.values():
            xml = pp.get('XML_ID')
            if xml:
                pp_map[xml] = pp
        total = resp.get('total_count') or 0
        if page * page_size >= total:
            break
        page += 1
    logger.info('Daichi productparams: fetched %d items across %d pages', len(pp_map), page)
    return pp_map


def _sync_images(product, photo_urls):
    """Полностью перезаписывает картинки товара списком URL'ов из Daichi."""
    if not photo_urls:
        return
    # Простой replace — sync идёт пакетно, дубликаты нам не нужны.
    product.images.all().delete()
    ProductImage.objects.bulk_create([
        ProductImage(product=product, url=url, order=i)
        for i, url in enumerate(photo_urls)
        if isinstance(url, str) and url.startswith('http')
    ])


def _attr_value(pp_data, key):
    """Извлекает VALUE из структуры ATTR_* (dict {CODE,NAME,VALUE,GROUP})."""
    attr = pp_data.get(key)
    if isinstance(attr, dict):
        val = attr.get('VALUE')
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _build_description(pp_data, series, brand_title):
    """Синтезирует human-readable текст из структурированных ATTR_* Daichi.

    API не отдаёт готовое описание — собираем сами из ключевых характеристик.
    """
    intro_bits = []
    if brand_title and series:
        intro_bits.append(f'Сплит-система серии {series} от бренда {brand_title}.')
    elif series:
        intro_bits.append(f'Сплит-система серии {series}.')

    facts = []
    cool = _attr_value(pp_data, 'ATTR_CAPACITY_COOL') or _attr_value(pp_data, 'ATTR_CAP_COOL_NOM')
    if cool:
        facts.append(f'Мощность охлаждения {cool} кВт')

    noise_in = _attr_value(pp_data, 'ATTR_SOUND_PRESSURE_IU_COOL')
    noise_out = _attr_value(pp_data, 'ATTR_SOUND_PRESSURE_COOL')
    if noise_in or noise_out:
        parts = []
        if noise_in: parts.append(f'внутренний блок {noise_in} дБ')
        if noise_out: parts.append(f'наружный {noise_out} дБ')
        facts.append('уровень шума ' + ', '.join(parts))

    refr = _attr_value(pp_data, 'ATTR_L_REFR')
    if refr:
        facts.append(f'хладагент {refr}')

    color = _attr_value(pp_data, 'ATTR_L_COLOR')
    if color:
        facts.append(f'цвет {color.lower()}')

    dims = _attr_value(pp_data, 'ATTR_DIMENS')
    if dims:
        facts.append(f'габариты {dims}')

    weight = _attr_value(pp_data, 'ATTR_WEIGHT_NET')
    if weight:
        facts.append(f'вес {weight} кг')

    country = _attr_value(pp_data, 'ATTR_STRANA')
    if country:
        facts.append(f'страна производства — {country}')

    srok = _attr_value(pp_data, 'ATTR_SROK_EKSP')
    if srok:
        facts.append(f'срок эксплуатации {srok}')

    sections = []
    if intro_bits:
        sections.append(' '.join(intro_bits))
    if facts:
        sections.append('Характеристики: ' + '; '.join(facts) + '.')
    return '\n\n'.join(sections)


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

    # /products/get/ не отдаёт PHOTOES — они приходят только через /productparams/get/.
    # Тянем все productparams заранее (10 страниц по 500) и матчим по XML_ID.
    pp_map = _fetch_all_productparams(client)

    seen_xml_ids = set()
    created = updated = skipped_no_category = skipped_not_kit = images_synced = 0

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
            series = (params.get('ATTR_L_SERIA') or '').strip()
            # Title формата «Brand Articul Series». ATTR_RUS_NAME_AX часто
            # generic «Бытовой кондиционер» — оставляем только как fallback,
            # когда ни бренд, ни артикул, ни серия не дали внятной строки.
            brand_title = (brand.title if brand else '').strip()
            title_parts = [p for p in (brand_title, articul, series) if p]
            if title_parts:
                title = ' '.join(title_parts)
            else:
                title = (params.get('ATTR_RUS_NAME_AX') or xml_id).strip()

            prices_obj = entry.get('PRICES') or entry.get('PRICES:') or {}
            wholesale, ric, currency = _extract_prices(prices_obj)

            slug = _build_slug(brand, articul, xml_id)
            # уникальность slug по таблице (на случай коллизии с Breeze/Rusklimat)
            base_slug = slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(nc_code=xml_id).exists():
                counter += 1
                slug = f'{base_slug}-{counter}'

            pp = pp_map.get(xml_id)
            description = ''
            if pp:
                description = _build_description(
                    pp, series, brand.title if brand else ''
                )

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
                    'description': description,
                    'source': DAICHI_SOURCE,
                    'is_active': True,
                },
            )
            seen_xml_ids.add(xml_id)

            if pp:
                photos = pp.get('PHOTOES') or pp.get('PHOTOES:') or []
                if photos:
                    _sync_images(product, photos)
                    images_synced += 1

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
        'Daichi sync: created=%d updated=%d skipped_not_kit=%d skipped_no_cat=%d '
        'deactivated=%d images_synced=%d',
        created, updated, skipped_not_kit, skipped_no_category, deactivated, images_synced,
    )
    return {
        'created': created,
        'updated': updated,
        'skipped_not_kit': skipped_not_kit,
        'skipped_no_category': skipped_no_category,
        'deactivated': deactivated,
        'images_synced': images_synced,
    }
