from unittest.mock import patch

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
