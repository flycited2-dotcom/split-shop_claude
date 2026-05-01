from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.catalog.urls')),
    path('auth/', include('apps.accounts.urls')),
    path('account/', include('apps.accounts.urls_account')),
    path('cart/', include('apps.orders.urls')),
    path('export/', include('apps.export.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
