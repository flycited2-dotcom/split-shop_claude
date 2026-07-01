"""Юнит-тесты пагинации _fetch_all_productparams (apps/sync/daichi_catalog.py).

Регрессия: раньше останов зависел от resp['total_count']. Если API отдаёт
его пустым/некорректным (0, None, отсутствует) — забор данных обрывался
после первой же страницы, часть фото/описаний Daichi не подтягивалась.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.sync.daichi_catalog import _fetch_all_productparams, _prefetch_kit_wholesales


class FakeClient:
    """Отдаёт заранее заданные страницы вместо реального Daichi API."""

    def __init__(self, pages=None, targeted_price=None):
        self.pages = pages or []
        self.calls = []
        self.targeted_price = targeted_price

    def get_productparams(self, page_size=500, page=1):
        self.calls.append(page)
        return self.pages[page - 1]

    def get_products(self, store_id='default', filter_xml_id=None):
        # Точечный запрос для _recover_kit_wholesale: либо отдаёт цену, либо пусто.
        if self.targeted_price is None:
            return {}
        return {
            '1': {'XML_ID': filter_xml_id, 'PRICES': {
                'p': {'XML_ID': 'BASE', 'PRICE': str(self.targeted_price), 'CURRENCY': 'RUR'},
            }},
        }


def _page(items, total_count=None):
    return {
        'data': {str(i): {'XML_ID': xml_id} for i, xml_id in enumerate(items)},
        'total_count': total_count,
    }


class FetchAllProductparamsTest(SimpleTestCase):

    def test_stops_on_partial_page_with_correct_total(self):
        client = FakeClient([_page(['a', 'b'], total_count=2)])
        pp_map = _fetch_all_productparams(client, page_size=500)
        self.assertEqual(set(pp_map), {'a', 'b'})
        self.assertEqual(client.calls, [1])

    def test_continues_across_full_pages(self):
        page_size = 2
        client = FakeClient([
            _page(['a', 'b'], total_count=3),
            _page(['c'], total_count=3),
        ])
        pp_map = _fetch_all_productparams(client, page_size=page_size)
        self.assertEqual(set(pp_map), {'a', 'b', 'c'})
        self.assertEqual(client.calls, [1, 2])

    def test_survives_missing_total_count(self):
        # total_count отсутствует/0 — раньше это обрывало забор после 1-й
        # страницы, даже если пришла полная страница (значит есть ещё данные).
        page_size = 2
        client = FakeClient([
            _page(['a', 'b'], total_count=0),
            _page(['c'], total_count=0),
        ])
        pp_map = _fetch_all_productparams(client, page_size=page_size)
        self.assertEqual(set(pp_map), {'a', 'b', 'c'})
        self.assertEqual(client.calls, [1, 2])

    def test_empty_response_stops_immediately(self):
        client = FakeClient([_page([], total_count=0)])
        pp_map = _fetch_all_productparams(client, page_size=500)
        self.assertEqual(pp_map, {})
        self.assertEqual(client.calls, [1])


def _kit_entry(xml_id, name='KIT-1/KIT-2'):
    return {
        'XML_ID': xml_id,
        'NAME': name,
        'PARAMS': {'ATTR_L_GOODTYPE': 'Комплект'},
        'PRICES': {},  # BASE пуст — типичный кейс из массового дампа
    }


class PrefetchKitWholesalesTest(SimpleTestCase):
    """Регрессия: если ни точечный запрос, ни сумма блоков не восстановили
    опт — раньше это тонуло в INFO-логе без явного счётчика."""

    def test_recovered_via_targeted_fetch_no_error_logged(self):
        products = {'1': _kit_entry('kit-xml-1')}
        client = FakeClient(targeted_price=Decimal('12345'))
        with self.assertLogs('apps.sync.daichi_catalog', level='INFO') as cm:
            recovered = _prefetch_kit_wholesales(client, 'default', products)
        self.assertEqual(recovered, {'kit-xml-1': Decimal('12345')})
        self.assertFalse(any(r.levelname == 'ERROR' for r in cm.records))

    def test_both_recovery_paths_fail_logs_error(self):
        # Точечный запрос пуст (targeted_price=None), а компоненты 'KIT-1'/'KIT-2'
        # отсутствуют среди products — сумма блоков тоже не считается.
        products = {'1': _kit_entry('kit-xml-2')}
        client = FakeClient(targeted_price=None)
        with self.assertLogs('apps.sync.daichi_catalog', level='INFO') as cm:
            recovered = _prefetch_kit_wholesales(client, 'default', products)
        self.assertEqual(recovered, {})
        error_logs = [r for r in cm.records if r.levelname == 'ERROR']
        self.assertEqual(len(error_logs), 1)
        self.assertIn('kit-xml-2', error_logs[0].getMessage())
