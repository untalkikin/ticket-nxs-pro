from django.contrib import admin
from django.utils.html import format_html
from .models import Event, TicketType


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = ('name', 'price', 'quantity', 'sold_quantity', 'has_numbered_seats', 'seat_prefix', 'available_display')
    readonly_fields = ('sold_quantity', 'available_display')

    def available_display(self, obj):
        return obj.available_quantity if obj.pk else '-'
    available_display.short_description = 'Disponibles'


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'venue', 'total_capacity', 'tickets_sold_display', 'sold_percentage_bar', 'is_active')
    list_filter = ('is_active', 'date')
    search_fields = ('name', 'venue')
    inlines = [TicketTypeInline]
    readonly_fields = ('tickets_sold_display', 'available_capacity_display', 'sold_percentage_display', 'created_at')

    fieldsets = (
        ('Información del evento', {
            'fields': ('name', 'description', 'date', 'venue', 'is_active')
        }),
        ('Capacidad', {
            'fields': ('total_capacity', 'tickets_sold_display', 'available_capacity_display', 'sold_percentage_display')
        }),
        ('Registro', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def tickets_sold_display(self, obj):
        return obj.tickets_sold
    tickets_sold_display.short_description = 'Boletos vendidos'

    def available_capacity_display(self, obj):
        return obj.available_capacity
    available_capacity_display.short_description = 'Lugares disponibles'

    def sold_percentage_display(self, obj):
        return f"{obj.sold_percentage}%"
    sold_percentage_display.short_description = '% Vendido'

    def sold_percentage_bar(self, obj):
        pct = obj.sold_percentage
        color = '#28a745' if pct < 75 else '#ffc107' if pct < 90 else '#dc3545'
        return format_html(
            '<div style="width:130px;background:#e9ecef;border-radius:4px;height:20px;border:1px solid #dee2e6;">'
            '<div style="width:{0}%;background:{1};height:20px;border-radius:3px;'
            'text-align:center;color:white;font-size:11px;font-weight:bold;line-height:20px;">'
            '{0}%</div></div>',
            pct, color
        )
    sold_percentage_bar.short_description = '% Vendido'


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'price', 'quantity', 'sold_quantity', 'available_display', 'has_numbered_seats')
    list_filter = ('event', 'has_numbered_seats')
    search_fields = ('name', 'event__name')

    def available_display(self, obj):
        return obj.available_quantity
    available_display.short_description = 'Disponibles'
