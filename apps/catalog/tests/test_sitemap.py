"""Регрессия на sitemap.xml. Баг 09.06.2026: StaticViewSitemap содержал имя
'brands', для которого нет URL → reverse() бросал NoReverseMatch → весь
sitemap отдавал HTTP 500. Поисковики, заходя по ссылке из robots.txt, видели
ошибку вместо карты сайта.
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch

from apps.catalog.models import Brand, Category, Product
from apps.catalog.sitemaps import CategorySitemap, ProductSitemap, StaticViewSitemap
from apps.stock.models import Stock


class SitemapTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(title='Сплит-системы', slug='split')
        cls.brand = Brand.objects.create(title='Midea', slug='midea')
        p = Product.objects.create(
            nc_code='NC-SM', articul='NC-SM',
            category=cls.category, brand=cls.brand,
            title='AC NC-SM', ric=Decimal('30000'), is_active=True,
        )
        Stock.objects.create(product=p, quantity=5, warehouse='Симферополь')
        cls.accessory = Product.objects.create(
            nc_code='NC-ACC', articul='NC-ACC',
            category=cls.category, brand=cls.brand,
            title='Экран для вентиляционной решётки Ballu Квадра 600',
            ric=Decimal('1500'), is_active=True,
        )

    def setUp(self):
        self.client = Client()

    def test_sitemap_returns_200(self):
        # secure=True — обойти SECURE_SSL_REDIRECT (в prod-настройках http→https
        # отдаёт 301), чтобы дойти до самого view карты.
        r = self.client.get('/sitemap.xml', secure=True)
        self.assertEqual(r.status_code, 200)

    def test_sitemap_contains_urls(self):
        r = self.client.get('/sitemap.xml', secure=True)
        self.assertIn(b'<url>', r.content)
        # товар попал в карту
        self.assertIn(b'/product/', r.content)

    def test_all_static_names_resolve(self):
        """Каждое имя из StaticViewSitemap.items() обязано резолвиться —
        иначе location() упадёт при рендере карты.
        """
        for name in StaticViewSitemap().items():
            try:
                reverse(name)
            except NoReverseMatch:  # pragma: no cover
                self.fail(f"sitemap содержит нерезолвящееся имя url: {name!r}")

    def test_product_sitemap_excludes_accessories(self):
        # Аксессуары (не NON_RETAIL по regex) не должны попадать в sitemap —
        # раньше исключался только MULTI_SPLIT_BLOCK_Q, аксессуары индексировались.
        items = list(ProductSitemap().items())
        self.assertNotIn(self.accessory, items)

    def test_category_sitemap_location_uses_reverse(self):
        location = CategorySitemap().location(self.category)
        self.assertEqual(location, f'/catalog/?category={self.category.pk}')
