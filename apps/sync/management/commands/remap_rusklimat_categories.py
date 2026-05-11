from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.catalog.models import Product, Category
from apps.sync.rusklimat_catalog import _resolve_master_category, _make_unique_slug


class Command(BaseCommand):
    help = 'Re-map Rusklimat products to unified master categories'

    def handle(self, *args, **options):
        qs = Product.objects.filter(source='rusklimat').select_related('category__parent')
        total = qs.count()
        self.stdout.write(f'Remapping {total} Rusklimat products...')

        # Build path → category cache
        cat_cache = {}
        remapped = skipped = unchanged = 0

        for product in qs.iterator(chunk_size=500):
            # Reconstruct the original category path for matching
            cat = product.category
            if cat:
                path = f'{cat.parent.title} - {cat.title}' if cat.parent else cat.title
            else:
                path = ''

            kind, value = _resolve_master_category(path)
            new_cat = None

            if kind == 'breez_id':
                if value not in cat_cache:
                    cat_cache[value] = Category.objects.filter(breez_id=value).first()
                new_cat = cat_cache[value]
            elif kind == 'master':
                if value not in cat_cache:
                    obj = Category.objects.filter(title__iexact=value).first()
                    if not obj:
                        slug = _make_unique_slug(Category, slugify(value, allow_unicode=True) or 'category')
                        obj = Category.objects.create(title=value, slug=slug, breez_id=None, sync_enabled=True)
                    cat_cache[value] = obj
                new_cat = cat_cache[value]

            if new_cat is None:
                skipped += 1
                continue

            if product.category_id == new_cat.pk:
                unchanged += 1
                continue

            Product.objects.filter(pk=product.pk).update(category=new_cat)
            remapped += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: remapped={remapped} unchanged={unchanged} skipped={skipped}'
        ))
