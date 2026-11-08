"""Региональные посадочные (ТЗ по SEO, п. 5) и мелочи аудита."""
from decimal import Decimal

from django.test import Client, TestCase, override_settings

from apps.catalog.cities import CITIES
from apps.catalog.models import Brand, Category, Product
from apps.stock.models import Stock


@override_settings(SITE_URL='https://splithome.ru', ALLOWED_HOSTS=['*'])
class CityLandingTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(title='Сплит-системы', slug='split', sync_enabled=True)
        brand = Brand.objects.create(title='Midea', slug='midea')
        cls.p = Product.objects.create(
            nc_code='NC-CITY', articul='MSAG-09', category=cat, brand=brand,
            title='Midea MSAG-09', ric=Decimal('30000'), is_active=True,
        )
        Stock.objects.create(product=cls.p, quantity=4, warehouse='Симферополь')

    def setUp(self):
        self.client = Client()

    def test_all_cities_render(self):
        for slug, c in CITIES.items():
            r = self.client.get(f'/{slug}/', secure=True)
            self.assertEqual(r.status_code, 200, slug)
            body = r.content.decode()
            self.assertIn(f'Кондиционеры {c.where}: продажа и установка</h1>', body)
            self.assertIn(f'"areaServed": {{"@type": "City", "name": "{c.name}"}}', body)
            self.assertIn(f'<link rel="canonical" href="https://splithome.ru/{slug}/">', body)
            self.assertIn('hx-post="/leads/installation/"', body)
            self.assertIn('/quiz/', body)

    def test_popular_models(self):
        self.assertContains(self.client.get('/sevastopol/', secure=True), 'Midea MSAG-09')

    def test_unknown_city_404(self):
        self.assertEqual(self.client.get('/moskva/', secure=True).status_code, 404)

    def test_sitemap_has_cities_not_category_queries(self):
        body = self.client.get('/sitemap.xml', secure=True).content.decode()
        for slug in CITIES:
            self.assertIn(f'<loc>https://splithome.ru/{slug}/</loc>', body)
        self.assertNotIn('?category=', body)

    def test_footer_links_cities(self):
        self.assertContains(self.client.get('/contacts/', secure=True), 'href="/kerch/"')


@override_settings(ALLOWED_HOSTS=['*'])
class HomeEmptyStockTest(TestCase):
    """Без единого товара в крымском наличии главная отдавала 500 (featured.0)."""

    def test_home_without_stock(self):
        self.assertEqual(Client().get('/', secure=True).status_code, 200)
