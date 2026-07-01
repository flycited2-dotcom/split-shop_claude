from django.test import SimpleTestCase

from apps.catalog.classify import classify_title
from apps.catalog.models import Product


class ClassifyTitleTest(SimpleTestCase):

    def test_real_split_system(self):
        self.assertEqual(
            classify_title('Инверторная сплит-система серии DAIJIN Inverter RAC-I-DA25HP.D01 (комплект)'),
            Product.KIND_SPLIT_SYSTEM,
        )

    def test_multi_split_block(self):
        self.assertEqual(
            classify_title('Мульти-блок внутренний 9'),
            Product.KIND_MULTI_SPLIT_BLOCK,
        )

    def test_accessory(self):
        self.assertEqual(
            classify_title('Экран для вентиляционной решётки Ballu Квадра 600'),
            Product.KIND_ACCESSORY,
        )

    def test_evaporative_cooler_is_accessory(self):
        self.assertEqual(
            classify_title('Охладитель воздуха Ballu Prime BCOOL-05L PM'),
            Product.KIND_ACCESSORY,
        )

    def test_empty_title_defaults_to_split_system(self):
        self.assertEqual(classify_title(''), Product.KIND_SPLIT_SYSTEM)
        self.assertEqual(classify_title(None), Product.KIND_SPLIT_SYSTEM)

    def test_multi_split_takes_priority_over_non_retail(self):
        # На случай если оба паттерна совпадут — порядок проверки в
        # classify_title важен: мульти-блок проверяется первым.
        self.assertEqual(
            classify_title('Мульти сплит блок внутренний с кронштейном'),
            Product.KIND_MULTI_SPLIT_BLOCK,
        )
