"""View-тесты для каталога. Защита HTTP-эндпоинтов от регрессий —
GET /catalog/, GET /product/<slug>/, htmx-фрагменты, /availability/.
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from apps.catalog.models import Brand, Category, Product
from apps.stock.models import Stock, WarehouseStock


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

    def test_catalog_default_only_crimea_stock(self):
        # Правило владельца (2026-05-24): по умолчанию каталог показывает
        # только то, что физически на крымском складе.
        self._make('NC-crimea', warehouse='Симферополь', qty=5)
        self._make('NC-moscow', warehouse='Москва', qty=10)
        r = self.client.get(reverse('catalog'))
        ncs = {p.nc_code for p in r.context['page_obj'].object_list}
        self.assertEqual(ncs, {'NC-crimea'})

    def test_catalog_with_order_param_includes_non_crimea(self):
        # Opt-out через ?with_order=1 — показываем всё, включая «под заказ».
        self._make('NC-crimea', warehouse='Симферополь', qty=5)
        self._make('NC-moscow', warehouse='Москва', qty=10)
        r = self.client.get(reverse('catalog'), {'with_order': '1'})
        ncs = {p.nc_code for p in r.context['page_obj'].object_list}
        self.assertEqual(ncs, {'NC-crimea', 'NC-moscow'})

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


class AvailabilityViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит-системы', slug='split', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='Midea', slug='midea')

    def _make(self, nc, title=None, is_active=True, category=None):
        return Product.objects.create(
            nc_code=nc, articul=nc,
            title=title or f'AC {nc}',
            category=category or self.category,
            brand=self.brand,
            is_active=is_active,
        )

    def setUp(self):
        self.client = Client()

    def test_default_warehouse_simferopol(self):
        p = self._make('NC-1')
        WarehouseStock.objects.create(product=p, warehouse='Симферополь', quantity=3)
        r = self.client.get(reverse('availability'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'NC-1')
        self.assertEqual(r.context['warehouse'], 'Симферополь')
        self.assertEqual(r.context['total_items'], 1)
        self.assertEqual(r.context['total_qty'], 3)

    def test_zero_quantity_excluded(self):
        p = self._make('NC-1')
        WarehouseStock.objects.create(product=p, warehouse='Симферополь', quantity=0)
        r = self.client.get(reverse('availability'))
        self.assertEqual(r.context['total_items'], 0)
        self.assertNotContains(r, 'NC-1')

    def test_other_warehouse_excluded_by_default(self):
        p = self._make('NC-msk')
        WarehouseStock.objects.create(product=p, warehouse='Москва', quantity=10)
        r = self.client.get(reverse('availability'))
        self.assertEqual(r.context['total_items'], 0)

    def test_warehouse_query_param(self):
        p = self._make('NC-msk')
        WarehouseStock.objects.create(product=p, warehouse='Москва', quantity=10)
        r = self.client.get(reverse('availability'), {'warehouse': 'Москва'})
        self.assertEqual(r.context['warehouse'], 'Москва')
        self.assertEqual(r.context['total_items'], 1)
        self.assertContains(r, 'NC-msk')

    def test_inactive_product_excluded(self):
        p = self._make('NC-1', is_active=False)
        WarehouseStock.objects.create(product=p, warehouse='Симферополь', quantity=5)
        r = self.client.get(reverse('availability'))
        self.assertEqual(r.context['total_items'], 0)

    def test_disabled_category_excluded(self):
        disabled = Category.objects.create(
            title='Off', slug='off', sync_enabled=False,
        )
        p = self._make('NC-1', category=disabled)
        WarehouseStock.objects.create(product=p, warehouse='Симферополь', quantity=5)
        r = self.client.get(reverse('availability'))
        self.assertEqual(r.context['total_items'], 0)

    def test_multi_split_blocks_excluded(self):
        p = self._make('NC-1', title='Мульти-блок внутренний 9')
        WarehouseStock.objects.create(product=p, warehouse='Симферополь', quantity=5)
        r = self.client.get(reverse('availability'))
        self.assertEqual(r.context['total_items'], 0)

    def test_empty_state_renders_friendly_message(self):
        r = self.client.get(reverse('availability'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'сейчас пусто')

    def test_ordering_by_quantity_desc(self):
        p1 = self._make('NC-A')
        p2 = self._make('NC-B')
        WarehouseStock.objects.create(product=p1, warehouse='Симферополь', quantity=2)
        WarehouseStock.objects.create(product=p2, warehouse='Симферополь', quantity=10)
        r = self.client.get(reverse('availability'))
        stocks = list(r.context['stocks'])
        self.assertEqual(stocks[0].product.nc_code, 'NC-B')
        self.assertEqual(stocks[1].product.nc_code, 'NC-A')
