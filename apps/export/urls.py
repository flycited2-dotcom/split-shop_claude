from django.urls import path
from . import views

urlpatterns = [
    path('price/excel/', views.export_excel, name='export_excel'),
    path('price/pdf/', views.export_pdf, name='export_pdf'),
]
