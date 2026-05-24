"""Объединить две полупромышленные категории и убрать аксессуары из розницы.

Контекст (2026-05-24, владелец):
1) В каталоге есть «Полупромышленные кондиционеры» (id=115) и «Полупромышленные
   сплит-системы» (id=6) — это одно и то же. Объединяем в id=6.
2) «Аксессуары для кондиционеров» (id=116) случайно sync_enabled=True — туда
   попадают кронштейны/запчасти/инструменты, которые засоряют каталог и
   подбор. Выключаем sync_enabled.

Миграция идемпотентна — повторный запуск ничего не сделает.
"""
from django.db import migrations


# Регекс для определения «полупромышленные» категории
# (используется как fallback на случай если id поменялись).
_POLYPROM_TITLE_RE = r'полупром'


def merge_polyprom_and_disable_accessories(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    Product = apps.get_model('catalog', 'Product')

    # 1. Найти все «полупромышленные» категории (исключая осушители).
    polyprom = list(
        Category.objects
        .filter(title__iregex=_POLYPROM_TITLE_RE)
        .exclude(title__iregex=r'осушител')
        .order_by('id')
    )
    if len(polyprom) > 1:
        # Канонической оставляем самую раннюю (id=6 «Полупромышленные сплит-системы»).
        canonical = polyprom[0]
        duplicates = polyprom[1:]
        for dup in duplicates:
            moved = Product.objects.filter(category=dup).update(category=canonical)
            print(f'  Перенесли {moved} товаров из «{dup.title}» (id={dup.id}) в '
                  f'«{canonical.title}» (id={canonical.id})')
            dup.sync_enabled = False
            dup.save(update_fields=['sync_enabled'])

    # 2. Выключить sync_enabled у не-AC категорий, которые сейчас включены.
    # Розница не должна показывать аксессуары / запчасти / комплектующие.
    bad_re = r'аксессуар|запчаст|комплектующ|расходн|чехл|пульт|фильтр|кронштей|инструмент|трубк|насадк'
    bad = Category.objects.filter(sync_enabled=True, title__iregex=bad_re)
    for c in bad:
        print(f'  Выключаем sync_enabled у «{c.title}» (id={c.id})')
        c.sync_enabled = False
        c.save(update_fields=['sync_enabled'])


def noop_reverse(apps, schema_editor):
    """Откатывать нельзя — данные товаров уже перемещены."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_brand_featured_in_quiz'),
    ]

    operations = [
        migrations.RunPython(merge_polyprom_and_disable_accessories, noop_reverse),
    ]
