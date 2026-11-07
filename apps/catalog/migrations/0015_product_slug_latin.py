"""Кириллица в адресах товаров → латиница (SEO-аудит 06.11.2026).

Меняются только slug с не-ASCII символами, латинские остаются как были.
Старые адреса продолжают работать: product_detail переводит запрошенный
slug той же функцией to_latin() и отдаёт 301 на новый адрес.
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
        # Коллизия — суффикс. Старый адрес такого товара редирект уведёт на
        # владельца латинского slug, поэтому перед выкладкой число коллизий
        # проверено на боевой БД (ожидается 0).
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
        ('catalog', '0014_product_heating_min_temp_product_is_heat_pump'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
