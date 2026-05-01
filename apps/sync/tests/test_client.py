from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from apps.sync.client import BreezClient


FAKE_SETTINGS = {
    'BREEZ_BASE_URL': 'https://api.breez.ru/v1/',
    'BREEZ_AUTH_HEADER': 'Basic dGVzdDp0ZXN0',
}


@override_settings(**FAKE_SETTINGS)
class BreezClientTest(TestCase):

    def setUp(self):
        self.client = BreezClient()

    @patch('apps.sync.client.requests.get')
    def test_get_categories_returns_list(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: [{'id': 1, 'title': 'Кондиционеры', 'chpu': 'konditsionery'}],
        )
        mock_get.return_value.raise_for_status = Mock()
        result = self.client.get_categories()
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'Кондиционеры')

    @patch('apps.sync.client.requests.get')
    def test_returns_empty_list_on_api_error(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {'error': 'Нет данных'},
        )
        mock_get.return_value.raise_for_status = Mock()
        result = self.client.get_categories()
        self.assertEqual(result, [])

    @patch('apps.sync.client.requests.get')
    def test_returns_empty_list_on_timeout(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout()
        result = self.client.get_brands()
        self.assertEqual(result, [])

    @patch('apps.sync.client.requests.get')
    def test_returns_empty_list_on_http_error(self, mock_get):
        import requests as req
        mock_resp = Mock()
        mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError('403')
        mock_get.return_value = mock_resp
        result = self.client.get_products()
        self.assertEqual(result, [])

    @patch('apps.sync.client.requests.get')
    def test_get_stock_calls_leftoversnew(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: [{'nc': 'ABC123', 'quantity': 5}],
        )
        mock_get.return_value.raise_for_status = Mock()
        result = self.client.get_stock()
        self.assertEqual(len(result), 1)
        called_url = mock_get.call_args[0][0]
        self.assertIn('leftoversnew', called_url)

    @patch('apps.sync.client.requests.get')
    def test_get_stock_by_nc_passes_nc_param(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: [{'nc': 'ABC123', 'quantity': 2}],
        )
        mock_get.return_value.raise_for_status = Mock()
        self.client.get_stock_by_nc('ABC123')
        called_params = mock_get.call_args[1]['params']
        self.assertEqual(called_params, {'nc': 'ABC123'})

    @patch('apps.sync.client.requests.get')
    def test_returns_empty_list_on_json_error(self, mock_get):
        import requests as req
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.side_effect = req.exceptions.JSONDecodeError('', '', 0)
        mock_get.return_value = mock_resp
        result = self.client.get_categories()
        self.assertEqual(result, [])

    @patch('apps.sync.client.requests.get')
    def test_auth_header_sent(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: [],
        )
        mock_get.return_value.raise_for_status = Mock()
        self.client.get_brands()
        called_headers = mock_get.call_args[1]['headers']
        self.assertIn('Authorization', called_headers)
        self.assertEqual(called_headers['Authorization'], 'Basic dGVzdDp0ZXN0')
