from django.db.models import F

from apps.catalog.models import Product

BTU_VALUES = [7, 9, 12, 18, 24, 30]


def btu_from_area(area_sqm):
    if area_sqm <= 20:
        return 7
    if area_sqm <= 25:
        return 9
    if area_sqm <= 35:
        return 12
    if area_sqm <= 45:
        return 18
    if area_sqm <= 65:
        return 24
    return 30


def _btu_code(btu):
    return f'{btu:02d}'


def recommend_products(btu, *, budget_max=None, needs_inverter=False, limit=6):
    code = _btu_code(btu)
    qs = Product.objects.filter(
        is_active=True,
        category__sync_enabled=True,
        articul__iregex=rf'(^|[^0-9]){code}([^0-9]|$)',
    )
    if needs_inverter:
        qs = qs.filter(title__iregex=r'инвертор|inverter')
    if budget_max:
        qs = qs.filter(ric__lte=budget_max)
    qs = qs.select_related('brand').prefetch_related('images').order_by(
        F('stock__quantity').desc(nulls_last=True),
        'ric',
    )
    return list(qs[:limit])
