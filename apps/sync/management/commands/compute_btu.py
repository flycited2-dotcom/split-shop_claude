"""Пересчитывает Product.btu_calc для всех (или фильтра) товаров.

Источник — `apps.catalog.btu.compute_btu` (мощность охлаждения / площадь /
артикул). Выводит сводку: сколько подтянули из tech, сколько из артикула,
сколько без BTU.

Usage:
    python manage.py compute_btu                  # все активные товары
    python manage.py compute_btu --all            # включая is_active=False
    python manage.py compute_btu --source breeze  # только Бриз
    python manage.py compute_btu --recalc-only    # только товары, где btu_calc уже задан (refresh)
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Product
from apps.catalog.btu import compute_btu


class Command(BaseCommand):
    help = 'Пересчитывает Product.btu_calc для всех товаров'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true',
                            help='Включая is_active=False')
        parser.add_argument('--source', type=str, default='',
                            help='Только указанный source (breeze/rusklimat/daichi)')
        parser.add_argument('--recalc-only', action='store_true',
                            help='Только товары с уже заданным btu_calc')
        parser.add_argument('--batch', type=int, default=500,
                            help='Batch size для bulk_update')

    def handle(self, *args, **opts):
        qs = Product.objects.all()
        if not opts['all']:
            qs = qs.filter(is_active=True)
        if opts['source']:
            qs = qs.filter(source=opts['source'])
        if opts['recalc_only']:
            qs = qs.exclude(btu_calc__isnull=True)
        qs = qs.prefetch_related('tech_values__spec')

        total = qs.count()
        self.stdout.write(f'Пересчёт btu_calc для {total} товаров...')

        counter = Counter()
        to_update = []
        batch_size = opts['batch']
        processed = 0

        for p in qs.iterator(chunk_size=batch_size):
            new = compute_btu(p)
            old = p.btu_calc
            if new != old:
                p.btu_calc = new
                to_update.append(p)
            counter['total'] += 1
            if new:
                counter[f'btu_{new}'] += 1
            else:
                counter['btu_none'] += 1

            if len(to_update) >= batch_size:
                with transaction.atomic():
                    Product.objects.bulk_update(to_update, ['btu_calc'])
                processed += len(to_update)
                to_update.clear()
                self.stdout.write(f'  ... {counter["total"]} обработано, {processed} обновлено')

        if to_update:
            with transaction.atomic():
                Product.objects.bulk_update(to_update, ['btu_calc'])
            processed += len(to_update)

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: обработано {counter["total"]}, обновлено {processed}.'
        ))
        self.stdout.write('Распределение BTU:')
        rows = sorted(
            ((k.replace('btu_', ''), v) for k, v in counter.items()
             if k.startswith('btu_')),
            key=lambda x: (-1 if x[0] == 'none' else int(x[0]))
        )
        for label, n in rows:
            tag = 'нет' if label == 'none' else f'{label} kBTU'
            self.stdout.write(f'  {n:>5}  {tag}')
