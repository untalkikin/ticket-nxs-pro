from django.contrib import admin
from django.utils.html import format_html
from .models import Sale, Ticket, PendingOrder


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = ('ticket_number', 'ticket_type', 'quantity', 'unit_price', 'seats_display', 'subtotal_display')
    can_delete = False

    def subtotal_display(self, obj):
        return f"${obj.subtotal:,.2f}" if obj.pk else '-'
    subtotal_display.short_description = 'Subtotal'

    def seats_display(self, obj):
        return obj.seats_display if obj.pk else '-'
    seats_display.short_description = 'Asientos'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'buyer_name', 'buyer_email', 'buyer_phone', 'total_tickets_display', 'total_amount', 'sale_date')
    list_filter = ('event', 'sale_date')
    search_fields = ('buyer_name', 'buyer_email', 'buyer_phone')
    readonly_fields = ('sale_date', 'total_amount', 'event', 'buyer_name', 'buyer_email', 'buyer_phone', 'total_tickets_display')
    inlines = [TicketInline]

    fieldsets = (
        ('Datos de la venta', {
            'fields': ('event', 'sale_date', 'total_amount', 'total_tickets_display')
        }),
        ('Datos del comprador', {
            'fields': ('buyer_name', 'buyer_email', 'buyer_phone')
        }),
    )

    def total_tickets_display(self, obj):
        return obj.total_tickets
    total_tickets_display.short_description = 'Total boletos'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'sale', 'ticket_type', 'quantity', 'unit_price', 'seats_display', 'subtotal_display')
    list_filter = ('ticket_type__event',)
    search_fields = ('ticket_number', 'sale__buyer_name')
    readonly_fields = ('ticket_number', 'sale', 'ticket_type', 'quantity', 'unit_price', 'seat_numbers', 'seats_display')

    def subtotal_display(self, obj):
        return f"${obj.subtotal:,.2f}"
    subtotal_display.short_description = 'Subtotal'

    def seats_display(self, obj):
        return obj.seats_display
    seats_display.short_description = 'Asientos'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PendingOrder)
class PendingOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'buyer_name', 'buyer_email', 'total_amount', 'status_badge', 'created_at', 'expires_at')
    list_filter = ('status', 'event', 'created_at')
    search_fields = ('buyer_name', 'buyer_email', 'mp_payment_id')
    readonly_fields = ('event', 'buyer_name', 'buyer_email', 'buyer_phone', 'items', 'total_amount',
                       'mp_preference_id', 'mp_payment_id', 'status', 'sale', 'created_at', 'expires_at')

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'paid': '#28a745',
            'failed': '#dc3545',
            'expired': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:bold;">'
            '{}</span>', color, obj.get_status_display()
        )
    status_badge.short_description = 'Estado'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
