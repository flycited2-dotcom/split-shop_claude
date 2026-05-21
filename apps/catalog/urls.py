from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    path('availability/', views.availability, name='availability'),
    re_path(r'^product/(?P<slug>[^/]+)/$', views.product_detail, name='product_detail'),
]
