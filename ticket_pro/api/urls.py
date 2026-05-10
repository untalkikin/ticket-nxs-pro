from django.urls import path
from . import views

urlpatterns = [
    # Events
    path('events/', views.EventListView.as_view(), name='api-event-list'),
    path('events/<int:event_id>/', views.EventDetailView.as_view(), name='api-event-detail'),
    path('events/<int:event_id>/seats/<int:ticket_type_id>/', views.AvailableSeatsView.as_view(), name='api-available-seats'),

    # Mercado Pago flow
    path('orders/', views.CreateOrderView.as_view(), name='api-create-order'),
    path('orders/<int:order_id>/', views.OrderStatusView.as_view(), name='api-order-status'),
    path('payment/webhook/', views.PaymentWebhookView.as_view(), name='api-payment-webhook'),
    path('payment/result/', views.PaymentResultView.as_view(), name='api-payment-result'),

    # Direct POS sale (no payment gateway)
    path('sales/', views.DirectSaleView.as_view(), name='api-direct-sale'),

    # Ticket validation
    path('tickets/<str:ticket_number>/', views.ValidateTicketView.as_view(), name='api-validate-ticket'),
]
