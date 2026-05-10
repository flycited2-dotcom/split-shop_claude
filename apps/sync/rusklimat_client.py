import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_REMAINS_BASE = 'https://remains.b2b-one.rusklimat.com/api/v1'


class RusklimatClient:
    """Client for Rusklimat b2b-one REST API (JWT auth)."""

    def __init__(self):
        self.token = getattr(settings, 'RUSKLIMAT_JWT_TOKEN', '')
        self.contractor_guid = getattr(settings, 'RUSKLIMAT_CONTRACTOR_GUID', '')
        self._session = requests.Session()
        self._session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        self.timeout = 60

    def _get(self, url, params=None):
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            logger.error('Rusklimat HTTP %s for %s', exc.response.status_code, url)
            return None
        except Exception as exc:
            logger.error('Rusklimat error for %s: %s', url, exc)
            return None

    def get_remains(self):
        """Returns list of {productGuid, totalRemain, isAvailable} for all products."""
        if not self.contractor_guid:
            logger.error('RUSKLIMAT_CONTRACTOR_GUID not configured')
            return []
        url = f'{_REMAINS_BASE}/remains/{self.contractor_guid}/'
        data = self._get(url)
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ('items', 'data', 'remains', 'result'):
                if isinstance(data.get(key), list):
                    return data[key]
        logger.warning('Rusklimat remains: unexpected format %s', type(data))
        return []

    def find_product_by_nc(self, nc_code):
        """Try to find productGuid by NS/NC code. Returns guid str or None."""
        for params in ({'ns': nc_code}, {'nc': nc_code}, {'nsCode': nc_code}):
            data = self._get(f'{_REMAINS_BASE}/products/', params=params)
            if isinstance(data, list) and data:
                item = data[0]
                guid = item.get('productGuid') or item.get('guid') or item.get('id')
                if guid:
                    return str(guid)
            if isinstance(data, dict):
                guid = data.get('productGuid') or data.get('guid') or data.get('id')
                if guid:
                    return str(guid)
        return None

    def find_product_by_articul(self, articul):
        """Try to find productGuid by vendor article. Returns guid str or None."""
        for params in ({'article': articul}, {'articul': articul}, {'vendorCode': articul}):
            data = self._get(f'{_REMAINS_BASE}/products/', params=params)
            if isinstance(data, list) and data:
                item = data[0]
                guid = item.get('productGuid') or item.get('guid') or item.get('id')
                if guid:
                    return str(guid)
        return None
