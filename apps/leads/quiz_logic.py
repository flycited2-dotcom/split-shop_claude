from django.db.models import F, Q

from apps.catalog.models import Product
from apps.catalog.filters import MULTI_SPLIT_BLOCK_Q

BTU_VALUES = [7, 9, 12, 18, 24, 30]

# Карта «верхняя граница площади м² → подобранный BTU». Используется и в view
# для отрисовки кнопок-пилюль шага 1 квиза.
AREA_TO_BTU = [
    (20, 7),
    (25, 9),
    (35, 12),
    (45, 18),
    (65, 24),
    (None, 30),  # >65 м²
]

# Границы диапазонов: (граничная_площадь, нижний_btu, верхний_btu). area ≤ граница → нижний.
_BTU_BORDERS = [
    (20, 7, 9),
    (25, 9, 12),
    (35, 12, 18),
    (45, 18, 24),
    (65, 24, 30),
]
# Запас в м² у границы, при котором показываем соседний BTU.
_BORDER_TOLERANCE = 3


def btu_from_area(area_sqm):
    main, _ = btu_candidates(area_sqm)
    return main


def btu_candidates(area_sqm):
    """Возвращает (main_btu, secondary_btus).

    Для пограничных площадей (±3 м² от границы диапазона) добавляет соседний BTU
    в secondary — чтобы юзер увидел и «впритык», и «с запасом».
    """
    if area_sqm <= 20:
        main = 7
    elif area_sqm <= 25:
        main = 9
    elif area_sqm <= 35:
        main = 12
    elif area_sqm <= 45:
        main = 18
    elif area_sqm <= 65:
        main = 24
    else:
        main = 30

    secondary = []
    for border, lower, upper in _BTU_BORDERS:
        if abs(area_sqm - border) > _BORDER_TOLERANCE:
            continue
        candidate = lower if main == upper else upper if main == lower else None
        if candidate and candidate != main and candidate not in secondary:
            secondary.append(candidate)
    return main, secondary


def _btu_q(btus):
    q = Q()
    for btu in btus:
        code = f'{btu:02d}'
        q |= Q(articul__iregex=rf'(^|[^0-9]){code}([^0-9]|$)')
    return q


_COLOR_BLACK_Q = Q(title__icontains='черн') | Q(title__icontains='black')
_MOBILE_Q = Q(title__icontains='мобильн')

# Сколько брать товаров на pre-filter (буфер для балансировки по поставщикам).
_BUFFER = 30


def _base_qs(btus, *, needs_inverter, budget_max, needs_black, exclude_mobile=False):
    qs = Product.objects.filter(
        _btu_q(btus),
        is_active=True,
        category__sync_enabled=True,
    ).exclude(MULTI_SPLIT_BLOCK_Q)
    if exclude_mobile:
        qs = qs.exclude(_MOBILE_Q)
    if needs_inverter:
        qs = qs.filter(title__iregex=r'инвертор|inverter')
    if budget_max:
        qs = qs.filter(ric__lte=budget_max)
    if needs_black:
        qs = qs.filter(_COLOR_BLACK_Q)
    return qs.select_related('brand').prefetch_related('images').order_by(
        F('stock__quantity').desc(nulls_last=True),
        'ric',
    )


def _balance_by_source(products, per_source=2, total=6):
    """Round-robin балансировка по полю Product.source.

    Шаг 1: круг за кругом берём по 1 от каждого source (до per_source кругов).
    Шаг 2: если total не набран — добиваем тем, что осталось (без лимита).
    Сохраняет относительный порядок внутри source-группы (приоритет stock+ric).
    """
    if not products:
        return []

    groups = {}
    for p in products:
        groups.setdefault(p.source or 'unknown', []).append(p)

    result = []
    seen = set()
    sources = list(groups.keys())
    for round_idx in range(per_source):
        for s in sources:
            if len(result) >= total:
                break
            lst = groups[s]
            if round_idx < len(lst):
                p = lst[round_idx]
                if p.pk not in seen:
                    result.append(p)
                    seen.add(p.pk)
        if len(result) >= total:
            break

    if len(result) < total:
        for s in sources:
            for p in groups[s][per_source:]:
                if len(result) >= total:
                    break
                if p.pk not in seen:
                    result.append(p)
                    seen.add(p.pk)
            if len(result) >= total:
                break

    return result[:total]


def recommend_products(btu, *, budget_max=None, needs_inverter=False,
                       needs_black=False, room_type=None,
                       per_source=2, total=6, secondary_btus=None):
    """Подбор товаров с последовательным ослаблением фильтров и балансировкой по поставщикам.

    Возвращает (products, relaxed). `relaxed` — список причин ослабления:
        'color_relaxed', 'budget_relaxed', 'inverter_relaxed', 'nothing_found'.
    Пустой список = нашли по строгим параметрам.
    Порядок ослабления: цвет → бюджет → инвертор (от менее критичного
    к более — инвертор/тишина для юзера важнее всего).

    `room_type='commercial'` — для коммерции/офисов исключаем мобильные кондиционеры.

    Финальная выборка балансируется по `Product.source` (breeze/rusklimat/daichi):
    по `per_source` товаров от каждого источника, общая длина до `total`.
    """
    all_btus = [btu] + list(secondary_btus or [])
    relaxed = []
    exclude_mobile = (room_type == 'commercial')

    def _try(*, needs_inverter, budget_max, needs_black):
        qs = _base_qs(
            all_btus,
            needs_inverter=needs_inverter,
            budget_max=budget_max,
            needs_black=needs_black,
            exclude_mobile=exclude_mobile,
        )
        return list(qs[:_BUFFER])

    # 1. Строго по всем фильтрам.
    products = _try(needs_inverter=needs_inverter, budget_max=budget_max, needs_black=needs_black)
    if products:
        return _balance_by_source(products, per_source, total), relaxed

    # 2. Снять цвет.
    if needs_black:
        relaxed.append('color_relaxed')
        products = _try(needs_inverter=needs_inverter, budget_max=budget_max, needs_black=False)
        if products:
            return _balance_by_source(products, per_source, total), relaxed

    # 3. Снять бюджет.
    if budget_max:
        relaxed.append('budget_relaxed')
        products = _try(needs_inverter=needs_inverter, budget_max=None, needs_black=False)
        if products:
            return _balance_by_source(products, per_source, total), relaxed

    # 4. Снять инвертор.
    if needs_inverter:
        relaxed.append('inverter_relaxed')
        products = _try(needs_inverter=False, budget_max=None, needs_black=False)
        if products:
            return _balance_by_source(products, per_source, total), relaxed

    relaxed.append('nothing_found')
    return [], relaxed
