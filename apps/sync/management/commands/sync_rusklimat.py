from django.core.management.base import BaseCommand
from apps.sync.tasks import build_rusklimat_mapping, sync_rusklimat_stock, sync_rusklimat_catalog


class Command(BaseCommand):
    help = 'Manage Rusklimat stock and catalog synchronisation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--build-mapping', action='store_true',
            help='Query Rusklimat API to populate rusklimat_guid on products (run once)',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Process only N products when building mapping (for testing)',
        )
        parser.add_argument(
            '--sync-catalog', action='store_true',
            help='Download full Rusklimat catalog CSV and import AC products',
        )

    def handle(self, *args, **options):
        if options['build_mapping']:
            self.stdout.write('Building Rusklimat GUID mapping...')
            result = build_rusklimat_mapping(limit=options['limit'])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Mapping done: mapped={result['mapped']} skipped={result['skipped']}"
                )
            )
        elif options['sync_catalog']:
            self.stdout.write('Syncing Rusklimat full catalog (this may take several minutes)...')
            result = sync_rusklimat_catalog()
            if 'error' in result:
                self.stdout.write(self.style.ERROR(f"Catalog sync failed: {result['error']}"))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Catalog sync done: created={result['created']} "
                        f"updated={result['updated']} skipped={result['skipped']}"
                    )
                )
        else:
            self.stdout.write('Syncing Rusklimat stock...')
            result = sync_rusklimat_stock()
            self.stdout.write(
                self.style.SUCCESS(f"Stock updated: {result['updated']} products")
            )
