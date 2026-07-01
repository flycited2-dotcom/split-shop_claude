"""Динамические фильтры по TechSpec.is_filter=True.

В отличие от filters.py (фасеты захардкожены в коде — brand/btu/color/...),
здесь набор фасет зависит от данных: какие TechSpec с is_filter=True
привязаны к выбранной категории (флаг приходит из Breez API, см.
apps/sync/breeze_tech.py). Позволяет добавлять новые фильтры (Wi-Fi, класс
энергоэффективности и т.п.) без правки кода — просто пометив характеристику
в админке.

URL: ?tech=<spec_id>:<value> (повторяется для нескольких значений/спеков).
Внутри одного spec_id — OR (любое из выбранных значений), между разными
spec_id — AND.
"""
from django.db.models import Count, Q

from .models import ProductTech, TechSpec

# Специфики с числом уникальных значений выше этого порога почти наверняка
# непрерывные/числовые (площадь, длина трассы и т.п.), а не категориальные —
# живой пример: «Эффективен для помещений площадью до» отдаёт 20, 20.5, 21,
# 21.4... — десятки почти одинаковых значений. Чекбокс-панель для них
# бесполезна (нужен range-slider — отдельная задача), поэтому такие
# специфики просто не показываем как фасету.
_MAX_FACET_OPTIONS = 15


def parse_tech_params(get_data):
    """{spec_id: {value, ...}} из повторяющихся ?tech=<spec_id>:<value>."""
    grouped = {}
    for raw in get_data.getlist('tech'):
        spec_id_str, _, value = raw.partition(':')
        if not value:
            continue
        try:
            spec_id = int(spec_id_str)
        except ValueError:
            continue
        grouped.setdefault(spec_id, set()).add(value)
    return grouped


def apply_tech_filters(get_data, qs, exclude_spec_id=None):
    """Накладывает выбранные tech-фильтры на qs. AND между spec_id, OR внутри."""
    grouped = parse_tech_params(get_data)
    applied = False
    for spec_id, values in grouped.items():
        if spec_id == exclude_spec_id:
            continue
        qs = qs.filter(tech_values__spec_id=spec_id, tech_values__value__in=values)
        applied = True
    return qs.distinct() if applied else qs


def compute_tech_facets(get_data, category, qs):
    """qs — уже отфильтрован по всем статическим ProductFilter-полям (включая
    category), но ДО tech-фильтров.

    TechSpec.category сейчас у всех is_filter=True записей пуст (специфика
    данных из Breez API — специфики глобальные, не привязаны к категории),
    поэтому показываем: глобальные (category=None) всегда + специфичные для
    выбранной категории, если она выбрана. Нерелевантные для текущей выдачи
    специфики сами отсеются ниже (rows будет пустым, если ни у одного товара
    в qs нет значения по этой характеристике).
    """
    spec_filter = Q(category__isnull=True)
    if category:
        spec_filter |= Q(category=category)
    grouped_selected = parse_tech_params(get_data)
    specs = TechSpec.objects.filter(spec_filter, is_filter=True).order_by('order')

    result = []
    for spec in specs:
        qs_excl = apply_tech_filters(get_data, qs, exclude_spec_id=spec.id)
        # Значения НЕ нормализуются по регистру/пробелам — разные поставщики
        # пишут «Да»/«да» как отдельные варианты. Известное ограничение
        # качества данных, не блокирует базовую работу фильтра.
        rows = list(
            ProductTech.objects
            .filter(product__in=qs_excl, spec=spec)
            .values('value')
            .annotate(n=Count('product', distinct=True))
            .order_by('-n')
        )
        if len(rows) > _MAX_FACET_OPTIONS:
            continue
        selected_values = grouped_selected.get(spec.id, set())
        options = []
        for row in rows:
            val = row['value']
            n = row['n']
            if n == 0 and val not in selected_values:
                continue
            options.append({'value': val, 'count': n, 'selected': val in selected_values})
        if options:
            result.append({'spec_id': spec.id, 'title': spec.title, 'options': options})
    return result
