from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.leads import views as views_leads


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
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
