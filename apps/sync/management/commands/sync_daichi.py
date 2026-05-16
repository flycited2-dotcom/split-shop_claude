from django.core.management.base import BaseCommand

from apps.sync.daichi_catalog import sync_catalog


class Command(BaseCommand):
    help = 'Sync Daichi B2B catalog (products, prices, stock) for configured store.'

    def handle(self, *args, **options):
        result = sync_catalog()
        self.stdout.write(self.style.SUCCESS(f'Daichi sync: {result}'))
