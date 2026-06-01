#!/usr/bin/env python3
"""
Standalone daily stock report.
Fetches stock + wholesale prices from Breez API, sends to Telegram.

Usage:
    python daily_stock_report.py

Dependencies (pip install):
    requests

Config: .env file in the same directory (or real env vars):
    BREEZ_AUTH_HEADER   — "Basic <base64>" — из настроек аккаунта Бриз
    BREEZ_BASE_URL      — https://api.breez.ru/v1/
    TELEGRAM_BOT_TOKEN  — токен бота от @BotFather
    TELEGRAM_CHAT_ID    — твой Telegram user/chat ID

Cron (ежедневно в 09:00):
    0 9 * * * /usr/bin/python3 /path/to/daily_stock_report.py >> /var/log/daily_stock.log 2>&1
"""

import os
import sys
import logging
from datetime import date
from pathlib import Path

import requests

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_dotenv():
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        return
    with open(env_file, encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key not in os.environ:
                os.environ[key] = val


def get_config():
    _load_dotenv()
    required = ['BREEZ_AUTH_HEADER', 'BREEZ_BASE_URL', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        sys.exit(f"ERROR: Missing env vars: {', '.join(missing)}")
    return {
        'breez_auth': os.environ['BREEZ_AUTH_HEADER'],
        'breez_url':  os.environ['BREEZ_BASE_URL'].rstrip('/') + '/',
        'tg_token':   os.environ['TELEGRAM_BOT_TOKEN'],
        'tg_chat_id': os.environ['TELEGRAM_CHAT_ID'],
    }


# ---------------------------------------------------------------------------
# Breez API client
# ---------------------------------------------------------------------------

class BreezClient:
    def __init__(self, base_url: str, auth_header: str):
        self.base_url = base_url
        self.headers = {'Authorization': auth_header, 'Accept': 'application/json'}
        self.timeout = 60

    def _get(self, endpoint: str, params=None) -> list:
        url = self.base_url + endpoint
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as exc:
            log.error("Breez API error [%s]: %s", endpoint, exc)
            return []

    def get_stock(self) -> list:
        return self._get('leftoversnew/')

    def get_products(self) -> list:
        return self._get('products/')


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def tg_send(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()


def tg_send_long(token: str, chat_id: str, header: str, pre_lines: list[str]):
    """
    Sends header + pre_lines as one or more messages.
    pre_lines are wrapped in <pre>...</pre> blocks (monospace table).
    Each message stays under Telegram's 4096-char limit.
    """
    MAX = 4000
    first = True

    def flush(lines, is_first):
        block = '<pre>' + '\n'.join(lines) + '</pre>'
        msg = (header + '\n\n' + block) if is_first else block
        tg_send(token, chat_id, msg)

    chunk: list[str] = []
    overhead = len(header) + len('<pre></pre>') + 4  # approx header overhead

    for line in pre_lines:
        candidate_len = overhead + sum(len(l) + 1 for l in chunk) + len(line) + 1
        if candidate_len > MAX and chunk:
            flush(chunk, first)
            first = False
            overhead = len('<pre></pre>') + 2
            chunk = [line]
        else:
            chunk.append(line)

    if chunk:
        flush(chunk, first)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _fmt_price(val) -> str:
    if val is None:
        return '—'
    try:
        return f"{float(val):,.0f} ₽".replace(',', ' ')  # narrow no-break space
    except (ValueError, TypeError):
        return str(val)


def build_and_send(stock_data: list, products_data: list, token: str, chat_id: str):
    # Index products by nc_code
    products: dict = {}
    for p in products_data:
        nc = p.get('nc') or p.get('nc_code')
        if nc:
            products[nc] = p

    rows = []
    for item in stock_data:
        nc = item.get('nc') or item.get('nc_code')
        if not nc:
            continue
        qty = int(item.get('quantity') or 0)
        if qty <= 0:
            continue

        prod = products.get(nc, {})
        rows.append({
            'articul':   prod.get('articul') or nc,
            'title':     prod.get('title', ''),
            'brand':     prod.get('brand', ''),
            'qty':       qty,
            'price':     prod.get('price'),        # оптовая входящая
            'warehouse': item.get('warehouse', ''),
        })

    rows.sort(key=lambda r: (r['brand'].lower(), r['articul']))

    today       = date.today().strftime('%d.%m.%Y')
    total_units = sum(r['qty'] for r in rows)

    header = (
        f"<b>📦 Остатки Бриз — {today}</b>\n"
        f"Позиций: <b>{len(rows)}</b>   "
        f"Единиц всего: <b>{total_units}</b>"
    )

    # Table header
    col_art   = 14
    col_qty   = 6
    col_price = 13
    divider   = '-' * (col_art + col_qty + col_price + 38)

    table_header = (
        f"{'Артикул':<{col_art}} {'Кол':>{col_qty}}  {'Опт. цена':>{col_price}}  Название"
    )

    pre_lines = [table_header, divider]
    for r in rows:
        name = (r['title'][:34] + '…') if len(r['title']) > 35 else r['title']
        line = (
            f"{r['articul']:<{col_art}} "
            f"{r['qty']:>{col_qty}}  "
            f"{_fmt_price(r['price']):>{col_price}}  "
            f"{name}"
        )
        pre_lines.append(line)

    if not rows:
        tg_send(token, chat_id, header + '\n\n<i>Нет позиций с остатком.</i>')
        return

    tg_send_long(token, chat_id, header, pre_lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
    )

    cfg    = get_config()
    client = BreezClient(cfg['breez_url'], cfg['breez_auth'])

    log.info("Fetching stock...")
    stock = client.get_stock()
    log.info("  → %d records", len(stock))

    log.info("Fetching products...")
    products = client.get_products()
    log.info("  → %d records", len(products))

    log.info("Building report and sending to Telegram...")
    build_and_send(stock, products, cfg['tg_token'], cfg['tg_chat_id'])
    log.info("Done.")


if __name__ == '__main__':
    main()
