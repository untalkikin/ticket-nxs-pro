from django.db import models


class TicketEntry(models.Model):
    ticket = models.ForeignKey(
        'point_of_sale.Ticket',
        on_delete=models.PROTECT,
        related_name='entries',
        verbose_name='Boleto',
    )
    entered_at = models.DateTimeField(auto_now_add=True, verbose_name='Hora de entrada')

    class Meta:
        verbose_name = 'Registro de Entrada'
        verbose_name_plural = 'Registros de Entradas'
        ordering = ['-entered_at']

    def __str__(self):
        return f"{self.ticket.ticket_number} — {self.entered_at.strftime('%d/%m/%Y %H:%M')}"
