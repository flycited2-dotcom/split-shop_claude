"""Тесты парсера минимальной температуры обогрева.

SimpleTestCase — БД не нужна: parse_min_heating_temp чистая функция.
Кейсы взяты из реальных значений прода (разведка 2026-08-28): Бриз отдаёт
диапазон «-20 ~ +24», Daichi «-25~30» без пробелов, Rusklimat одно число.
"""
from django.test import SimpleTestCase

from apps.catalog.heating import parse_min_heating_temp


class ParseMinHeatingTempTest(SimpleTestCase):

    def test_breez_range(self):
        self.assertEqual(parse_min_heating_temp('-20 ~ +24'), -20)

    def test_daichi_range_without_spaces(self):
        self.assertEqual(parse_min_heating_temp('-25~30'), -25)

    def test_rusklimat_single_number(self):
        self.assertEqual(parse_min_heating_temp('-15'), -15)

    def test_unicode_minus(self):
        # Rusklimat местами присылает юникодный минус U+2212
        self.assertEqual(parse_min_heating_temp('−20 ~ +24'), -20)

    def test_en_dash_separator(self):
        self.assertEqual(parse_min_heating_temp('-30 – +24'), -30)

    def test_positive_only_range_is_none(self):
        # «+17 ~ +30» — машина на обогрев в минус не работает, в подборку не идёт
        self.assertIsNone(parse_min_heating_temp('+17 ~ +30'))

    def test_empty_is_none(self):
        self.assertIsNone(parse_min_heating_temp(''))

    def test_none_is_none(self):
        self.assertIsNone(parse_min_heating_temp(None))

    def test_garbage_is_none(self):
        self.assertIsNone(parse_min_heating_temp('нет данных'))

    def test_degree_suffix(self):
        self.assertEqual(parse_min_heating_temp('-22 °C'), -22)
