from django.urls import path
from . import views

app_name = 'scanner'

urlpatterns = [
    path('', views.scanner_index, name='index'),
    path('<int:event_id>/', views.scanner_view, name='scan'),
    path('validate/', views.validate_ticket, name='validate'),
]
