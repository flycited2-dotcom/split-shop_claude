"""Утилиты для определения мощности (BTU) кондиционера.

Два уровня контроля по TZ:
1. **Холодопроизводительность** в характеристиках (TechSpec/ProductTech) —
   kBTU, кВт или Вт. Это первичный источник.
2. **Рекомендуемая площадь** помещения (м²) — fallback, если мощность не
   указана. По таблице AREA→BTU.
3. **Артикул** — последний fallback. У мобильников Ballu (BPAC-40) и
   XIGMA (TXE27) число — это НЕ BTU, а маркетинговый код (тип серии или
   рекомендуемая площадь). Поэтому артикул — крайнее средство.
"""
import re

# Стандартные значения BTU (kBTU) с соответствующей рекомендуемой площадью (м²).
BTU_TO_AREA = {
    7: 20,  9: 25,  10: 28,  12: 35,  13: 38,  14: 40,  16: 42,
    18: 50,  20: 55,  22: 60,  24: 65,  25: 70,  26: 72,  27: 75,
    30: 85,  32: 90,  35: 100, 36: 105, 40: 120, 42: 125, 48: 145, 60: 180,
}
_BTU_STANDARDS = sorted(BTU_TO_AREA.keys())

# 1 kW = 3.412 kBTU/h.
_KW_TO_KBTU = 3.412142

_BTU_REGEX = re.compile(
    r'(^|[^0-9])(07|09|10|12|13|14|16|18|20|22|24|25|26|27|30|32|35|36|40|42|48|60)([^0-9]|$)'
)


def _round_to_standard(value):
    """Округляем произвольное число kBTU к ближайшему стандартному."""
    if value is None or value <= 0:
        return None
    if value in BTU_TO_AREA:
        return int(value)
    return min(_BTU_STANDARDS, key=lambda b: abs(b - value))


def _parse_number(raw):
    """Из '9' / '9.5' / '2.65 (0.7 - 3.37)' / '7000' → float."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = re.search(r'\d+(?:[.,]\d+)?', s)
    if not m:
        return None
    try:
        return float(m.group().replace(',', '.'))
    except (TypeError, ValueError):
        return None


# Спеки про cooling capacity: точное соответствие или подстроки.
_COOLING_HINTS = (
    'холодопроизв',
    'производительность охлажд',  # «Макс. производительность охлаждения» (Ballu)
    'мощность охлажд',            # «Мощность охлаждения, BTU» (Daichi)
    'мощность кондиционера',      # «Мощность кондиционера (охлаждение),BTU» (Rusklimat)
    'cooling capacity',
)
# Чёрный список — эти спеки про потребляемую/электронагрев, не охлаждение.
_COOLING_BLACKLIST = (
    'потреб',          # «Потребляемая мощность в режиме охлаждения»
    'электронагрев',   # «Теплопроизводительность встроенного электронагревателя»
    'эер',             # «EER» — эффективность, не мощность
    'cop',
)


def _is_cooling_spec(title):
    """Распознаёт TechSpec о мощности охлаждения."""
    t = (title or '').lower()
    if not t:
        return False
    if not any(h in t for h in _COOLING_HINTS):
        return False
    if any(b in t for b in _COOLING_BLACKLIST):
        return False
    return True


def _unit_kind(title, unit):
    """Определяет, в каких единицах число: kbtu, kw, w или None."""
    t = (title or '').lower()
    u = (unit or '').lower()
    # kBTU — приоритет
    if 'kbtu' in u or 'kbtu' in t:
        return 'kbtu'
    # kW — две формы
    if u in ('квт', 'kw') or 'квт' in t or 'kw' in t:
        return 'kw'
    # W (только если явно «Вт», не «кВт»)
    if u in ('вт', 'w'):
        return 'w'
    # «BTU» без «k» — обычно полное число (7000), Rusklimat и Ballu пишут так.
    if u == 'btu' or ',btu' in t or 'btu' in t:
        return 'btu'
    return None


def _value_to_kbtu(value, kind):
    """Конвертирует распарсенное value в kBTU по типу единицы."""
    if value is None or value <= 0:
        return None
    if kind == 'kbtu':
        return value  # уже kBTU
    if kind == 'btu':
        return value / 1000.0  # «7000» BTU → 7 kBTU
    if kind == 'kw':
        return value * _KW_TO_KBTU
    if kind == 'w':
        return (value / 1000.0) * _KW_TO_KBTU
    return None


def _btu_from_tech_cooling(tech_values):
    """Источник 1: мощность охлаждения из TechSpec."""
    # Соберём всех кандидатов с парой (kind_priority, kbtu_value), потом
    # выберем по приоритету единиц: kbtu > btu > kw > w.
    priority = {'kbtu': 4, 'btu': 3, 'kw': 2, 'w': 1}
    candidates = []
    for tv in tech_values:
        spec = getattr(tv, 'spec', None)
        if not spec or not _is_cooling_spec(spec.title):
            continue
        kind = _unit_kind(spec.title, spec.unit)
        if not kind:
            continue
        val = _parse_number(tv.value)
        if val is None:
            continue
        kbtu = _value_to_kbtu(val, kind)
        if kbtu and kbtu > 0:
            candidates.append((priority[kind], kbtu))
    if not candidates:
        return None
    # Самый «доверенный» источник.
    candidates.sort(key=lambda x: -x[0])
    return _round_to_standard(candidates[0][1])


# Спеки про площадь помещения.
_AREA_HINTS = (
    'эффективен для помещ',
    'для помещения площад',
    'площадь помещения',
    'recommended area',
)
_AREA_BLACKLIST = (
    'эксплуатиро',  # «должен устанавливаться, эксплуатироваться в помещении более»
    'хранит',
)


def _is_area_spec(title, unit):
    t = (title or '').lower()
    u = (unit or '').lower()
    if not any(h in t for h in _AREA_HINTS):
        return False
    if any(b in t for b in _AREA_BLACKLIST):
        return False
    # unit может быть «м2», «м<sup>2</sup>», пустым (значение часто содержит число).
    if u and 'м' not in u and 'm' not in u:
        return False
    return True


def _btu_from_tech_area(tech_values):
    """Источник 2: рекомендуемая площадь."""
    for tv in tech_values:
        spec = getattr(tv, 'spec', None)
        if not spec or not _is_area_spec(spec.title, spec.unit):
            continue
        area = _parse_number(tv.value)
        if area and area > 0:
            # Ближайший BTU по target area.
            return min(_BTU_STANDARDS, key=lambda b: abs(BTU_TO_AREA[b] - area))
    return None


def extract_btu(articul):
    """Достаёт BTU-код из артикула. Последний fallback.

    Внимание: ненадёжно для мобильников Ballu (BPAC-09 — 09 ловится верно,
    но `Ballu Eclipse-40` поломает результат) и XIGMA (TXE27 = 27 м², 9 kBTU).
    """
    m = _BTU_REGEX.search((articul or '').strip())
    return int(m.group(2)) if m else None


def resolve_btu(product):
    """Возвращает BTU товара в kBTU.

    Приоритет:
    1. cached `product.btu_calc` (если поле есть и не None).
    2. TechSpec мощность охлаждения (kBTU > BTU > kW > W).
    3. TechSpec рекомендуемая площадь.
    4. Артикул.
    """
    if product is None:
        return None
    cached = getattr(product, 'btu_calc', None)
    if cached:
        return cached
    return compute_btu(product)


def compute_btu(product):
    """Свежее вычисление без чтения кэша — для пересчёта поля btu_calc."""
    if product is None:
        return None
    try:
        tech_values = list(product.tech_values.all())
    except Exception:
        tech_values = []
    return (
        _btu_from_tech_cooling(tech_values)
        or _btu_from_tech_area(tech_values)
        or extract_btu(getattr(product, 'articul', ''))
    )


def refresh_btu_calc(product):
    """Пересчитывает и сохраняет `Product.btu_calc`. Вызывается из sync
    после записи tech_values. Тихий no-op, если значение не изменилось."""
    if product is None:
        return None
    new = compute_btu(product)
    if product.btu_calc != new:
        product.btu_calc = new
        product.save(update_fields=['btu_calc'])
    return new


def btu_label(btu, with_area=True):
    """«9 000 BTU (до 25 м²)» или «9 000 BTU»."""
    if not btu:
        return ''
    base = f'{btu} 000 BTU'
    if with_area:
        area = BTU_TO_AREA.get(btu)
        if area:
            return f'{base} (до {area} м²)'
    return base
