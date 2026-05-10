from django.contrib import admin
from django.utils.html import format_html
from .models import TicketEntry


@admin.register(TicketEntry)
class TicketEntryAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_number_display', 'buyer_display', 'event_display',
        'type_display', 'seats_display', 'entered_at',
    )
    list_filter = ('ticket__sale__event', 'entered_at')
    search_fields = ('ticket__ticket_number', 'ticket__sale__buyer_name')
    readonly_fields = (
        'ticket', 'entered_at',
        'ticket_number_display', 'buyer_display', 'event_display',
        'type_display', 'seats_display',
    )
    date_hierarchy = 'entered_at'

    def ticket_number_display(self, obj):
        return format_html('<code>{}</code>', obj.ticket.ticket_number)
    ticket_number_display.short_description = 'Número de boleto'

    def buyer_display(self, obj):
        return obj.ticket.sale.buyer_name
    buyer_display.short_description = 'Comprador'

    def event_display(self, obj):
        return obj.ticket.sale.event.name
    event_display.short_description = 'Evento'

    def type_display(self, obj):
        return obj.ticket.ticket_type.name
    type_display.short_description = 'Tipo'

    def seats_display(self, obj):
        return obj.ticket.seats_display
    seats_display.short_description = 'Asientos'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
