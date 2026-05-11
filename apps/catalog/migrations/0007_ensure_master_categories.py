from django.db import migrations
from django.utils.text import slugify


MASTER_CATEGORIES = [
    # (breez_id, title, slug, order)
    (2,  'Бытовые сплит-системы',         'bytovye-split-sistemy',           10),
    (9,  'Мульти-сплит системы',          'multi-split-sistemy',             20),
    (10, 'Мобильные кондиционеры',        'mobilnye-konditsionery',          40),
]
MASTER_MASTERS = [
    # (title, slug, order) — categories without breez_id
    ('Полупромышленные кондиционеры', 'polupromyshlennye-konditsionery', 30),
    ('Аксессуары для кондиционеров',  'aksessuary-dlya-konditsionerov',  90),
]


def _unique_slug(Category, base, exclude_pk=None):
    slug = base
    qs = Category.objects.filter(slug=slug)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if not qs.exists():
        return slug
    suffix = 2
    while True:
        candidate = f'{base}-{suffix}'
        qs = Category.objects.filter(slug=candidate)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return candidate
        suffix += 1


def ensure_master_categories(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')

    for breez_id, title, slug, order in MASTER_CATEGORIES:
        cat = Category.objects.filter(breez_id=breez_id).first()
        if cat:
            cat.title = title
            cat.order = order
            cat.sync_enabled = True
            if not cat.slug:
                cat.slug = _unique_slug(Category, slug, exclude_pk=cat.pk)
            cat.save()
        else:
            Category.objects.create(
                breez_id=breez_id,
                title=title,
                slug=_unique_slug(Category, slug),
                order=order,
                sync_enabled=True,
            )

    for title, slug, order in MASTER_MASTERS:
        cat = Category.objects.filter(title__iexact=title).first()
        if cat:
            cat.title = title
            cat.order = order
            cat.sync_enabled = True
            cat.save()
        else:
            Category.objects.create(
                breez_id=None,
                title=title,
                slug=_unique_slug(Category, slug),
                order=order,
                sync_enabled=True,
            )


def noop_reverse(apps, schema_editor):
    """Do not delete master categories on rollback — they may hold products."""


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_product_source'),
    ]

    operations = [
        migrations.RunPython(ensure_master_categories, noop_reverse),
    ]
