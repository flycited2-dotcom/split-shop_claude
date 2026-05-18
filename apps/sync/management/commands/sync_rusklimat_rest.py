from django.core.management.base import BaseCommand

from apps.sync.rusklimat_rest import sync_rusklimat_rest


class Command(BaseCommand):
    help = 'Sync Rusklimat catalog via REST API (internet-partner.rusklimat.com)'

    def add_arguments(self, parser):
        parser.add_argument('--max-pages', type=int, default=None,
                            help='Ограничить число страниц для теста (по умолчанию все)')

    def handle(self, *args, **options):
        result = sync_rusklimat_rest(max_pages=options.get('max_pages'))
        self.stdout.write(self.style.SUCCESS(f'Rusklimat REST sync: {result}'))
