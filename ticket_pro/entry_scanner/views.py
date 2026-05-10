import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from evente.models import Event
from point_of_sale.models import Ticket
from .models import TicketEntry


@login_required
def scanner_index(request):
    events = Event.objects.filter(is_active=True).prefetch_related('ticket_types')
    events_data = []
    for event in events:
        sold = sum(tt.sold_quantity for tt in event.ticket_types.all())
        entries = TicketEntry.objects.filter(ticket__sale__event=event).count()
        pct = round((entries / sold * 100), 1) if sold else 0
        events_data.append({
            'event': event,
            'sold': sold,
            'entries': entries,
            'pending': sold - entries,
            'entry_pct': pct,
        })
    return render(request, 'entry_scanner/index.html', {'events_data': events_data})


@login_required
def scanner_view(request, event_id):
    event = get_object_or_404(Event, pk=event_id, is_active=True)
    sold = sum(tt.sold_quantity for tt in event.ticket_types.all())
    entries = TicketEntry.objects.filter(ticket__sale__event=event).count()
    recent = (
        TicketEntry.objects
        .filter(ticket__sale__event=event)
        .select_related('ticket__sale', 'ticket__ticket_type')
        .order_by('-entered_at')[:30]
    )
    return render(request, 'entry_scanner/scanner.html', {
        'event': event,
        'sold': sold,
        'entries': entries,
        'pending': sold - entries,
        'entry_pct': round((entries / sold * 100), 1) if sold else 0,
        'recent': recent,
    })


@login_required
@require_POST
def validate_ticket(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'valid': False, 'status': 'error', 'message': 'Datos inválidos.'}, status=400)

    raw = body.get('ticket_number', '').strip().upper()
    event_id = body.get('event_id')

    if not raw:
        return JsonResponse({
            'valid': False, 'status': 'empty',
            'message': 'Ingresa un número de boleto.', 'color': 'danger',
        })

    try:
        ticket = Ticket.objects.select_related('sale__event', 'ticket_type').get(ticket_number=raw)
    except Ticket.DoesNotExist:
        return JsonResponse({
            'valid': False, 'status': 'not_found',
            'message': f'Boleto «{raw}» no encontrado en el sistema.',
            'color': 'danger',
        })

    # Verify event
    if event_id:
        try:
            if ticket.sale.event.pk != int(event_id):
                return JsonResponse({
                    'valid': False, 'status': 'wrong_event',
                    'message': f'Este boleto pertenece al evento «{ticket.sale.event.name}».',
                    'color': 'warning',
                    'ticket': _ticket_info(ticket),
                })
        except (ValueError, TypeError):
            pass

    entry_count = ticket.entries.count()
    if entry_count >= ticket.quantity:
        last = ticket.entries.order_by('-entered_at').first()
        return JsonResponse({
            'valid': False, 'status': 'already_used',
            'message': f'Boleto ya registrado el {last.entered_at.strftime("%d/%m/%Y a las %H:%M")}.',
            'color': 'warning',
            'ticket': _ticket_info(ticket),
        })

    TicketEntry.objects.create(ticket=ticket)
    remaining = ticket.quantity - entry_count - 1

    suffix = f' ({remaining} entrada(s) adicional(es) permitida(s))' if remaining > 0 else ''
    return JsonResponse({
        'valid': True, 'status': 'ok',
        'message': f'¡Bienvenido/a, {ticket.sale.buyer_name}!{suffix}',
        'color': 'success',
        'ticket': _ticket_info(ticket, entries_used=entry_count + 1),
    })


def _ticket_info(ticket, entries_used=None):
    info = {
        'number': ticket.ticket_number,
        'event': ticket.sale.event.name,
        'type': ticket.ticket_type.name,
        'buyer': ticket.sale.buyer_name,
        'buyer_email': ticket.sale.buyer_email,
        'quantity': ticket.quantity,
        'seats': ticket.seat_numbers,
        'seats_display': ticket.seats_display,
    }
    if entries_used is not None:
        info['entries_used'] = entries_used
    return info
