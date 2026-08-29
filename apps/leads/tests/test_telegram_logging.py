from unittest.mock import Mock, patch

import requests

from django.test import SimpleTestCase, override_settings

from apps.notifications.telegram import send_telegram


class TelegramLoggingTest(SimpleTestCase):
    @override_settings(
        TELEGRAM_BOT_TOKEN='secret-token',
        TELEGRAM_CHAT_ID='123',
        TELEGRAM_API_URL='https://api.telegram.test',
    )
    @patch('apps.notifications.telegram.logger.error')
    @patch('apps.notifications.telegram.requests.post', side_effect=ConnectionError('secret-token'))
    def test_network_error_does_not_log_token_or_exception_text(self, post, log_error):
        self.assertFalse(send_telegram('message'))
        log_error.assert_called_once_with('Telegram send failed (%s)', 'ConnectionError')

    @override_settings(
        TELEGRAM_BOT_TOKEN='secret-token',
        TELEGRAM_CHAT_ID='123',
        TELEGRAM_API_URL='https://api.telegram.test',
        TELEGRAM_CONNECT_ATTEMPTS=3,
    )
    @patch('apps.notifications.telegram.time.sleep')
    @patch('apps.notifications.telegram.requests.post')
    def test_connect_timeout_retries_until_success(self, post, sleep):
        response = Mock()
        response.raise_for_status.return_value = None
        post.side_effect = [requests.ConnectTimeout(), response]

        self.assertTrue(send_telegram('message'))
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(0.25)

    @override_settings(
        TELEGRAM_BOT_TOKEN='secret-token',
        TELEGRAM_CHAT_ID='123',
        TELEGRAM_API_URL='https://api.telegram.test',
        TELEGRAM_CONNECT_ATTEMPTS=3,
    )
    @patch('apps.notifications.telegram.time.sleep')
    @patch('apps.notifications.telegram.requests.post',
           side_effect=requests.ConnectTimeout)
    def test_connect_timeout_stops_after_configured_attempts(self, post, sleep):
        self.assertFalse(send_telegram('message'))
        self.assertEqual(post.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @override_settings(
        TELEGRAM_BOT_TOKEN='secret-token',
        TELEGRAM_CHAT_ID='123',
        TELEGRAM_API_URL='https://api.telegram.test',
    )
    @patch('apps.notifications.telegram.requests.post',
           side_effect=requests.ReadTimeout)
    def test_read_timeout_is_not_retried_to_avoid_duplicates(self, post):
        self.assertFalse(send_telegram('message'))
        post.assert_called_once()
