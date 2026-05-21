"""View-тесты для каталога. Защита HTTP-эндпоинтов от регрессий —
GET /catalog/, GET /product/<slug>/, htmx-фрагменты.
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from apps.catalog.models import Brand, Category, Product
from apps.stock.models import Stock


class CatalogViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит-системы', slug='split', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='Midea', slug='midea')

    def _make(self, nc, btu_calc=9, qty=5, warehouse='Симферополь', is_active=True):
        p = Product.objects.create(
            nc_code=nc, articul=nc,
            category=self.category, brand=self.brand,
            title=f'AC {nc}', ric=Decimal('30000'),
            btu_calc=btu_calc, is_active=is_active,
        )
        Stock.objects.create(product=p, quantity=qty, warehouse=warehouse)
        return p

    def setUp(self):
        self.client = Client()

    def test_catalog_returns_200(self):
        self._make('NC-1')
        r = self.client.get(reverse('catalog'))
        self.assertEqual(r.status_code, 200)

    def test_catalog_filter_by_btu(self):
        self._make('NC-9', btu_calc=9)
        self._make('NC-12', btu_calc=12)
        r = self.client.get(reverse('catalog'), {'btu': '9'})
        self.assertEqual(r.status_code, 200)
        page = r.context['page_obj']
        ncs = {p.nc_code for p in page.object_list}
        self.assertEqual(ncs, {'NC-9'})

    def test_catalog_full_page_when_no_hx_header(self):
        self._make('NC-1')
        r = self.client.get(reverse('catalog'))
        # Полная страница содержит layout (base.html → <html>, <head>).
        self.assertContains(r, '<html', status_code=200)

    def test_catalog_fragment_when_hx_request(self):
        self._make('NC-1')
        r = self.client.get(reverse('catalog'), HTTP_HX_REQUEST='true')
        self.assertEqual(r.status_code, 200)
        # Фрагмент НЕ содержит <html> — это partial.
        self.assertNotContains(r, '<html')

    def test_catalog_excludes_inactive(self):
        self._make('NC-active', is_active=True)
        self._make('NC-inactive', is_active=False)
        r = self.client.get(reverse('catalog'))
        ncs = {p.nc_code for p in r.context['page_obj'].object_list}
        self.assertEqual(ncs, {'NC-active'})

    def test_catalog_in_stock_filter_crimea_only(self):
        self._make('NC-crimea', warehouse='Симферополь', qty=5)
        self._make('NC-moscow', warehouse='Москва', qty=10)
        r = self.client.get(reverse('catalog'), {'in_stock': 'on'})
        ncs = {p.nc_code for p in r.context['page_obj'].object_list}
        # Только крымский считается «в наличии».
        self.assertEqual(ncs, {'NC-crimea'})

    def test_product_detail_returns_200(self):
        p = self._make('NC-1')
        r = self.client.get(reverse('product_detail', args=[p.slug]))
        self.assertEqual(r.status_code, 200)

    def test_product_detail_404_for_missing(self):
        r = self.client.get(reverse('product_detail', args=['no-such-slug']))
        self.assertEqual(r.status_code, 404)

    def test_product_detail_404_for_inactive(self):
        p = self._make('NC-1', is_active=False)
        r = self.client.get(reverse('product_detail', args=[p.slug]))
        self.assertEqual(r.status_code, 404)

    def test_catalog_pagination_works(self):
        for i in range(20):
            self._make(f'NC-{i}')
        r = self.client.get(reverse('catalog'), {'page': '2'})
        self.assertEqual(r.status_code, 200)
        # Paginator 16/page → на page=2 минимум 4.
        self.assertTrue(len(r.context['page_obj'].object_list) >= 4)
