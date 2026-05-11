from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.catalog.models import Brand


class Command(BaseCommand):
    help = 'Delete Brand rows that have no related Product (dry-run by default)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually delete brands. Without this flag the command only prints candidates.',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        qs = (
            Brand.objects
            .annotate(products_count=Count('products'))
            .filter(products_count=0)
            .order_by('title')
        )

        total_brands = Brand.objects.count()
        candidates = list(qs.values('id', 'title', 'breez_id', 'slug'))

        self.stdout.write(f'Total brands in DB: {total_brands}')
        self.stdout.write(f'Brands without products: {len(candidates)}')

        if not candidates:
            self.stdout.write(self.style.SUCCESS('Nothing to delete.'))
            return

        for row in candidates:
            origin = 'breeze' if row['breez_id'] is not None else 'rusklimat/manual'
            self.stdout.write(
                f"  id={row['id']:>5}  breez_id={row['breez_id']!s:<5}  "
                f"origin={origin:<16}  {row['title']}"
            )

        if not apply:
            self.stdout.write(self.style.WARNING(
                'Dry-run mode. Re-run with --apply to delete these brands.'
            ))
            return

        ids = [row['id'] for row in candidates]
        deleted, _ = Brand.objects.filter(id__in=ids).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} rows.'))
