import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'},
            timeout=5,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error('Telegram send failed: %s', exc)
        return False
