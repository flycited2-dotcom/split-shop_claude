from django.urls import path
from . import views

urlpatterns = [
    path('quick-order/', views.quick_order_submit, name='quick_order_submit'),
    path('selection/', views.selection_submit, name='selection_submit'),
    path('installation/', views.installation_submit, name='installation_submit'),
]
