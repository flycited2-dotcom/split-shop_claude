"""Юнит-тесты для apps/sync/rusklimat_auth — JWT auto-refresh.

Все сетевые вызовы мокаются. cache замокан через override_settings или
clear() в setUp.
"""
from unittest.mock import patch, MagicMock

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from apps.sync import rusklimat_auth


class _MockResp:
    def __init__(self, status_code=200, json_data=None, text=''):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


@override_settings(
    RUSKLIMAT_LOGIN='user@example.com',
    RUSKLIMAT_PASSWORD='secret',
    RUSKLIMAT_JWT_TOKEN='',
)
class FetchJwtTest(TestCase):

    def setUp(self):
        cache.delete(rusklimat_auth.CACHE_KEY)

    @patch('apps.sync.rusklimat_auth.requests.post')
    def test_fetch_jwt_success_caches_token(self, mock_post):
        mock_post.return_value = _MockResp(
            200, json_data={'data': {'jwtToken': 'eyJ-abc'}},
        )
        token = rusklimat_auth.fetch_jwt()

        self.assertEqual(token, 'eyJ-abc')
        self.assertEqual(cache.get(rusklimat_auth.CACHE_KEY), 'eyJ-abc')
        # Заголовок User-Agent — обязателен по спецификации.
        _args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['headers']['User-Agent'], 'catalog-ip')
        self.assertEqual(kwargs['json'], {'login': 'user@example.com', 'password': 'secret'})

    @patch('apps.sync.rusklimat_auth.requests.post')
    def test_fetch_jwt_raises_on_4xx(self, mock_post):
        mock_post.return_value = _MockResp(401, text='Invalid user/password')
        with self.assertRaises(rusklimat_auth.RusklimatAuthError):
            rusklimat_auth.fetch_jwt()
        self.assertIsNone(cache.get(rusklimat_auth.CACHE_KEY))

    @patch('apps.sync.rusklimat_auth.requests.post')
    def test_fetch_jwt_raises_on_network_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError('boom')
        with self.assertRaises(rusklimat_auth.RusklimatAuthError):
            rusklimat_auth.fetch_jwt()

    @patch('apps.sync.rusklimat_auth.requests.post')
    def test_fetch_jwt_raises_on_malformed_payload(self, mock_post):
        mock_post.return_value = _MockResp(200, json_data={'unexpected': 'shape'})
        with self.assertRaises(rusklimat_auth.RusklimatAuthError):
            rusklimat_auth.fetch_jwt()


@override_settings(
    RUSKLIMAT_LOGIN='',
    RUSKLIMAT_PASSWORD='',
    RUSKLIMAT_JWT_TOKEN='',
)
class FetchJwtMissingCredsTest(TestCase):

    def setUp(self):
        cache.delete(rusklimat_auth.CACHE_KEY)

    def test_fetch_jwt_without_creds_raises(self):
        with self.assertRaises(rusklimat_auth.RusklimatAuthError):
            rusklimat_auth.fetch_jwt()


class GetJwtTest(TestCase):

    def setUp(self):
        cache.delete(rusklimat_auth.CACHE_KEY)

    def test_get_jwt_returns_cached_token(self):
        cache.set(rusklimat_auth.CACHE_KEY, 'cached-token', timeout=60)
        with patch('apps.sync.rusklimat_auth.fetch_jwt') as m:
            self.assertEqual(rusklimat_auth.get_jwt(), 'cached-token')
            m.assert_not_called()

    @override_settings(
        RUSKLIMAT_LOGIN='u', RUSKLIMAT_PASSWORD='p',
        RUSKLIMAT_JWT_TOKEN='',
    )
    @patch('apps.sync.rusklimat_auth.requests.post')
    def test_get_jwt_fetches_when_cache_empty(self, mock_post):
        mock_post.return_value = _MockResp(
            200, json_data={'data': {'jwtToken': 'fresh-token'}},
        )
        self.assertEqual(rusklimat_auth.get_jwt(), 'fresh-token')
        self.assertEqual(cache.get(rusklimat_auth.CACHE_KEY), 'fresh-token')

    @override_settings(
        RUSKLIMAT_LOGIN='', RUSKLIMAT_PASSWORD='',
        RUSKLIMAT_JWT_TOKEN='legacy-static',
    )
    def test_get_jwt_legacy_fallback(self):
        # Если LOGIN/PASSWORD не заданы — отдаём статичный токен из .env.
        token = rusklimat_auth.get_jwt()
        self.assertEqual(token, 'legacy-static')

    @override_settings(
        RUSKLIMAT_LOGIN='u', RUSKLIMAT_PASSWORD='p',
        RUSKLIMAT_JWT_TOKEN='legacy-static',
    )
    @patch('apps.sync.rusklimat_auth.requests.post')
    def test_get_jwt_fallback_to_legacy_when_fetch_fails(self, mock_post):
        # Креды заданы, но auth-эндпоинт упал (например, неверный пароль).
        # Чтобы не ронять sync — используем legacy токен.
        mock_post.return_value = _MockResp(200, json_data={'code': 401, 'errors': []})
        token = rusklimat_auth.get_jwt()
        self.assertEqual(token, 'legacy-static')

    @override_settings(
        RUSKLIMAT_LOGIN='', RUSKLIMAT_PASSWORD='',
        RUSKLIMAT_JWT_TOKEN='',
    )
    def test_get_jwt_no_creds_no_legacy_raises(self):
        with self.assertRaises(rusklimat_auth.RusklimatAuthError):
            rusklimat_auth.get_jwt()


class InvalidateJwtTest(SimpleTestCase):

    def test_invalidate_clears_cache(self):
        cache.set(rusklimat_auth.CACHE_KEY, 'x', timeout=60)
        rusklimat_auth.invalidate_jwt()
        self.assertIsNone(cache.get(rusklimat_auth.CACHE_KEY))


@override_settings(
    RUSKLIMAT_LOGIN='u', RUSKLIMAT_PASSWORD='p',
    RUSKLIMAT_JWT_TOKEN='',
)
class RestClient401RetryTest(TestCase):
    """Интеграционный тест: RusklimatRestClient получает 401, рефрешит JWT,
    повторяет запрос. Один retry — если второй раз 401, бросает JWTExpired.
    """

    def setUp(self):
        cache.delete(rusklimat_auth.CACHE_KEY)

    @patch('apps.sync.rusklimat_auth.requests.post')
    @patch('apps.sync.rusklimat_rest.requests.Session')
    def test_401_triggers_refresh_and_retry(self, mock_session_cls, mock_auth_post):
        # session.get вернёт сначала 401, потом 200.
        session = MagicMock()
        session.headers = {}
        session.get.side_effect = [
            _MockResp(401, text='token expired'),
            _MockResp(200, json_data={'requestKey': 'KEY-1'}),
        ]
        mock_session_cls.return_value = session

        # Auth-эндпоинт отдаёт новый токен.
        mock_auth_post.return_value = _MockResp(
            200, json_data={'data': {'jwtToken': 'fresh-token'}},
        )

        # Стартовый кэш — какой-то старый токен.
        cache.set(rusklimat_auth.CACHE_KEY, 'old-token', timeout=60)

        from apps.sync.rusklimat_rest import RusklimatRestClient
        client = RusklimatRestClient()
        key = client.request_key()

        self.assertEqual(key, 'KEY-1')
        self.assertEqual(session.get.call_count, 2)
        # Authorization-заголовок обновился на свежий токен.
        self.assertEqual(session.headers['Authorization'], 'fresh-token')
        # Auth-эндпоинт вызван один раз (refresh).
        mock_auth_post.assert_called_once()

    @patch('apps.sync.rusklimat_auth.requests.post')
    @patch('apps.sync.rusklimat_rest.requests.Session')
    def test_second_401_raises_jwt_expired(self, mock_session_cls, mock_auth_post):
        session = MagicMock()
        session.headers = {}
        session.get.side_effect = [
            _MockResp(401),
            _MockResp(401),  # повторно тоже 401 — сдаёмся
        ]
        mock_session_cls.return_value = session
        mock_auth_post.return_value = _MockResp(
            200, json_data={'data': {'jwtToken': 'fresh-token'}},
        )
        cache.set(rusklimat_auth.CACHE_KEY, 'old-token', timeout=60)

        from apps.sync.rusklimat_rest import RusklimatJWTExpired, RusklimatRestClient
        client = RusklimatRestClient()
        with self.assertRaises(RusklimatJWTExpired):
            client.request_key()
