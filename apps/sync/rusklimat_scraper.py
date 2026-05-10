import logging
import re
import time

import requests
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)

_LOGIN_URL = 'https://b2b.rusklimat.com/auth/'
_NC_RE = re.compile(r'НС-(\d+)')
_QTY_RE = re.compile(r'(\d[\d\s]*)\s*шт', re.I)


class RusklimatScraper:
    """
    Logs into b2b.rusklimat.com and scrapes stock levels from the AC catalog.
    Matches products by NC code — no UUID mapping required.
    """

    def __init__(self):
        self.login_phone = getattr(settings, 'RUSKLIMAT_LOGIN', '')
        self.password = getattr(settings, 'RUSKLIMAT_PASSWORD', '')
        self.catalog_url = getattr(
            settings, 'RUSKLIMAT_AC_CATALOG_URL',
            'https://b2b.rusklimat.com/catalog/1162450-konditsionery-bytovye/',
        )
        self._session = requests.Session()
        self._session.headers['User-Agent'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )

    def _login(self):
        if not self.login_phone or not self.password:
            logger.error('RUSKLIMAT_LOGIN / RUSKLIMAT_PASSWORD not configured')
            return False

        # Fetch login page to get Bitrix sessid
        resp = self._session.get(_LOGIN_URL, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')
        sessid_tag = soup.find('input', {'name': re.compile(r'sessid', re.I)})
        sessid = sessid_tag['value'] if sessid_tag else ''

        post_data = {
            'AUTH_FORM': 'Y',
            'TYPE': 'AUTH',
            'backurl': self.catalog_url,
            'USER_LOGIN': self.login_phone,
            'USER_PASSWORD': self.password,
        }
        if sessid:
            post_data['sessid'] = sessid

        resp = self._session.post(_LOGIN_URL, data=post_data, timeout=30, allow_redirects=True)

        # On failed login Bitrix stays on /auth/; on success it redirects away
        if '/auth/' in resp.url:
            logger.error('Rusklimat login failed — still on auth page')
            return False

        logger.info('Rusklimat B2B login OK')
        return True

    def _fetch_page(self, page_num):
        url = self.catalog_url if page_num == 1 else f'{self.catalog_url}?PAGEN_1={page_num}'
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    def _last_page_num(self, html):
        """Extract the highest page number from pagination."""
        soup = BeautifulSoup(html, 'html.parser')
        nums = set()
        for tag in soup.find_all('a', href=True):
            m = re.search(r'PAGEN_1=(\d+)', tag['href'])
            if m:
                nums.add(int(m.group(1)))
            elif tag.get_text(strip=True).isdigit():
                nums.add(int(tag.get_text(strip=True)))
        return max(nums, default=1)

    def _parse_stock(self, html):
        """Return {nc_code: quantity} parsed from one catalog page."""
        soup = BeautifulSoup(html, 'html.parser')
        result = {}

        # Find product cards — try common Bitrix class names first
        cards = (
            soup.find_all(class_=re.compile(r'catalog-item|product-item|item_block', re.I))
            or soup.find_all('div', attrs={'data-id': True})
        )

        if cards:
            for card in cards:
                text = card.get_text(' ', strip=True)
                nc_match = _NC_RE.search(text)
                if not nc_match:
                    continue
                nc_code = f'НС-{nc_match.group(1)}'
                qty = _parse_qty(text)
                result[nc_code] = qty
        else:
            # Fallback: collect all NC codes from the entire page body
            body = soup.find('body')
            if body:
                text = body.get_text(' ', strip=True)
                for nc_match in _NC_RE.finditer(text):
                    nc_code = f'НС-{nc_match.group(1)}'
                    if nc_code not in result:
                        result[nc_code] = 0

        return result

    def get_ac_stock(self):
        """
        Login, scrape all pages of the AC catalog and return {nc_code: quantity}.
        """
        if not self._login():
            return {}

        try:
            first_html = self._fetch_page(1)
        except Exception as exc:
            logger.error('Rusklimat: failed to fetch catalog page 1: %s', exc)
            return {}

        total = self._last_page_num(first_html)
        logger.info('Rusklimat catalog: %d pages', total)

        all_stock = self._parse_stock(first_html)

        for page in range(2, total + 1):
            time.sleep(0.5)
            try:
                html = self._fetch_page(page)
                all_stock.update(self._parse_stock(html))
            except Exception as exc:
                logger.error('Rusklimat: page %d error: %s', page, exc)

        logger.info('Rusklimat catalog scraped: %d products', len(all_stock))
        return all_stock


def _parse_qty(text):
    """Extract stock quantity from product card text."""
    qty_match = _QTY_RE.search(text)
    if qty_match:
        return int(qty_match.group(1).replace(' ', ''))
    if re.search(r'в наличии|есть на складе|доступно', text, re.I):
        return 1
    if re.search(r'нет в наличии|под заказ|отсутствует', text, re.I):
        return 0
    return 0
