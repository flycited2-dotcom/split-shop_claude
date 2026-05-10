from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.contrib.sitemaps.views import sitemap
from apps.leads import views as views_leads
from apps.catalog.sitemaps import ProductSitemap, CategorySitemap, StaticViewSitemap

sitemaps = {
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'static': StaticViewSitemap,
}


def robots_txt(request):
    lines = [
        'User-agent: *',
        'Disallow: /admin/',
        'Disallow: /auth/',
        'Disallow: /account/',
        'Disallow: /cart/',
        'Disallow: /export/',
        f'Sitemap: https://{request.get_host()}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.catalog.urls')),
    path('auth/', include('apps.accounts.urls')),
    path('account/', include('apps.accounts.urls_account')),
    path('cart/', include('apps.orders.urls')),
    path('export/', include('apps.export.urls')),
    path('leads/', include('apps.leads.urls')),
    path('selection/', views_leads.selection_page, name='selection'),
    path('installation/', views_leads.installation_page, name='installation'),
    # Static pages
    path('delivery/', TemplateView.as_view(template_name='pages/delivery.html'), name='delivery'),
    path('payment/', TemplateView.as_view(template_name='pages/payment.html'), name='payment'),
    path('contacts/', TemplateView.as_view(template_name='pages/contacts.html'), name='contacts'),
    path('warranty/', TemplateView.as_view(template_name='pages/warranty.html'), name='warranty'),
    path('about/', TemplateView.as_view(template_name='pages/about.html'), name='about'),
    # SEO
    path('robots.txt', robots_txt),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
