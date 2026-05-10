from rest_framework import serializers
from evente.models import Event, TicketType
from point_of_sale.models import Sale, Ticket, PendingOrder


# ---------------------------------------------------------------------------
# Event / TicketType
# ---------------------------------------------------------------------------

class TicketTypeSerializer(serializers.ModelSerializer):
    available_quantity = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()
    available_seats = serializers.SerializerMethodField()

    class Meta:
        model = TicketType
        fields = [
            'id', 'name', 'price', 'quantity', 'sold_quantity',
            'available_quantity', 'is_available',
            'has_numbered_seats', 'seat_prefix', 'available_seats',
        ]

    def get_available_seats(self, obj):
        if not obj.has_numbered_seats:
            return None
        taken = set()
        for seats_list in obj.sold_tickets.values_list('seat_numbers', flat=True):
            if seats_list:
                taken.update(seats_list)
        return [s for s in obj.get_all_seat_labels() if s not in taken]


class EventListSerializer(serializers.ModelSerializer):
    sold_percentage = serializers.ReadOnlyField()
    tickets_sold = serializers.ReadOnlyField()
    available_capacity = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = [
            'id', 'name', 'description', 'date', 'venue',
            'total_capacity', 'tickets_sold', 'available_capacity', 'sold_percentage',
        ]


class EventDetailSerializer(EventListSerializer):
    ticket_types = TicketTypeSerializer(many=True, read_only=True)

    class Meta(EventListSerializer.Meta):
        fields = EventListSerializer.Meta.fields + ['ticket_types']


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------

class OrderItemSerializer(serializers.Serializer):
    ticket_type = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, required=False, default=1)
    seats = serializers.ListField(
        child=serializers.CharField(max_length=30),
        required=False, default=list,
        help_text='Requerido si el tipo de boleto tiene asientos numerados.'
    )


class CreateOrderSerializer(serializers.Serializer):
    event = serializers.IntegerField(min_value=1)
    buyer_name = serializers.CharField(max_length=200)
    buyer_email = serializers.EmailField()
    buyer_phone = serializers.CharField(max_length=20, required=False, default='')
    items = OrderItemSerializer(many=True, allow_empty=False)


# ---------------------------------------------------------------------------
# Tickets / Sales
# ---------------------------------------------------------------------------

class TicketDetailSerializer(serializers.ModelSerializer):
    ticket_type_name = serializers.CharField(source='ticket_type.name', read_only=True)
    event_name = serializers.CharField(source='sale.event.name', read_only=True)
    event_date = serializers.DateTimeField(source='sale.event.date', read_only=True)
    venue = serializers.CharField(source='sale.event.venue', read_only=True)
    buyer_name = serializers.CharField(source='sale.buyer_name', read_only=True)
    subtotal = serializers.ReadOnlyField()
    seats_display = serializers.ReadOnlyField()

    class Meta:
        model = Ticket
        fields = [
            'ticket_number', 'ticket_type_name', 'event_name', 'event_date', 'venue',
            'quantity', 'unit_price', 'subtotal', 'seat_numbers', 'seats_display', 'buyer_name',
        ]


class SaleSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)
    tickets = TicketDetailSerializer(many=True, read_only=True)
    total_tickets = serializers.ReadOnlyField()

    class Meta:
        model = Sale
        fields = [
            'id', 'event_name', 'buyer_name', 'buyer_email', 'buyer_phone',
            'total_amount', 'total_tickets', 'sale_date', 'tickets',
        ]


# ---------------------------------------------------------------------------
# Pending orders
# ---------------------------------------------------------------------------

class PendingOrderStatusSerializer(serializers.ModelSerializer):
    sale_id = serializers.SerializerMethodField()

    class Meta:
        model = PendingOrder
        fields = ['id', 'status', 'total_amount', 'mp_preference_id', 'created_at', 'expires_at', 'sale_id']

    def get_sale_id(self, obj):
        return obj.sale_id if obj.sale_id else None
