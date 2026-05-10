import uuid
import logging
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from evente.models import Event, TicketType
from point_of_sale.models import PendingOrder, Sale, Ticket
from .mercadopago_service import create_preference, get_payment_info
from .serializers import (
    CreateOrderSerializer, EventDetailSerializer, EventListSerializer,
    PendingOrderStatusSerializer, SaleSerializer, TicketDetailSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _taken_seats_for(ticket_type: TicketType) -> set:
    taken = set()
    for seats_list in ticket_type.sold_tickets.values_list('seat_numbers', flat=True):
        if seats_list:
            taken.update(seats_list)
    return taken


def _confirm_pending_order(order: PendingOrder, mp_payment_id: str = '') -> Sale:
    """Convert an approved PendingOrder into a Sale + Tickets atomically."""
    with transaction.atomic():
        sale = Sale.objects.create(
            event=order.event,
            total_amount=order.total_amount,
            buyer_name=order.buyer_name,
            buyer_email=order.buyer_email,
            buyer_phone=order.buyer_phone,
        )
        for item in order.items:
            tt = TicketType.objects.select_for_update().get(pk=item['ticket_type_id'])
            Ticket.objects.create(
                sale=sale,
                ticket_type=tt,
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                ticket_number=uuid.uuid4().hex[:10].upper(),
                seat_numbers=item.get('seats', []),
            )
            tt.sold_quantity += item['quantity']
            tt.save(update_fields=['sold_quantity'])

        order.mp_payment_id = mp_payment_id
        order.status = PendingOrder.STATUS_PAID
        order.sale = sale
        order.save(update_fields=['mp_payment_id', 'status', 'sale'])
    return sale


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class EventListView(APIView):
    """GET /api/v1/events/ — list active events."""

    def get(self, request):
        events = Event.objects.filter(is_active=True).prefetch_related('ticket_types')
        return Response(EventListSerializer(events, many=True).data)


class EventDetailView(APIView):
    """GET /api/v1/events/<id>/ — event detail with ticket types and seat info."""

    def get(self, request, event_id):
        event = get_object_or_404(
            Event.objects.prefetch_related('ticket_types__sold_tickets'),
            pk=event_id, is_active=True
        )
        return Response(EventDetailSerializer(event).data)


class AvailableSeatsView(APIView):
    """GET /api/v1/events/<event_id>/seats/<ticket_type_id>/ — real-time seat availability."""

    def get(self, request, event_id, ticket_type_id):
        tt = get_object_or_404(TicketType, pk=ticket_type_id, event_id=event_id)
        if not tt.has_numbered_seats:
            return Response(
                {'error': 'Este tipo de boleto no tiene asientos numerados.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        taken = _taken_seats_for(tt)
        all_seats = tt.get_all_seat_labels()
        return Response({
            'ticket_type_id': tt.pk,
            'ticket_type_name': tt.name,
            'all_seats': all_seats,
            'available_seats': [s for s in all_seats if s not in taken],
            'taken_seats': sorted(taken),
        })


# ---------------------------------------------------------------------------
# Orders — Mercado Pago flow
# ---------------------------------------------------------------------------

class CreateOrderView(APIView):
    """
    POST /api/v1/orders/
    Create a PendingOrder and return a Mercado Pago payment preference.

    Body:
    {
        "event": 1,
        "buyer_name": "Juan Pérez",
        "buyer_email": "juan@mail.com",
        "buyer_phone": "5512345678",
        "items": [
            {"ticket_type": 2, "quantity": 2},
            {"ticket_type": 3, "seats": ["A-1", "A-2"]}
        ]
    }
    """

    def post(self, request):
        ser = CreateOrderSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        data = ser.validated_data
        event = get_object_or_404(Event, pk=data['event'], is_active=True)

        ticket_items = []
        mp_items = []
        total = 0

        for item in data['items']:
            tt = get_object_or_404(TicketType, pk=item['ticket_type'], event=event)

            if tt.has_numbered_seats:
                seats = item.get('seats', [])
                if not seats:
                    return Response(
                        {'error': f'Debes indicar los asientos para el tipo "{tt.name}".'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                taken = _taken_seats_for(tt)
                bad = [s for s in seats if s in taken]
                if bad:
                    return Response(
                        {'error': f'Los asientos {bad} ya no están disponibles en "{tt.name}".'},
                        status=status.HTTP_409_CONFLICT,
                    )
                qty = len(seats)
            else:
                seats = []
                qty = item.get('quantity', 1)
                if qty > tt.available_quantity:
                    return Response(
                        {'error': f'Solo quedan {tt.available_quantity} boleto(s) de "{tt.name}".'},
                        status=status.HTTP_409_CONFLICT,
                    )

            unit_price = float(tt.price)
            subtotal = unit_price * qty
            total += subtotal

            ticket_items.append({
                'ticket_type_id': tt.pk,
                'ticket_type_name': tt.name,
                'quantity': qty,
                'unit_price': unit_price,
                'seats': seats,
            })
            mp_items.append({
                'id': str(tt.pk),
                'title': f'{tt.name} — {event.name}',
                'quantity': qty,
                'unit_price': unit_price,
            })

        if not ticket_items:
            return Response({'error': 'No se especificaron boletos.'}, status=status.HTTP_400_BAD_REQUEST)

        expires_at = timezone.now() + timedelta(minutes=30)
        order = PendingOrder.objects.create(
            event=event,
            buyer_name=data['buyer_name'],
            buyer_email=data['buyer_email'],
            buyer_phone=data.get('buyer_phone', ''),
            items=ticket_items,
            total_amount=round(total, 2),
            expires_at=expires_at,
        )

        mp_result = create_preference(
            order=order,
            mp_items=mp_items,
            payer_email=data['buyer_email'],
            payer_name=data['buyer_name'],
        )

        response_data = {
            'order_id': order.pk,
            'total_amount': str(round(total, 2)),
            'expires_at': expires_at,
            'mp_configured': mp_result['success'],
        }

        if mp_result['success']:
            order.mp_preference_id = mp_result['preference_id']
            order.save(update_fields=['mp_preference_id'])
            response_data.update({
                'preference_id': mp_result['preference_id'],
                'init_point': mp_result['init_point'],
                'sandbox_init_point': mp_result.get('sandbox_init_point', ''),
            })
        else:
            response_data['mp_error'] = mp_result.get('error')

        return Response(response_data, status=status.HTTP_201_CREATED)


class OrderStatusView(APIView):
    """GET /api/v1/orders/<id>/ — check pending order status."""

    def get(self, request, order_id):
        order = get_object_or_404(PendingOrder, pk=order_id)
        return Response(PendingOrderStatusSerializer(order).data)


class PaymentWebhookView(APIView):
    """
    POST /api/v1/payment/webhook/
    Mercado Pago IPN/webhook. Verifies payment and confirms the order.
    """

    def post(self, request):
        topic = request.GET.get('topic') or request.data.get('type', '')
        mp_id = request.GET.get('id') or (request.data.get('data') or {}).get('id')

        if not mp_id or topic not in ('payment', 'merchant_order'):
            return Response({'status': 'ignored'})

        if topic != 'payment':
            return Response({'status': 'ignored'})

        mp_info = get_payment_info(str(mp_id))
        if not mp_info['success']:
            logger.error('MP webhook: could not retrieve payment %s — %s', mp_id, mp_info.get('error'))
            return Response({'status': 'error'}, status=status.HTTP_502_BAD_GATEWAY)

        payment = mp_info['payment']
        if payment.get('status') != 'approved':
            return Response({'status': 'not_approved'})

        external_ref = payment.get('external_reference')
        if not external_ref:
            return Response({'status': 'no_reference'})

        order = PendingOrder.objects.filter(
            pk=int(external_ref), status=PendingOrder.STATUS_PENDING
        ).first()

        if not order:
            return Response({'status': 'order_already_processed_or_not_found'})

        try:
            _confirm_pending_order(order, str(mp_id))
        except Exception as exc:
            logger.exception('Error confirming order %s: %s', order.pk, exc)
            return Response({'status': 'error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'status': 'ok'})


class PaymentResultView(APIView):
    """
    GET /api/v1/payment/result/
    Mercado Pago back_url redirect endpoint (shown to the user after payment).
    """

    def get(self, request):
        mp_status = request.GET.get('status', '')
        payment_id = request.GET.get('payment_id', '')
        order_id = request.GET.get('external_reference', '')
        return Response({
            'payment_status': mp_status,
            'payment_id': payment_id,
            'order_id': order_id,
            'message': {
                'success': 'Pago aprobado. Tu boleto será generado en breve.',
                'failure': 'El pago no pudo procesarse. Intenta de nuevo.',
                'pending': 'Tu pago está en proceso. Te notificaremos cuando sea confirmado.',
            }.get(mp_status, 'Estado desconocido.'),
        })


# ---------------------------------------------------------------------------
# Direct sale (POS mobile — no payment gateway)
# ---------------------------------------------------------------------------

class DirectSaleView(APIView):
    """
    POST /api/v1/sales/
    Create a confirmed sale directly (for internal POS without payment gateway).
    Same body as CreateOrderView.
    """

    def post(self, request):
        ser = CreateOrderSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        data = ser.validated_data
        event = get_object_or_404(Event, pk=data['event'], is_active=True)

        ticket_items = []
        total = 0

        for item in data['items']:
            tt = get_object_or_404(TicketType, pk=item['ticket_type'], event=event)

            if tt.has_numbered_seats:
                seats = item.get('seats', [])
                if not seats:
                    return Response(
                        {'error': f'Debes indicar los asientos para "{tt.name}".'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                taken = _taken_seats_for(tt)
                bad = [s for s in seats if s in taken]
                if bad:
                    return Response(
                        {'error': f'Asientos no disponibles: {bad}'},
                        status=status.HTTP_409_CONFLICT,
                    )
                qty = len(seats)
            else:
                seats = []
                qty = item.get('quantity', 1)
                if qty > tt.available_quantity:
                    return Response(
                        {'error': f'Solo quedan {tt.available_quantity} boleto(s) de "{tt.name}".'},
                        status=status.HTTP_409_CONFLICT,
                    )

            total += float(tt.price) * qty
            ticket_items.append({'ticket_type': tt, 'quantity': qty, 'seats': seats})

        if not ticket_items:
            return Response({'error': 'Sin boletos.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            sale = Sale.objects.create(
                event=event,
                total_amount=round(total, 2),
                buyer_name=data['buyer_name'],
                buyer_email=data['buyer_email'],
                buyer_phone=data.get('buyer_phone', ''),
            )
            for item in ticket_items:
                tt = item['ticket_type']
                Ticket.objects.create(
                    sale=sale,
                    ticket_type=tt,
                    quantity=item['quantity'],
                    unit_price=tt.price,
                    ticket_number=uuid.uuid4().hex[:10].upper(),
                    seat_numbers=item['seats'],
                )
                tt.sold_quantity += item['quantity']
                tt.save(update_fields=['sold_quantity'])

        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Ticket validation (for scanning at venue)
# ---------------------------------------------------------------------------

class ValidateTicketView(APIView):
    """
    GET /api/v1/tickets/<ticket_number>/
    Returns ticket details for QR validation at the venue.
    """

    def get(self, request, ticket_number):
        ticket = get_object_or_404(
            Ticket.objects.select_related('sale__event', 'ticket_type'),
            ticket_number=ticket_number.upper(),
        )
        return Response(TicketDetailSerializer(ticket).data)
