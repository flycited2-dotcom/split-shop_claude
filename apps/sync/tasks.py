import logging
from celery import shared_task
from django.db import transaction
from django.utils.text import slugify

from apps.sync.client import BreezClient
from apps.sync.rusklimat_client import RusklimatClient
from apps.catalog.models import Category, Brand, Product, ProductImage
from apps.stock.models import Stock

logger = logging.getLogger(__name__)

def _is_ac_category(category, allowed_ids=None):
    """Return True if this category should be synced."""
    if category is None:
        return False
    if allowed_ids is not None:
        return category.id in allowed_ids
    return category.sync_enabled


def _get_client():
    return BreezClient()


@shared_task(name='sync.sync_categories')
def sync_categories():
    client = _get_client()
    data = client.get_categories()
    if not data:
        logger.warning("sync_categories: no data returned from API")
        return {'created': 0, 'updated': 0}

    created = updated = 0
    for item in data:
        item_id = int(item['id'])
        raw_slug = item.get('chpu') or slugify(item.get('title', ''), allow_unicode=True)
        slug = raw_slug or f"cat-{item_id}"
        if Category.objects.filter(slug=slug).exclude(breez_id=item_id).exists():
            slug = f"{slug}-{item_id}"
        _, is_new = Category.objects.update_or_create(
            breez_id=item_id,
            defaults={
                'title': item.get('title', ''),
                'slug': slug,
                'order': int(item.get('order', 0) or 0),
            }
        )
        if is_new:
            created += 1
        else:
            updated += 1

    # Second pass: wire up parent relationships
    for item in data:
        item_id = int(item['id'])
        parent_breez_id = item.get('level')
        if parent_breez_id and int(parent_breez_id) != 0:
            Category.objects.filter(breez_id=item_id).update(
                parent=Category.objects.filter(breez_id=int(parent_breez_id)).first()
            )

    logger.info("sync_categories: created=%d updated=%d", created, updated)
    return {'created': created, 'updated': updated}


@shared_task(name='sync.sync_brands')
def sync_brands():
    client = _get_client()
    data = client.get_brands()
    if not data:
        logger.warning("sync_brands: no data returned from API")
        return {'created': 0, 'updated': 0}

    created = updated = 0
    for item in data:
        item_id = int(item['id'])
        raw_slug = item.get('chpu') or slugify(item.get('title', ''), allow_unicode=True)
        slug = raw_slug or f"brand-{item_id}"
        # Ensure slug uniqueness across different breez_ids
        if Brand.objects.filter(slug=slug).exclude(breez_id=item_id).exists():
            slug = f"{slug}-{item_id}"
        _, is_new = Brand.objects.update_or_create(
            breez_id=item_id,
            defaults={
                'title': item.get('title', ''),
                'slug': slug,
                'logo_url': item.get('image', ''),
                'site_url': item.get('url', ''),
                'order': int(item.get('order', 0) or 0),
            }
        )
        if is_new:
            created += 1
        else:
            updated += 1

    logger.info("sync_brands: created=%d updated=%d", created, updated)
    return {'created': created, 'updated': updated}


@shared_task(name='sync.sync_products')
def sync_products(category_ids=None):
    """
    Sync products from Breeze.
    category_ids: list of Category PKs to sync (manual run). None = use sync_enabled flag.
    """
    client = _get_client()
    data = client.get_products()
    if not data:
        logger.warning("sync_products: no data returned from API")
        return {'created': 0, 'updated': 0, 'deactivated': 0}

    allowed_ids = set(category_ids) if category_ids else None
    nc_codes_seen = set()
    created = updated = skipped = 0

    with transaction.atomic():
        for item in data:
            nc = item.get('nc')
            if not nc:
                continue

            cat_id = item.get('category_id')
            category = Category.objects.filter(breez_id=int(cat_id)).first() \
                if cat_id else None

            if not _is_ac_category(category, allowed_ids):
                skipped += 1
                continue

            nc_codes_seen.add(nc)

            brand_id = item.get('brand')
            brand = Brand.objects.filter(breez_id=int(brand_id)).first() \
                if brand_id else None

            # price is a dict {"ric": "...", "ric_currency": "..."} or None
            price_data = item.get('price') or {}
            ric_val = price_data.get('ric') if isinstance(price_data, dict) else None
            ric_currency = price_data.get('ric_currency', 'RUB') if isinstance(price_data, dict) else 'RUB'

            articul = item.get('articul', '')
            title = item.get('title', '') or articul or nc

            brand_part = slugify(brand.title, allow_unicode=True) if brand else ''
            if brand_part and articul:
                slug = f"{brand_part}-{slugify(articul, allow_unicode=True)}-{nc}"
            else:
                slug = f"{slugify(title, allow_unicode=True)}-{nc}"
            slug = slug[:500] or f"product-{nc}"

            obj, is_new = Product.objects.update_or_create(
                nc_code=nc,
                defaults={
                    'articul': articul,
                    'category': category,
                    'brand': brand,
                    'series': item.get('series', ''),
                    'title': title,
                    'slug': slug,
                    'price_wholesale': ric_val or None,
                    'ric': ric_val or None,
                    'ric_currency': ric_currency,
                    'description': item.get('description', ''),
                    'booklet_url': item.get('booklet', ''),
                    'manual_url': item.get('manual', ''),
                    'video_youtube': item.get('video_youtube', ''),
                    'video_rutube': item.get('video_rutube', ''),
                    'is_active': True,
                }
            )
            if is_new:
                created += 1
            else:
                updated += 1

            # Sync images: always replace when API returns a list (even empty)
            images = item.get('images')
            if images is not None:
                obj.images.all().delete()
                if images:
                    ProductImage.objects.bulk_create([
                        ProductImage(product=obj, url=url, order=i)
                        for i, url in enumerate(images)
                    ])

        # Deactivate products not seen in this sync (includes non-AC products)
        deactivated = Product.objects.exclude(nc_code__in=nc_codes_seen).update(is_active=False)

    logger.info("sync_products: created=%d updated=%d deactivated=%d skipped(non-AC)=%d",
                created, updated, deactivated, skipped)
    return {'created': created, 'updated': updated, 'deactivated': deactivated, 'skipped': skipped}


@shared_task(name='sync.sync_stock')
def sync_stock():
    client = _get_client()
    data = client.get_stock()
    if not data:
        logger.warning("sync_stock: no data returned from API")
        return {'updated': 0}

    created = updated = 0
    for item in data:
        nc = item.get('nc') or item.get('nc_code')
        if not nc:
            continue
        product = Product.objects.filter(nc_code=nc).first()
        if not product:
            continue

        # stocks is a list of {stock: name, quantity: int}
        stocks_list = item.get('stocks') or []
        total_qty = sum(int(s.get('quantity', 0) or 0) for s in stocks_list if isinstance(s, dict))

        # price is a list [{base: ..., base_currency: ...}, {ric: ..., ...}]
        price_list = item.get('price') or []
        price_base = None
        if isinstance(price_list, list):
            for p in price_list:
                if isinstance(p, dict) and 'base' in p:
                    price_base = p['base']
                    break

        _, is_new = Stock.objects.update_or_create(
            product=product,
            defaults={
                'quantity': total_qty,
                'warehouse': '',
                'price_base': price_base,
            }
        )
        if is_new:
            created += 1
        else:
            updated += 1

    logger.info("sync_stock: created=%d updated=%d", created, updated)
    return {'created': created, 'updated': updated}


@shared_task(name='sync.sync_catalog')
def sync_catalog():
    """Run full catalog sync: categories -> brands -> products."""
    cats = sync_categories()
    brands = sync_brands()
    products = sync_products()
    logger.info("sync_catalog complete: cats=%s brands=%s products=%s",
                cats, brands, products)
    return {'categories': cats, 'brands': brands, 'products': products}


_AC_CATEGORY_KEYWORDS = [
    'сплит', 'split', 'кондиционер', 'мультисплит', 'инвертор',
    'полупромышленн', 'мобильн', 'он-офф',
]


def _ac_products_qs():
    """QuerySet of products belonging to AC/split-system categories only."""
    from django.db.models import Q
    q = Q()
    for kw in _AC_CATEGORY_KEYWORDS:
        q |= Q(category__title__icontains=kw)
    return Product.objects.filter(q, is_active=True)


@shared_task(name='sync.build_rusklimat_mapping')
def build_rusklimat_mapping(limit=None):
    """Populate rusklimat_guid for AC/split-system products via Rusklimat API."""
    client = RusklimatClient()
    if not client.token or not client.contractor_guid:
        logger.warning('build_rusklimat_mapping: Rusklimat credentials not configured')
        return {'mapped': 0, 'skipped': 0}

    qs = _ac_products_qs().filter(rusklimat_guid='')
    if limit:
        qs = qs[:limit]

    mapped = skipped = 0
    for product in qs:
        guid = None
        if product.nc_code:
            guid = client.find_product_by_nc(product.nc_code)
        if not guid and product.articul:
            guid = client.find_product_by_articul(product.articul)
        if guid:
            Product.objects.filter(pk=product.pk).update(rusklimat_guid=guid)
            mapped += 1
            logger.debug('Mapped %s → %s', product.nc_code, guid)
        else:
            skipped += 1

    logger.info('build_rusklimat_mapping: mapped=%d skipped=%d', mapped, skipped)
    return {'mapped': mapped, 'skipped': skipped}


@shared_task(name='sync.sync_rusklimat_stock')
def sync_rusklimat_stock():
    """
    Scrape AC catalog from b2b.rusklimat.com and update stock by NC code.
    Covers: сплит-системы, мультисплит, полупромышленные, он-офф, мобильные.
    """
    from apps.sync.rusklimat_scraper import RusklimatScraper

    stock_data = RusklimatScraper().get_ac_stock()
    if not stock_data:
        logger.warning('sync_rusklimat_stock: no data returned from scraper')
        return {'updated': 0, 'skipped': 0}

    updated = skipped = 0
    for nc_code, qty in stock_data.items():
        product = Product.objects.filter(nc_code=nc_code).first()
        if not product:
            skipped += 1
            continue
        Stock.objects.update_or_create(
            product=product,
            defaults={'quantity': qty, 'warehouse': 'rusklimat'},
        )
        updated += 1

    logger.info('sync_rusklimat_stock: updated=%d skipped=%d', updated, skipped)
    return {'updated': updated, 'skipped': skipped}
