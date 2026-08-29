"""Тесты правила отбора подборки «Тепловые насосы».

Товар остаётся в своей категории — подборка это срез поверх каталога,
поэтому проверяем именно queryset-правило, а не принадлежность категории.
"""
from django.test import TestCase

from apps.catalog.collections import COLLECTIONS, get_collection
from apps.catalog.models import Brand, Category, Product


class HeatPumpCollectionRuleTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Бытовые сплит-системы', slug='split-coll', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='FUNAI', slug='funai-coll')

    def _product(self, nc, temp=None, declared=False, kind=Product.KIND_SPLIT_SYSTEM):
        return Product.objects.create(
            nc_code=nc, articul=nc, category=self.category, brand=self.brand,
            title=f'AC {nc}', slug=f'ac-{nc}',
            heating_min_temp=temp, is_heat_pump=declared, kind=kind,
        )

    def _selected(self):
        rule = COLLECTIONS['heat-pumps'].rule
        return set(Product.objects.filter(rule).values_list('nc_code', flat=True))

    def test_minus_20_included(self):
        self._product('NC-20', temp=-20)
        self.assertIn('NC-20', self._selected())

    def test_minus_25_included(self):
        self._product('NC-25', temp=-25)
        self.assertIn('NC-25', self._selected())

    def test_minus_15_excluded(self):
        self._product('NC-15', temp=-15)
        self.assertNotIn('NC-15', self._selected())

    def test_no_temp_excluded(self):
        self._product('NC-NONE')
        self.assertNotIn('NC-NONE', self._selected())

    def test_declared_included_without_temp(self):
        self._product('NC-DECL', declared=True)
        self.assertIn('NC-DECL', self._selected())

    def test_accessory_excluded_even_if_cold(self):
        self._product('NC-ACC', temp=-30, kind=Product.KIND_ACCESSORY)
        self.assertNotIn('NC-ACC', self._selected())

    def test_multi_split_block_excluded(self):
        self._product('NC-MULTI', temp=-25, kind=Product.KIND_MULTI_SPLIT_BLOCK)
        self.assertNotIn('NC-MULTI', self._selected())

    def test_get_collection_unknown_slug(self):
        self.assertIsNone(get_collection('no-such-collection'))

    def test_get_collection_known_slug(self):
        self.assertEqual(get_collection('heat-pumps').slug, 'heat-pumps')
