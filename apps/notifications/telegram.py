import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return False
    base_url = getattr(settings, 'TELEGRAM_API_URL', 'https://api.telegram.org').rstrip('/')
    # Явно UTF-8 + Content-Type charset=utf-8. requests при json=... ставит
    # Content-Type без charset, и socat-proxy / промежуточный слой ломал
    # кириллицу (баг 28 мая — заявки приходили с ??? в Telegram).
    # ensure_ascii=False даёт нативный UTF-8 в body (не \uXXXX escapes).
    payload = json.dumps(
        {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'},
        ensure_ascii=False,
    ).encode('utf-8')
    try:
        resp = requests.post(
            f'{base_url}/bot{token}/sendMessage',
            data=payload,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=5,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        # requests includes the full URL in its exception text. The URL contains
        # the bot token, so never write the exception message to production logs.
        logger.error('Telegram send failed (%s)', type(exc).__name__)
        return False
