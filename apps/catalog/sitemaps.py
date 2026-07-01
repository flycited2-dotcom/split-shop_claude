from django.contrib.sitemaps import Sitemap
from django.urls import reverse, NoReverseMatch
from .models import Product, Category, Brand


class ProductSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return Product.objects.filter(is_active=True, kind=Product.KIND_SPLIT_SYSTEM)

    def location(self, obj):
        return f'/product/{obj.slug}/'

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return f'{reverse("catalog")}?category={obj.pk}'


class StaticViewSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    # Имена URL статических страниц. items() отфильтровывает имена, которые
    # не резолвятся, чтобы один отсутствующий маршрут (как было с 'brands' —
    # такого url нет, reverse() бросал NoReverseMatch и ронял весь sitemap в
    # HTTP 500) больше не ломал карту сайта целиком.
    NAMES = ['home', 'catalog', 'selection', 'installation',
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
