"""Юнит-тесты пагинации _fetch_all_productparams (apps/sync/daichi_catalog.py).

Регрессия: раньше останов зависел от resp['total_count']. Если API отдаёт
его пустым/некорректным (0, None, отсутствует) — забор данных обрывался
после первой же страницы, часть фото/описаний Daichi не подтягивалась.
"""
from django.test import SimpleTestCase

from apps.sync.daichi_catalog import _fetch_all_productparams


class FakeClient:
    """Отдаёт заранее заданные страницы вместо реального Daichi API."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_productparams(self, page_size=500, page=1):
        self.calls.append(page)
        return self.pages[page - 1]


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
