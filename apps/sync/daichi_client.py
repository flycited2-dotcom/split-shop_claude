import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class DaichiClient:
    """HTTP client for api.daichi.ru/b2b/v1/ — Daichi Business partner API.

    All endpoints are GET with access-token as a query parameter.
    Responses follow {"Result": ..., "Time": float} or
    {"Result": {"error": "...", "success": false}, ...} on error.
    """

    def __init__(self):
        self.base_url = settings.DAICHI_BASE_URL.rstrip('/')
        self.access_token = settings.DAICHI_ACCESS_TOKEN
        self.timeout = 120  # /products/get returns ~5 MB

    def _get(self, path, params=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        merged = {'access-token': self.access_token}
        if params:
            merged.update({k: v for k, v in params.items() if v is not None})
        try:
            resp = requests.get(url, params=merged, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            logger.error('Daichi API timeout: %s', url)
            return None
        except requests.exceptions.JSONDecodeError as exc:
            logger.error('Daichi API JSON decode error %s: %s', url, exc)
            return None
        except requests.exceptions.HTTPError as exc:
            logger.error('Daichi API HTTP error %s: %s', url, exc)
            return None
        except requests.exceptions.RequestException as exc:
            logger.error('Daichi API request failed %s: %s', url, exc)
            return None

        result = data.get('Result') if isinstance(data, dict) else None
        if isinstance(result, dict) and result.get('success') is False:
            logger.warning('Daichi API error for %s: %s', url, result.get('error'))
            return None
        return result

    def get_stores(self):
        """Returns list of {NAME, XML_ID, IS_DEFAULT}."""
        result = self._get('stores/get/')
        return result if isinstance(result, list) else []

    def get_sections(self):
        """Returns {total_count, data: [{ID, NAME, ACTIVE, PARENT_SECTION_ID}]}."""
        result = self._get('sections/get/')
        if isinstance(result, dict):
            return result.get('data') or []
        return []

    def get_products(self, store_id='default', filter_name=None, filter_xml_id=None):
        """Returns dict {product_id: {NAME, XML_ID, PARAMS, PRICES, STORE}}.

        Daichi returns one big object for the whole store — no pagination here.
        """
        params = {'store-id': store_id}
        if filter_name:
            params['filter[NAME]'] = filter_name
        if filter_xml_id:
            params['filter[XML_ID]'] = filter_xml_id
        result = self._get('products/get/', params=params)
        return result if isinstance(result, dict) else {}

    def get_productparams(self, page_size=100, page=1, filter_name=None, filter_xml_id=None,
                          show_empty_params=False):
        """Returns {total_count, data: {product_id: {ATTR_*, ...}}}."""
        params = {
            'page-size': page_size,
            'page': page,
            'show-empty-params': 'true' if show_empty_params else 'false',
        }
        if filter_name:
            params['filter[NAME]'] = filter_name
        if filter_xml_id:
            params['filter[XML_ID]'] = filter_xml_id
        result = self._get('productparams/get/', params=params)
        return result if isinstance(result, dict) else {}
