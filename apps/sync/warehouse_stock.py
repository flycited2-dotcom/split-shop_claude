"""Общий helper для записи остатков по складам.

Все три поставщика (Бриз / Rusklimat / Daichi) умеют отдавать per-warehouse
breakdown. Эта утилита берёт нормализованный список (warehouse_name, qty)
и пишет в `Stock` (агрегат) + `WarehouseStock` (детализация).

Главное правило для Крыма: `Stock.quantity` хранит остаток на крымском
складе (Симферополь), потому что розничный покупатель в Крыму видит «В
наличии» именно по локальному складу. Остальные склады — справочно в
карточке товара через WarehouseStock.
"""
import re

from apps.stock.models import Stock, WarehouseStock


_CRIMEA_RE = re.compile(
    r'симфер|севастоп|крым|ялт|евпатор|феодос|керч',
    re.IGNORECASE,
)


def _parse_qty(raw):
    """Бриз отдаёт quantity как '>50' для остатков больше 50.
    Превращаем в int с safe-fallback."""
    if raw is None:
        return 0
    s = str(raw).strip()
    if not s:
        return 0
    if s.startswith('>'):
        # «>50» → 50 (минимум, реально больше — но точнее не знаем)
        try:
            return max(0, int(s[1:].strip()))
        except (TypeError, ValueError):
            return 0
    try:
        return max(0, int(s))
    except (TypeError, ValueError):
        try:
            return max(0, int(float(s)))
        except (TypeError, ValueError):
            return 0


def _normalize_warehouse_name(name):
    """Приводим имя склада к человеческому виду.

    Поставщики пишут по-разному: «симферополь склад» (Rusklimat), «Симферопль»
    (Daichi, опечатка), «Бриз Крым» (Бриз). Для UI унифицируем крымские
    варианты в «Симферополь», остальные оставляем как есть.
    """
    n = (name or '').strip()
    if not n:
        return ''
    low = n.lower()
    if 'симфер' in low or 'симфирополь' in low:
        return 'Симферополь'
    return n


def write_warehouse_stocks(product, warehouses):
    """Перезаписывает остатки товара по складам.

    `warehouses` — iterable of (name, quantity). Пустые/нулевые имена
    отфильтровываются. Отрицательные qty приводятся к 0.
    Возвращает (crimea_qty, total_qty, written_count).
    """
    seen_names = set()
    crimea = 0
    total = 0
    rows = []

    for raw_name, raw_qty in warehouses:
        name = _normalize_warehouse_name(raw_name)
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        qty = _parse_qty(raw_qty)
        rows.append((name, qty))
        total += qty
        if _CRIMEA_RE.search(name):
            crimea = max(crimea, qty)

    # Replace-strategy: удаляем старые записи + вставляем новые. Так чище,
    # чем считать diff (склады редко меняются, объём пары записей на товар).
    WarehouseStock.objects.filter(product=product).delete()
    if rows:
        WarehouseStock.objects.bulk_create([
            WarehouseStock(product=product, warehouse=name, quantity=qty)
            for name, qty in rows
        ])

    # Сводный Stock — главным остатком считаем Крым; если его нет — сумму.
    main_qty = crimea if crimea > 0 else 0  # «есть в Крыму или нет» — да/нет
    main_warehouse = 'Симферополь' if crimea > 0 else (
        rows[0][0] if rows and total > 0 else ''
    )
    Stock.objects.update_or_create(
        product=product,
        defaults={
            'quantity': main_qty,
            'warehouse': main_warehouse[:255],
            'price_base': product.price_wholesale,
        },
    )
    return crimea, total, len(rows)
