import uuid
from django.db import models
from django.utils import timezone


def _generate_ticket_number():
    return uuid.uuid4().hex[:10].upper()


class Sale(models.Model):
    event = models.ForeignKey(
        'evente.Event', on_delete=models.PROTECT, related_name='sales', verbose_name='Evento'
    )
    sale_date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de venta')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Total')
    buyer_name = models.CharField(max_length=200, verbose_name='Nombre del comprador')
    buyer_email = models.EmailField(blank=True, verbose_name='Correo electrónico')
    buyer_phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-sale_date']

    def __str__(self):
        return f"Venta #{self.pk} — {self.buyer_name}"

    @property
    def total_tickets(self):
        return sum(t.quantity for t in self.tickets.all())


class Ticket(models.Model):
    sale = models.ForeignKey(
        Sale, related_name='tickets', on_delete=models.CASCADE, verbose_name='Venta'
    )
    ticket_type = models.ForeignKey(
        'evente.TicketType', on_delete=models.PROTECT,
        related_name='sold_tickets', verbose_name='Tipo de boleto'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='Cantidad')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio unitario')
    ticket_number = models.CharField(
        max_length=20, unique=True, default=_generate_ticket_number, verbose_name='Número de boleto'
    )
    seat_numbers = models.JSONField(
        default=list, blank=True, verbose_name='Asientos',
        help_text='Lista de asientos asignados (para tipos con asientos numerados).'
    )

    class Meta:
        verbose_name = 'Boleto'
        verbose_name_plural = 'Boletos'

    def __str__(self):
        return f"Boleto {self.ticket_number} — {self.ticket_type.name}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    @property
    def seats_display(self):
        return ', '.join(self.seat_numbers) if self.seat_numbers else '—'


class PendingOrder(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente de pago'),
        (STATUS_PAID, 'Pagado'),
        (STATUS_FAILED, 'Fallido'),
        (STATUS_EXPIRED, 'Expirado'),
    ]

    event = models.ForeignKey(
        'evente.Event', on_delete=models.PROTECT,
        related_name='pending_orders', verbose_name='Evento'
    )
    buyer_name = models.CharField(max_length=200, verbose_name='Nombre')
    buyer_email = models.EmailField(verbose_name='Correo')
    buyer_phone = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    # [{"ticket_type_id": 1, "ticket_type_name": "VIP", "quantity": 2,
    #   "unit_price": 150.0, "seats": ["A-1", "A-2"]}]
    items = models.JSONField(verbose_name='Items del pedido')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Total')
    mp_preference_id = models.CharField(max_length=200, blank=True, verbose_name='Preferencia MP')
    mp_payment_id = models.CharField(max_length=200, blank=True, verbose_name='ID de pago MP')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='Estado'
    )
    sale = models.OneToOneField(
        Sale, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pending_order', verbose_name='Venta generada'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name='Expira el')

    class Meta:
        verbose_name = 'Orden Pendiente (MP)'
        verbose_name_plural = 'Órdenes Pendientes (MP)'
        ordering = ['-created_at']

    def __str__(self):
        return f"Orden #{self.pk} — {self.buyer_name} [{self.get_status_display()}]"

    @property
    def is_expired(self):
        return self.status == self.STATUS_PENDING and timezone.now() > self.expires_at
