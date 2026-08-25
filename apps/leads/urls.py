from django.urls import path
from . import views

urlpatterns = [
    path('quick-order/', views.quick_order_submit, name='quick_order_submit'),
    path('selection/', views.selection_submit, name='selection_submit'),
    path('installation/', views.installation_submit, name='installation_submit'),
    path('service/', views.service_submit, name='service_submit'),
    path('quiz-step/', views.quiz_step, name='quiz_step'),
    path('quiz-lead/<int:quiz_id>/', views.quiz_lead, name='quiz_lead'),
]
