from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    re_path(r'^product/(?P<slug>[^/]+)/$', views.product_detail, name='product_detail'),
    path('brands/', views.brands_list, name='brands'),
]
