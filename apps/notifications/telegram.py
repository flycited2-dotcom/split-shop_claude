import json
import logging
import time

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
    attempts = max(1, int(getattr(settings, 'TELEGRAM_CONNECT_ATTEMPTS', 3)))
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.post(
                f'{base_url}/bot{token}/sendMessage',
                data=payload,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                timeout=(3, 5),
            )
            resp.raise_for_status()
            return True
        except requests.ConnectTimeout:
            # No connection was established, so retrying cannot duplicate a
            # message already accepted by Telegram. Do not retry read timeouts:
            # in that case Telegram may have accepted the message already.
            if attempt < attempts:
                logger.warning(
                    'Telegram connect timed out; retrying (%s/%s)',
                    attempt, attempts,
                )
                time.sleep(0.25 * attempt)
                continue
            logger.error(
                'Telegram send failed after %s attempts (ConnectTimeout)', attempts,
            )
            return False
        except Exception as exc:
            # requests includes the full URL in its exception text. The URL contains
            # the bot token, so never write the exception message to production logs.
            logger.error('Telegram send failed (%s)', type(exc).__name__)
            return False
