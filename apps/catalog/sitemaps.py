from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product, Category, Brand
from .filters import MULTI_SPLIT_BLOCK_Q


class ProductSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return Product.objects.filter(is_active=True).exclude(MULTI_SPLIT_BLOCK_Q)

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
        return f'/catalog/?category={obj.pk}'


class StaticViewSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return ['home', 'catalog', 'brands', 'selection', 'installation',
                'delivery', 'payment', 'contacts', 'warranty', 'about']

    def location(self, item):
        return reverse(item)
