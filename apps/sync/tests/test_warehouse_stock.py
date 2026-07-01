"""Юнит-тесты для apps/sync/warehouse_stock.py.

Pure-функции через SimpleTestCase. Главный write_warehouse_stocks — через
TestCase с реальными Stock/WarehouseStock.
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.catalog.models import Brand, Category, Product
from apps.stock.models import Stock, WarehouseStock
from apps.sync import warehouse_stock as ws


class ParseQtyTest(SimpleTestCase):

    def test_int_string(self):
        self.assertEqual(ws._parse_qty('5'), 5)

    def test_breez_over_50_marker(self):
        # Бриз отдаёт '>50' для остатков > 50.
        self.assertEqual(ws._parse_qty('>50'), 50)

    def test_over_500(self):
        self.assertEqual(ws._parse_qty('>500'), 500)

    def test_none(self):
        self.assertEqual(ws._parse_qty(None), 0)

    def test_empty_string(self):
        self.assertEqual(ws._parse_qty(''), 0)

    def test_negative_clamped_to_zero(self):
        self.assertEqual(ws._parse_qty('-3'), 0)

    def test_float_truncated(self):
        # Daichi может прислать «5.7» — округляется к 5.
        self.assertEqual(ws._parse_qty('5.7'), 5)

    def test_garbage(self):
        self.assertEqual(ws._parse_qty('abc'), 0)

    def test_int_input(self):
        self.assertEqual(ws._parse_qty(7), 7)


class NormalizeWarehouseNameTest(SimpleTestCase):

    def test_simferopol_lowercase(self):
        self.assertEqual(ws._normalize_warehouse_name('симферополь склад'), 'Симферополь')

    def test_daichi_typo_simfiropol(self):
        # «Симфирополь» — известная опечатка Daichi.
        self.assertEqual(ws._normalize_warehouse_name('Симфирополь'), 'Симферополь')

    def test_breez_kryim(self):
        # Бриз называет склад «Бриз Крым» — не симфер*, поэтому ОСТАЁТСЯ как есть.
        # Crimea-detection сработает на этапе _CRIMEA_RE, а не нормализации.
        self.assertEqual(ws._normalize_warehouse_name('Бриз Крым'), 'Бриз Крым')

    def test_non_crimea_preserved(self):
        self.assertEqual(ws._normalize_warehouse_name('Краснодар'), 'Краснодар')

    def test_empty(self):
        self.assertEqual(ws._normalize_warehouse_name(''), '')
        self.assertEqual(ws._normalize_warehouse_name(None), '')

    def test_strips_whitespace(self):
        self.assertEqual(ws._normalize_warehouse_name('  Москва  '), 'Москва')


class CrimeaRegexTest(SimpleTestCase):
    """_CRIMEA_RE: подстрочный поиск крымских топонимов."""

    def test_matches_simferopol(self):
        self.assertTrue(ws._CRIMEA_RE.search('Симферополь'))

    def test_matches_sevastopol(self):
        self.assertTrue(ws._CRIMEA_RE.search('Севастополь'))

    def test_matches_breez_kryim(self):
        self.assertTrue(ws._CRIMEA_RE.search('Бриз Крым'))

    def test_matches_yalta(self):
        self.assertTrue(ws._CRIMEA_RE.search('Ялта'))

    def test_matches_evpatoria(self):
        self.assertTrue(ws._CRIMEA_RE.search('Евпатория'))

    def test_matches_feodosia(self):
        self.assertTrue(ws._CRIMEA_RE.search('Феодосия'))

    def test_matches_kerch(self):
        self.assertTrue(ws._CRIMEA_RE.search('Керчь'))

    def test_no_match_moscow(self):
        self.assertIsNone(ws._CRIMEA_RE.search('Москва'))

    def test_no_match_krasnodar(self):
        self.assertIsNone(ws._CRIMEA_RE.search('Краснодар'))


class WriteWarehouseStocksTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплиты', slug='split', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='B', slug='b')

    def _make_product(self, nc):
        return Product.objects.create(
            nc_code=nc, title=f'Product {nc}',
            category=self.category, brand=self.brand,
            price_wholesale=Decimal('1000.00'),
        )

    def test_crimea_priority(self):
        p = self._make_product('NC-1')
        crimea, total, count = ws.write_warehouse_stocks(p, [
            ('Симферополь', 5),
            ('Москва', 100),
        ])
        self.assertEqual(crimea, 5)
        self.assertEqual(total, 105)
        self.assertEqual(count, 2)
        stock = Stock.objects.get(product=p)
        # При наличии Крыма Stock.quantity = крымский остаток, не сумма.
        self.assertEqual(stock.quantity, 5)
        self.assertEqual(stock.warehouse, 'Симферополь')

    def test_no_crimea_total_with_largest_warehouse(self):
        p = self._make_product('NC-2')
        ws.write_warehouse_stocks(p, [
            ('Москва', 10),
            ('Ростов', 30),
        ])
        stock = Stock.objects.get(product=p)
        self.assertEqual(stock.quantity, 40)
        self.assertEqual(stock.warehouse, 'Ростов')

    def test_tie_breaks_deterministically(self):
        # При равном qty выбор главного склада не должен зависеть от порядка
        # ответа API — раньше max() брал первый попавшийся при равенстве.
        p = self._make_product('NC-2B')
        ws.write_warehouse_stocks(p, [
            ('Москва', 10),
            ('Ростов', 10),
        ])
        first = Stock.objects.get(product=p).warehouse
        ws.write_warehouse_stocks(p, [
            ('Ростов', 10),
            ('Москва', 10),
        ])
        second = Stock.objects.get(product=p).warehouse
        self.assertEqual(first, second)

    def test_all_zero_creates_empty_stock(self):
        p = self._make_product('NC-3')
        ws.write_warehouse_stocks(p, [('Москва', 0)])
        stock = Stock.objects.get(product=p)
        self.assertEqual(stock.quantity, 0)
        self.assertEqual(stock.warehouse, '')

    def test_dedup_by_normalized_name(self):
        # Два «симферопольских» имени → один WarehouseStock.
        p = self._make_product('NC-4')
        ws.write_warehouse_stocks(p, [
            ('симферополь склад', 3),
            ('Симфирополь', 10),  # опечатка Daichi → тоже нормализуется в Симферополь
        ])
        self.assertEqual(WarehouseStock.objects.filter(product=p).count(), 1)

    def test_idempotent_on_repeat_call(self):
        p = self._make_product('NC-5')
        warehouses = [('Симферополь', 5), ('Москва', 10)]
        ws.write_warehouse_stocks(p, warehouses)
        ws.write_warehouse_stocks(p, warehouses)
        # Должны остаться ровно 2 строки в WarehouseStock, не 4.
        self.assertEqual(WarehouseStock.objects.filter(product=p).count(), 2)
        # Stock тоже один.
        self.assertEqual(Stock.objects.filter(product=p).count(), 1)

    def test_replace_strategy_clears_old(self):
        p = self._make_product('NC-6')
        ws.write_warehouse_stocks(p, [('Москва', 10), ('Ростов', 5)])
        # Второй вызов с новым набором — старые должны исчезнуть.
        ws.write_warehouse_stocks(p, [('Краснодар', 7)])
        names = set(WarehouseStock.objects.filter(product=p).values_list('warehouse', flat=True))
        self.assertEqual(names, {'Краснодар'})

    def test_empty_input(self):
        p = self._make_product('NC-7')
        crimea, total, count = ws.write_warehouse_stocks(p, [])
        self.assertEqual((crimea, total, count), (0, 0, 0))
        self.assertEqual(WarehouseStock.objects.filter(product=p).count(), 0)
        # Stock всё равно создаётся (с quantity=0).
        self.assertEqual(Stock.objects.get(product=p).quantity, 0)

    def test_negative_qty_clamped(self):
        p = self._make_product('NC-8')
        ws.write_warehouse_stocks(p, [('Симферополь', '-5')])
        # WarehouseStock.quantity = PositiveIntegerField — отрицательные обнуляются.
        wh = WarehouseStock.objects.get(product=p)
        self.assertEqual(wh.quantity, 0)

    def test_over_50_marker_parsed(self):
        p = self._make_product('NC-9')
        ws.write_warehouse_stocks(p, [('Симферополь', '>50')])
        wh = WarehouseStock.objects.get(product=p, warehouse='Симферополь')
        self.assertEqual(wh.quantity, 50)
