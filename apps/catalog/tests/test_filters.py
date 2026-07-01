"""Регрессия на NON_RETAIL_Q: реальные аксессуары с прода, которые раньше
проходили мимо фильтра и попадали в каталог сплит-систем при сортировке по
цене (обнаружено на splithome.ru 2026-07-01).
"""
import re

from django.test import SimpleTestCase

from apps.catalog.filters import NON_RETAIL_Q


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
