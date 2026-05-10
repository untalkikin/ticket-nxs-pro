from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.pos_view, name='pos'),
    path('ticket/<int:sale_id>/', views.ticket_print, name='ticket_print'),
]
