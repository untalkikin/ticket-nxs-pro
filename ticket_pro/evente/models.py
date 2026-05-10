from django.db import models


class Event(models.Model):
    name = models.CharField(max_length=200, verbose_name='Nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    date = models.DateTimeField(verbose_name='Fecha y hora')
    venue = models.CharField(max_length=200, verbose_name='Lugar')
    total_capacity = models.PositiveIntegerField(verbose_name='Capacidad total')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering = ['-date']

    def __str__(self):
        return f"{self.name} - {self.date.strftime('%d/%m/%Y')}"

    @property
    def tickets_sold(self):
        return sum(tt.sold_quantity for tt in self.ticket_types.all())

    @property
    def sold_percentage(self):
        if self.total_capacity == 0:
            return 0
        return round((self.tickets_sold / self.total_capacity) * 100, 1)

    @property
    def available_capacity(self):
        return self.total_capacity - self.tickets_sold


class TicketType(models.Model):
    event = models.ForeignKey(
        Event, related_name='ticket_types', on_delete=models.CASCADE, verbose_name='Evento'
    )
    name = models.CharField(max_length=100, verbose_name='Tipo')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio')
    quantity = models.PositiveIntegerField(verbose_name='Cantidad total')
    sold_quantity = models.PositiveIntegerField(default=0, verbose_name='Vendidos')
    has_numbered_seats = models.BooleanField(
        default=False, verbose_name='Asientos numerados',
        help_text='Activa si los boletos de este tipo tienen número de asiento asignado.'
    )
    seat_prefix = models.CharField(
        max_length=10, blank=True, default='', verbose_name='Prefijo de asiento',
        help_text='Prefijo para los asientos (ej: "A-", "VIP-"). Se numeran del 1 al total.'
    )

    class Meta:
        verbose_name = 'Tipo de Boleto'
        verbose_name_plural = 'Tipos de Boleto'

    def __str__(self):
        return f"{self.name} ({self.event.name})"

    @property
    def available_quantity(self):
        return self.quantity - self.sold_quantity

    @property
    def is_available(self):
        return self.available_quantity > 0

    def get_seat_label(self, number: int) -> str:
        return f"{self.seat_prefix}{number}"

    def get_all_seat_labels(self) -> list:
        return [self.get_seat_label(i) for i in range(1, self.quantity + 1)]
