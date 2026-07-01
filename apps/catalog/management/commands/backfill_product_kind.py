from django.core.management.base import BaseCommand

from apps.catalog.classify import classify_title
from apps.catalog.models import Product


class Command(BaseCommand):
    help = (
        'Пересчитывает Product.kind по title для всех существующих товаров '
        '(classify_title — та же логика, что теперь применяется живым '
        'синкам при создании/обновлении). Разово, после добавления поля '
        'kind. Dry-run по умолчанию — печатает только сводку.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Записать изменения в БД. Без флага — только dry-run.')

    def handle(self, *args, **options):
        apply_changes = options['apply']

        counts = {Product.KIND_SPLIT_SYSTEM: 0, Product.KIND_ACCESSORY: 0,
                  Product.KIND_MULTI_SPLIT_BLOCK: 0}
        changed = 0
        to_update = []

        for product in Product.objects.only('id', 'title', 'kind').iterator(chunk_size=1000):
            new_kind = classify_title(product.title)
            counts[new_kind] += 1
            if new_kind != product.kind:
                changed += 1
                product.kind = new_kind
                to_update.append(product)

        self.stdout.write(f'Всего товаров: {sum(counts.values())}')
        self.stdout.write(f'  → {Product.KIND_SPLIT_SYSTEM}: {counts[Product.KIND_SPLIT_SYSTEM]}')
        self.stdout.write(f'  → {Product.KIND_ACCESSORY}: {counts[Product.KIND_ACCESSORY]}')
        self.stdout.write(f'  → {Product.KIND_MULTI_SPLIT_BLOCK}: {counts[Product.KIND_MULTI_SPLIT_BLOCK]}')
        self.stdout.write(f'Изменится kind у: {changed}')

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                '\nDry-run mode. Re-run with --apply to write changes.'
            ))
            return

        Product.objects.bulk_update(to_update, ['kind'], batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f'\nПрименено. Обновлено товаров: {changed}.'))
