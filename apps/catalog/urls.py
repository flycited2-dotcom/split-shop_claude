from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    # Подборки — срезы каталога (apps/catalog/collections.py). Маршрут идёт
    # после 'catalog/', чтобы сам каталог не перехватывался как подборка.
    path('catalog/<slug:slug>/', views.collection, name='collection'),
    path('availability/', views.availability, name='availability'),
    re_path(r'^product/(?P<slug>[^/]+)/$', views.product_detail, name='product_detail'),
    # Региональные посадочные — явный список, чтобы маршрут не ловил
    # произвольные /<что-угодно>/ (тексты: apps/catalog/cities.py).
    re_path(r'^(?P<city>simferopol|sevastopol|yalta|evpatoriya|feodosiya|kerch)/$',
            views.city_landing, name='city'),
]
