"""Утилиты для определения мощности (BTU) кондиционера по артикулу.

BTU-код регулярно встречается в артикулах поставщиков (07/09/12/18/24/30 — стандарт,
плюс редкие 10/13/14/16/20/22/25/26/32/35/40 у Electrolux/Mitsubishi).
"""
import re

_BTU_REGEX = re.compile(
    r'(^|[^0-9])(07|09|10|12|13|14|16|18|20|22|24|25|26|27|30|32|35|36|40|42|48|60)([^0-9]|$)'
)

# Приблизительная максимальная площадь помещения для данной мощности (м²).
# Используется в подписях «9 000 BTU (до 25 м²)».
BTU_TO_AREA = {
    7: 20,  9: 25,  10: 28,  12: 35,  13: 38,  14: 40,  16: 42,
    18: 50,  20: 55,  22: 60,  24: 65,  25: 70,  26: 72,  27: 75,
    30: 85,  32: 90,  35: 100, 36: 105, 40: 120, 42: 125, 48: 145, 60: 180,
}


def extract_btu(articul):
    """Достаёт BTU-код из артикула. Возвращает int или None.

    **Внимание:** некоторые поставщики (например, XIGMA) маркируют артикул
    цифрой ПЛОЩАДИ помещения (XGI-TXE27RHA = до 27 м², но реально 9 kBTU).
    Поэтому всегда сначала пробовать resolve_btu(product) — с приоритетом на
    реальную «Холодопроизводительность (kBTU)» из tech_values.
    """
    m = _BTU_REGEX.search((articul or '').strip())
    return int(m.group(2)) if m else None


# Возможные названия TechSpec, в которых лежит мощность в kBTU.
_BTU_SPEC_HINTS = (
    'холодопроизв',          # «Холодопроизводительность (kBTU)» — Бриз
    'мощность охлажд',       # Daichi: «Мощность охлаждения, BTU»
    'cooling capacity',
)


def _is_kbtu_spec(title, unit):
    """Распознаёт TechSpec в kBTU по title+unit."""
    t = (title or '').lower()
    u = (unit or '').lower()
    if 'kbtu' in u or 'btu' in u:
        return True
    if any(h in t for h in _BTU_SPEC_HINTS) and 'квт' not in t and 'kw' not in u:
        # «Холодопроизводительность (kBTU)» — да; «(кВт)» — нет.
        return 'kbtu' in t or 'btu' in t
    return False


def _parse_btu_value(raw):
    """Парсит значение типа '9', '9.5', '2.65 (0.7 - 3.37)' → ближайший стандарт BTU."""
    s = str(raw or '').strip()
    if not s:
        return None
    # Берём первое число
    import re as _re
    m = _re.search(r'\d+(?:[.,]\d+)?', s)
    if not m:
        return None
    try:
        val = float(m.group().replace(',', '.'))
    except (TypeError, ValueError):
        return None
    # Округляем до ближайшего из BTU_VALUES, иначе int(val)
    rounded = int(round(val))
    if rounded in BTU_TO_AREA:
        return rounded
    # Если не точное совпадение — ближайшее из таблицы
    if rounded > 0 and BTU_TO_AREA:
        return min(BTU_TO_AREA.keys(), key=lambda x: abs(x - rounded))
    return rounded if rounded > 0 else None


def resolve_btu(product):
    """Возвращает мощность товара в kBTU с приоритетом на tech_values.

    1. Ищет в product.tech_values запись типа «Холодопроизводительность (kBTU)».
    2. Если не нашлось — fallback на extract_btu(articul) (XIGMA tricky).
    3. None если нет ни того ни другого.
    """
    if product is None:
        return None
    # Без обращения к БД если уже prefetch'нуто
    try:
        tech_values = product.tech_values.all()
    except Exception:
        tech_values = []
    for tv in tech_values:
        spec = getattr(tv, 'spec', None)
        if spec and _is_kbtu_spec(spec.title, spec.unit):
            val = _parse_btu_value(tv.value)
            if val:
                return val
    # Fallback на артикул
    return extract_btu(getattr(product, 'articul', ''))


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
