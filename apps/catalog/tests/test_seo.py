"""SEO-аудит 06.11.2026: canonical от SITE_URL, латиница в адресах товаров,
301 со старых кириллических адресов, H1 главной, sitemap без мёртвых адресов.
"""
from decimal import Decimal

from django.test import Client, TestCase, override_settings

from apps.catalog.models import Brand, Category, Product
from apps.catalog.sitemaps import ProductSitemap
from apps.catalog.slugs import to_latin
from apps.stock.models import Stock


class ToLatinTest(TestCase):

    def test_cyrillic_nc_code(self):
        self.assertEqual(to_latin('electrolux-ewh-80-citadel-НС-1181388'),
                         'electrolux-ewh-80-citadel-ns-1181388')

    def test_ascii_untouched(self):
        for s in ('ballu-blci_d-48hn1_24y', 'euroklimat-eksf-25his-OF-25HIS'):
            self.assertEqual(to_latin(s), s)

    def test_idempotent(self):
        s = to_latin('аэроник-щ-ё-ъ-ü²')
        self.assertTrue(s.isascii())
        self.assertEqual(to_latin(s), s)

    def test_cyrillic_brand(self):
        self.assertEqual(to_latin('ресанта-спн-13500'), 'resanta-spn-13500')


@override_settings(SITE_URL='https://splithome.ru', ALLOWED_HOSTS=['*'])
class SeoViewsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(title='Сплит-системы', slug='split', sync_enabled=True)
        cls.brand = Brand.objects.create(title='Electrolux', slug='electrolux')
        cls.product = Product.objects.create(
            nc_code='НС-1181388', articul='EWH 80 Citadel', category=cls.category,
            brand=cls.brand, title='Electrolux EWH 80', ric=Decimal('30000'), is_active=True,
        )
        # главная без товара в крымском наличии не рендерится (featured.0)
        Stock.objects.create(product=cls.product, quantity=3, warehouse='Симферополь')
        # Товар Бриза после миграции 0015: был …-НС-1181388, стал …-ns-1181388
        cls.migrated = Product.objects.create(
            nc_code='НС-1181389', articul='x', category=cls.category, brand=cls.brand,
            title='Electrolux EWH 80 Citadel', ric=Decimal('30000'), is_active=True,
            slug='electrolux-ewh-80-citadel-ns-1181389',
        )
        cls.inactive = Product.objects.create(
            nc_code='НС-2', articul='OLD', category=cls.category, brand=cls.brand,
            title='Electrolux OLD', ric=Decimal('1'), is_active=False,
        )

    def setUp(self):
        self.client = Client()

    def test_new_slug_is_latin(self):
        self.assertTrue(self.product.slug.isascii())
        self.assertTrue(self.product.slug.endswith('-ns-1181388'))

    def test_old_cyrillic_url_redirects_301(self):
        r = self.client.get('/product/electrolux-ewh-80-citadel-НС-1181389/', secure=True)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r['Location'], '/product/electrolux-ewh-80-citadel-ns-1181389/')
        self.assertEqual(self.client.get(r['Location'], secure=True).status_code, 200)

    def test_old_url_of_inactive_is_404(self):
        r = self.client.get('/product/electrolux-old-НС-2/', secure=True)
        self.assertEqual(r.status_code, 404)

    def test_canonical_ignores_www_host(self):
        r = self.client.get('/', HTTP_HOST='www.splithome.ru', secure=True)
        self.assertContains(r, '<link rel="canonical" href="https://splithome.ru/">', html=False)
        self.assertNotContains(r, 'https://www.splithome.ru')

    def test_home_h1(self):
        body = self.client.get('/', secure=True).content.decode()
        self.assertEqual(body.count('<h1'), 1)
        self.assertIn('Кондиционеры и сплит-системы в Крыму с установкой</h1>', body)

    def test_sitemap_only_live_latin_urls(self):
        items = list(ProductSitemap().items())
        self.assertIn(self.product, items)
        self.assertNotIn(self.inactive, items)
        body = self.client.get('/sitemap.xml', HTTP_HOST='www.splithome.ru', secure=True).content.decode()
        self.assertIn(f'<loc>https://splithome.ru/product/{self.product.slug}/</loc>', body)
        self.assertNotIn('www.splithome.ru', body)
        self.assertNotIn('НС', body)

    def test_robots_uses_site_url(self):
        body = self.client.get('/robots.txt', HTTP_HOST='www.splithome.ru', secure=True).content.decode()
        self.assertIn('Sitemap: https://splithome.ru/sitemap.xml', body)
        self.assertIn('Sitemap: https://splithome.ru/articles/sitemap.xml', body)
