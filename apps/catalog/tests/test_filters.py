"""Регрессия на NON_RETAIL_Q: реальные аксессуары с прода, которые раньше
проходили мимо фильтра и попадали в каталог сплит-систем при сортировке по
цене (обнаружено на splithome.ru 2026-07-01).
"""
import re

from django.db.models import Q
from django.test import SimpleTestCase, TestCase

from apps.catalog.filters import NON_RETAIL_Q, ProductFilter, _heating_q
from apps.catalog.models import Category, Product


class NonRetailQTest(SimpleTestCase):

    def _regex_matches(self, title):
        # NON_RETAIL_Q — чистый Q(title__iregex=...), проверяем сам паттерн
        # без обращения к БД (SimpleTestCase не даёт транзакций).
        pattern = NON_RETAIL_Q.children[0][1]
        return re.search(pattern, title, re.IGNORECASE) is not None

    def test_ventilation_grille_screen(self):
        self.assertTrue(self._regex_matches('Экран для вентиляционной решётки Ballu Квадра 600'))

    def test_winter_kit(self):
        self.assertTrue(self._regex_matches('Комплект зимний Ballu для полупромышленных сплит-систем'))

    def test_portable_washer(self):
        self.assertTrue(self._regex_matches('Мойка портативная Ballu для кондиционера Aquamaster'))

    def test_water_tank_spare_part(self):
        self.assertTrue(self._regex_matches('Бак для воды BCOOL-05L (DF-AF1301D-47)'))

    def test_evaporative_air_cooler(self):
        # Испарительный охладитель воздуха (BCOOL) — не сплит-система, решение
        # владельца сайта: не показывать в каталоге кондиционеров.
        self.assertTrue(self._regex_matches('Охладитель воздуха Ballu Prime BCOOL-05L PM'))
        self.assertTrue(self._regex_matches('Охладитель воздуха Ballu Cyclone BCOOL-30L CL'))

    def test_bare_grille_word(self):
        self.assertTrue(self._regex_matches('Защитная решётка для наружного блока'))

    def test_real_split_system_not_matched(self):
        self.assertFalse(self._regex_matches(
            'Инверторная сплит-система серии DAIJIN Inverter RAC-I-DA25HP.D01 (комплект)'
        ))

    def test_real_kit_with_komplekt_word_not_matched(self):
        # «комплект» в названии кита (внутр+наруж блок в сборе) — не аксессуар,
        # excludить должны только «комплект зимний».
        self.assertFalse(self._regex_matches('Midea MSAG1-09HRN8-I/MSAG1-09HRN8-OU2 (комплект)'))


class HeatingFilterTest(TestCase):
    """Фасета «Работает на обогрев до» — по Product.heating_min_temp."""

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит-системы', slug='split-heatfilter', sync_enabled=True,
        )

    def _product(self, nc, temp):
        return Product.objects.create(
            nc_code=nc, articul=nc, category=self.category,
            title=f'AC {nc}', slug=f'ac-{nc}', heating_min_temp=temp,
        )

    def test_filter_minus_25_keeps_colder_only(self):
        self._product('NC-H20', -20)
        self._product('NC-H25', -25)
        self._product('NC-H30', -30)
        qs = Product.objects.filter(_heating_q(['-25']))
        self.assertEqual(
            set(qs.values_list('nc_code', flat=True)), {'NC-H25', 'NC-H30'},
        )

    def test_several_thresholds_take_the_warmest(self):
        # Выбраны -20 и -25 → показываем всё, что подходит хотя бы под один,
        # то есть от -20 и холоднее
        self._product('NC-M20', -20)
        self._product('NC-M15', -15)
        qs = Product.objects.filter(_heating_q(['-20', '-25']))
        self.assertEqual(set(qs.values_list('nc_code', flat=True)), {'NC-M20'})

    def test_empty_selection_no_filter(self):
        self.assertEqual(_heating_q([]), Q())

    def test_filterset_applies_heating(self):
        self._product('NC-F25', -25)
        self._product('NC-F15', -15)
        f = ProductFilter({'heating': ['-25']}, queryset=Product.objects.all())
        self.assertEqual(
            set(f.qs.values_list('nc_code', flat=True)), {'NC-F25'},
        )
