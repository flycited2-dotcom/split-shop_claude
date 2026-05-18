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
        name = (raw_name or '').strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        try:
            qty = max(0, int(raw_qty or 0))
        except (TypeError, ValueError):
            qty = 0
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
