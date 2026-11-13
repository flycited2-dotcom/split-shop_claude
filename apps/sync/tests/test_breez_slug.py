"""Адрес товара из синхронизации Бриза должен быть латинским.

13.11.2026: sync_products раз в 4 часа записывал slug с кодом «НС-…»
кириллицей и тем самым откатывал миграцию 0015 — 1 660 активных товаров
из sitemap отдавали 404 (product_detail не открывает кириллический slug).
"""
from django.test import SimpleTestCase

from apps.sync.tasks import _breez_slug


class BreezSlugTest(SimpleTestCase):

    def test_nc_code_is_latin(self):
        self.assertEqual(
            _breez_slug('Hisense', 'AS-07HW4SYDTG035В', 'Сплит', 'НС-1414392'),
            'hisense-as-07hw4sydtg035v-ns-1414392')

    def test_result_is_ascii(self):
        slug = _breez_slug('Аэроник', 'АС-12', 'Кондиционер', 'НС-1')
        self.assertTrue(slug.isascii(), slug)

    def test_without_brand_uses_title(self):
        self.assertEqual(_breez_slug('', '', 'Сплит-система Ballu', 'НС-7'),
                         'split-sistema-ballu-ns-7')

    def test_same_as_migration_0015(self):
        # Старый кириллический адрес должен переводиться в тот же slug,
        # что пишет синхронизация, — иначе редирект product_detail не сработает.
        from apps.catalog.slugs import to_latin
        old = 'hisense-as-07hw4sydtg035в-НС-1414392'
        self.assertEqual(to_latin(old),
                         _breez_slug('Hisense', 'AS-07HW4SYDTG035В', '', 'НС-1414392'))

    def test_empty_fallback(self):
        self.assertEqual(_breez_slug('', '', '', 'НС-5'), 'ns-5')
