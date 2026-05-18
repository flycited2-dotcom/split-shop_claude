from django.core.management.base import BaseCommand

from apps.sync.breeze_tech import sync_breez_tech


class Command(BaseCommand):
    help = 'Sync technical characteristics from Breez API (~1100 calls, 3 min)'

    def handle(self, *args, **options):
        result = sync_breez_tech()
        self.stdout.write(self.style.SUCCESS(f'Breez tech sync: {result}'))
