import logging
import os
import tempfile
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)

_BASE_URL = 'https://b2b.rusklimat.com'
_PARTNER_PAGE = _BASE_URL + '/personal/internet_partner/'
_DOWNLOAD_TPL = (
    _BASE_URL
    + '/personal/internet_partner/download.php'
    '?filename=catalog.yml&dirload=/personalprice/{guid}/'
    '&custom_file_name=price_list.yml'
)


class RusklimatStockSync:
    """
    Downloads the personalised YML price list (contains 'Всего на складах')
    and returns {nc_code: quantity} for all products.
    """

    def __init__(self):
        self.login_phone = getattr(settings, 'RUSKLIMAT_LOGIN', '')
        self.password = getattr(settings, 'RUSKLIMAT_PASSWORD', '')
        self._session = requests.Session()
        self._session.headers['User-Agent'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )

    def _login(self):
        if not self.login_phone or not self.password:
            logger.error('RUSKLIMAT_LOGIN / RUSKLIMAT_PASSWORD not set')
            return False
        resp = self._session.get(_BASE_URL + '/auth/', timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        tag = soup.find('input', {'name': 'sessionId'})
        sessid = tag['value'] if tag else ''
        resp = self._session.post(
            _BASE_URL + '/api/v1/user/signIn/',
            data={'sessionId': sessid, 'phone': self.login_phone, 'password': self.password},
            timeout=15,
        )
        ok = resp.json().get('code') == 200
        if not ok:
            logger.error('Rusklimat login failed: %s', resp.text[:200])
        return ok

    def _get_price_guid(self):
        """Extract the personalised price directory GUID from the Internet Partner page."""
        import re
        resp = self._session.get(_PARTNER_PAGE, timeout=30)
        m = re.search(r'/personalprice/([0-9a-f-]{36})/', resp.text)
        if m:
            return m.group(1)
        logger.error('Could not extract price GUID from Internet Partner page')
        return None

    def _download_yml(self, guid):
        """Stream YML to a temp file. Returns path."""
        url = _DOWNLOAD_TPL.format(guid=guid)
        logger.info('Downloading Rusklimat price YML...')
        resp = self._session.get(url, timeout=300, stream=True)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.yml')
        for chunk in resp.iter_content(chunk_size=65536):
            tmp.write(chunk)
        tmp.close()
        size_mb = os.path.getsize(tmp.name) / 1024 / 1024
        logger.info('Downloaded %.1f MB to %s', size_mb, tmp.name)
        return tmp.name

    def get_stock(self):
        """Login, download price YML, parse {nc_code: quantity}."""
        if not self._login():
            return {}

        guid = self._get_price_guid()
        if not guid:
            return {}

        tmp_path = self._download_yml(guid)
        stock = {}
        try:
            tree = ET.parse(tmp_path)
            root = tree.getroot()
            for offer in root.iter('offer'):
                nc_code = None
                qty = 0
                for param in offer.findall('param'):
                    name = param.get('name', '')
                    val = (param.text or '').strip()
                    if name == 'НС-код':
                        nc_code = val
                    elif name == 'Всего на складах':
                        try:
                            qty = int(val)
                        except (ValueError, TypeError):
                            qty = 0
                if nc_code:
                    stock[nc_code] = qty
        finally:
            os.unlink(tmp_path)

        logger.info('Rusklimat stock parsed: %d products', len(stock))
        return stock
