from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse, NoReverseMatch
from django.utils.encoding import iri_to_uri

from .models import Product, Category, Brand


class SiteSitemap(Sitemap):
    """Домен и протокол — из SITE_URL, а не из запроса: запрос на www или
    по IP иначе отдаст карту с чужим доменом."""
    protocol = 'https'

    def get_domain(self, site=None):
        return urlsplit(settings.SITE_URL).netloc


class ProductSitemap(SiteSitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        # Тот же фильтр, что и в product_detail (is_active), плюс только
        # сплит-системы: в карте нет адресов, которые отдают 404.
        return (Product.objects.filter(is_active=True, kind=Product.KIND_SPLIT_SYSTEM)
                .only('slug', 'updated_at').order_by('pk'))

    def location(self, obj):
        # iri_to_uri: если кириллица всё же осталась в slug, в <loc> уйдёт
        # percent-encoding, а не сырые символы.
        return iri_to_uri(f'/product/{obj.slug}/')

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(SiteSitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return f'{reverse("catalog")}?category={obj.pk}'


class CollectionSitemap(SiteSitemap):
    """Подборки — срезы каталога со своими SEO-страницами (collections.py)."""
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        from .collections import COLLECTIONS
        return list(COLLECTIONS.values())

    def location(self, obj):
        return reverse('collection', args=[obj.slug])


class StaticViewSitemap(SiteSitemap):
    changefreq = 'monthly'
    priority = 0.5

    # Имена URL статических страниц. items() отфильтровывает имена, которые
    # не резолвятся, чтобы один отсутствующий маршрут (как было с 'brands' —
    # такого url нет, reverse() бросал NoReverseMatch и ронял весь sitemap в
    # HTTP 500) больше не ломал карту сайта целиком.
    NAMES = ['home', 'catalog', 'selection', 'installation', 'service',
             'delivery', 'payment', 'contacts', 'warranty', 'about', 'privacy']

    def items(self):
        resolvable = []
        for name in self.NAMES:
            try:
                reverse(name)
            except NoReverseMatch:
                continue
            resolvable.append(name)
        return resolvable

    def location(self, item):
        return reverse(item)
