from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.sync.tasks import sync_catalog, sync_stock


class Command(BaseCommand):
    help = 'Полная синхронизация каталога и остатков с API Бриз'

    def add_arguments(self, parser):
        parser.add_argument(
            '--catalog-only',
            action='store_true',
            help='Синхронизировать только каталог',
        )
        parser.add_argument(
            '--stock-only',
            action='store_true',
            help='Синхронизировать только остатки',
        )
        parser.add_argument(
            '--skip-remap',
            action='store_true',
            help='Не запускать remap_categories после синхронизации каталога',
        )

    def handle(self, *args, **options):
        if options['stock_only']:
            self.stdout.write('Синхронизация остатков...')
            result = sync_stock()
            self.stdout.write(self.style.SUCCESS(f'Остатки: {result}'))
            return

        self.stdout.write('Синхронизация каталога...')
        result = sync_catalog()
        self.stdout.write(self.style.SUCCESS(f'Каталог: {result}'))

        if not options['skip_remap']:
            self.stdout.write('Пересборка категорий (remap_categories --apply)...')
            call_command('remap_categories', apply=True)

        if not options['catalog_only']:
            self.stdout.write('Синхронизация остатков...')
            result = sync_stock()
            self.stdout.write(self.style.SUCCESS(f'Остатки: {result}'))
