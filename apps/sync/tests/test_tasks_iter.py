"""Юнит-тесты для apps/sync/tasks._iter_leftoversnew.

Чистый generator, поддерживающий 3 формата ответа Breez API
`/v1/leftoversnew/`.
"""
from django.test import SimpleTestCase

from apps.sync.tasks import _iter_leftoversnew


class IterLeftoversNewTest(SimpleTestCase):

    def test_format1_dict_with_nc_keys(self):
        # Текущий формат: ключ — NC-код, значение — товар.
        data = {
            'НС-1': {'stocks': [{'stock': 'Симф', 'quantity': 5}]},
            'НС-2': {'stocks': [{'stock': 'Москва', 'quantity': 10}]},
        }
        items = list(_iter_leftoversnew(data))
        self.assertEqual(len(items), 2)
        ncs = {it['nc'] for it in items}
        self.assertEqual(ncs, {'НС-1', 'НС-2'})

    def test_format1_existing_nc_not_overwritten(self):
        # Если у товара уже есть nc — ключ не перетирает (setdefault).
        data = {'НС-key': {'nc': 'НС-explicit', 'stocks': []}}
        items = list(_iter_leftoversnew(data))
        self.assertEqual(items[0]['nc'], 'НС-explicit')

    def test_format1_skip_non_dict_values(self):
        data = {'НС-1': {'nc': 'НС-1'}, 'НС-2': 'just a string'}
        items = list(_iter_leftoversnew(data))
        self.assertEqual(len(items), 1)

    def test_format2_list_of_single_key_dicts(self):
        # Формат из инструкции 2026-05-19.
        data = [
            {'НС-1': {'stocks': [{'stock': 'Симф', 'quantity': 3}]}},
            {'НС-2': {'stocks': []}},
        ]
        items = list(_iter_leftoversnew(data))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['nc'], 'НС-1')
        self.assertEqual(items[1]['nc'], 'НС-2')

    def test_format3_flat_list_with_id(self):
        data = [{'id': 'НС-1', 'stocks': []}]
        items = list(_iter_leftoversnew(data))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], 'НС-1')

    def test_format3_flat_list_with_nc(self):
        data = [{'nc': 'НС-1', 'stocks': []}]
        items = list(_iter_leftoversnew(data))
        self.assertEqual(len(items), 1)

    def test_format3_skips_entries_without_nc_or_id(self):
        data = [{'random': 'value'}]
        items = list(_iter_leftoversnew(data))
        self.assertEqual(items, [])

    def test_list_skips_non_dict_entries(self):
        data = ['just a string', None, {'nc': 'НС-1', 'stocks': []}]
        items = list(_iter_leftoversnew(data))
        self.assertEqual(len(items), 1)

    def test_empty_dict(self):
        self.assertEqual(list(_iter_leftoversnew({})), [])

    def test_empty_list(self):
        self.assertEqual(list(_iter_leftoversnew([])), [])

    def test_none_input_yields_nothing(self):
        # Не словарь и не список → пустой генератор.
        self.assertEqual(list(_iter_leftoversnew(None)), [])

    def test_format2_multi_key_dict_falls_to_format3_check(self):
        # Если в list-entry больше одного ключа, формат 2 не сработает —
        # проверяется на наличие 'nc' или 'id' (формат 3).
        data = [{'НС-1': {'foo': 1}, 'extra': 'value'}]  # 2 ключа, ни nc, ни id
        items = list(_iter_leftoversnew(data))
        self.assertEqual(items, [])
