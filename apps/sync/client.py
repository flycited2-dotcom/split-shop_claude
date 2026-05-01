import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BreezClient:
    """HTTP client for api.breez.ru API."""

    def __init__(self):
        self.base_url = settings.BREEZ_BASE_URL.rstrip('/')
        self.headers = {
            'Authorization': settings.BREEZ_AUTH_HEADER,
            'Accept': 'application/json',
        }
        self.timeout = 60

    def _get(self, endpoint, params=None):
        """Make a GET request and return a list of items, or [] on error."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            resp = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and 'error' in data:
                logger.warning("Breez API returned error for %s: %s", url, data['error'])
                return []
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # API returns {id: {...item...}} — flatten to [{id, ...item}]
                result = []
                for key, val in data.items():
                    if isinstance(val, dict):
                        item = {'id': key}
                        item.update(val)
                        result.append(item)
                return result
            logger.warning("Breez API unexpected response type for %s: %s", url, type(data))
            return []
        except requests.exceptions.Timeout:
            logger.error("Breez API timeout for %s", url)
            return []
        except requests.exceptions.JSONDecodeError as exc:
            logger.error("Breez API JSON decode error for %s: %s", url, exc)
            return []
        except requests.exceptions.HTTPError as exc:
            logger.error("Breez API HTTP error for %s: %s", url, exc)
            return []
        except requests.exceptions.RequestException as exc:
            logger.error("Breez API request failed for %s: %s", url, exc)
            return []

    def get_categories(self):
        return self._get('categories/')

    def get_brands(self):
        return self._get('brands/')

    def get_products(self):
        return self._get('products/')

    def get_tech_for_category(self, category_id):
        return self._get('tech/', params={'category': category_id})

    def get_tech_for_product(self, product_nc):
        return self._get('tech/', params={'id': product_nc})

    def get_stock(self):
        return self._get('leftoversnew/')

    def get_stock_by_nc(self, nc_code):
        return self._get('leftovers/', params={'nc': nc_code})
