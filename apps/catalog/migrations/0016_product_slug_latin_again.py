"""Повтор 0015: кириллица в адресах товаров → латиница (13.11.2026).

После 0015 синхронизация Бриза (apps/sync/tasks.sync_products) раз в 4 часа
снова записывала slug с «НС-…» кириллицей: на проде набралось 1 660 активных
товаров, которые из sitemap открывались как 404. Синхронизация исправлена
(_breez_slug), эта миграция переводит уже испорченные slug. Логика та же,
что в 0015; конфликтов на боевой БД перед выкладкой — 0.
"""
from django.db import migrations

BATCH = 1000


def forwards(apps, schema_editor):
    from apps.catalog.slugs import to_latin

    Product = apps.get_model('catalog', 'Product')
    taken = set(Product.objects.values_list('slug', flat=True))
    changed = []
    for p in Product.objects.only('id', 'slug', 'nc_code').iterator(chunk_size=BATCH):
        if p.slug.isascii():
            continue
        new = to_latin(p.slug)[:500] or f'product-{to_latin(p.nc_code) or p.pk}'
        base, i = new, 1
        while new in taken:
            i += 1
            new = f'{base[:490]}-{i}'
        taken.discard(p.slug)
        taken.add(new)
        p.slug = new
        changed.append(p)
        if len(changed) >= BATCH:
            Product.objects.bulk_update(changed, ['slug'])
            changed = []
    if changed:
        Product.objects.bulk_update(changed, ['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0015_product_slug_latin'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
