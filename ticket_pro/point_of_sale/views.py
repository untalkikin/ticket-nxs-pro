import io
import json
import uuid
import base64

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from evente.models import Event
from .models import Sale, Ticket


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _taken_seats_for(ticket_type):
    taken = set()
    for seats_list in Ticket.objects.filter(ticket_type=ticket_type).values_list('seat_numbers', flat=True):
        if seats_list:
            taken.update(seats_list)
    return taken


def _build_events_data(events):
    """Return enriched list with per-ticket-type seat availability."""
    result = []
    for event in events:
        tt_list = []
        for tt in event.ticket_types.all():
            entry = {'obj': tt, 'available_seats': None, 'taken_seats': []}
            if tt.has_numbered_seats:
                taken = _taken_seats_for(tt)
                all_seats = tt.get_all_seat_labels()
                entry['available_seats'] = [s for s in all_seats if s not in taken]
                entry['taken_seats'] = list(taken)
            tt_list.append(entry)
        result.append({'event': event, 'ticket_types': tt_list})
    return result


def _generate_qr_b64(data: dict) -> str:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=3)
    qr.add_data(json.dumps(data, ensure_ascii=False))
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def pos_view(request):
    events = Event.objects.filter(is_active=True).prefetch_related('ticket_types')
    events_data = _build_events_data(events)

    if request.method == 'POST':
        event_id = request.POST.get('event')
        buyer_name = request.POST.get('buyer_name', '').strip()
        buyer_email = request.POST.get('buyer_email', '').strip()
        buyer_phone = request.POST.get('buyer_phone', '').strip()

        if not event_id or not buyer_name:
            messages.error(request, 'El evento y el nombre del comprador son obligatorios.')
            return render(request, 'point_of_sale/pos.html', {'events_data': events_data})

        event = get_object_or_404(Event, pk=event_id, is_active=True)

        ticket_items = []
        errors = []

        for tt in event.ticket_types.all():
            if tt.has_numbered_seats:
                selected_seats = request.POST.getlist(f'seats_{tt.pk}')
                if not selected_seats:
                    continue
                # Verify seats are still available
                taken = _taken_seats_for(tt)
                unavailable = [s for s in selected_seats if s in taken]
                if unavailable:
                    errors.append(f'Los asientos {", ".join(unavailable)} ya no están disponibles en "{tt.name}".')
                    continue
                ticket_items.append({
                    'ticket_type': tt,
                    'quantity': len(selected_seats),
                    'seat_numbers': selected_seats,
                })
            else:
                raw = request.POST.get(f'qty_{tt.pk}', '0')
                qty = int(raw) if raw.isdigit() else 0
                if qty <= 0:
                    continue
                if qty > tt.available_quantity:
                    errors.append(f'Solo quedan {tt.available_quantity} boleto(s) de "{tt.name}".')
                    continue
                ticket_items.append({'ticket_type': tt, 'quantity': qty, 'seat_numbers': []})

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'point_of_sale/pos.html', {'events_data': events_data})

        if not ticket_items:
            messages.error(request, 'Debes seleccionar al menos un boleto.')
            return render(request, 'point_of_sale/pos.html', {'events_data': events_data})

        total = sum(item['ticket_type'].price * item['quantity'] for item in ticket_items)

        with transaction.atomic():
            sale = Sale.objects.create(
                event=event,
                total_amount=total,
                buyer_name=buyer_name,
                buyer_email=buyer_email,
                buyer_phone=buyer_phone,
            )
            for item in ticket_items:
                tt = item['ticket_type']
                Ticket.objects.create(
                    sale=sale,
                    ticket_type=tt,
                    quantity=item['quantity'],
                    unit_price=tt.price,
                    ticket_number=uuid.uuid4().hex[:10].upper(),
                    seat_numbers=item['seat_numbers'],
                )
                tt.sold_quantity += item['quantity']
                tt.save(update_fields=['sold_quantity'])

        return redirect('pos:ticket_print', sale_id=sale.pk)

    return render(request, 'point_of_sale/pos.html', {'events_data': events_data})


@login_required
def ticket_print(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.select_related('event').prefetch_related('tickets__ticket_type'),
        pk=sale_id
    )
    tickets_with_qr = []
    for ticket in sale.tickets.all():
        qr_data = {
            'num': ticket.ticket_number,
            'evento': sale.event.name,
            'tipo': ticket.ticket_type.name,
            'comprador': sale.buyer_name,
            'fecha': sale.event.date.strftime('%d/%m/%Y %H:%M'),
            'lugar': sale.event.venue,
        }
        if ticket.seat_numbers:
            qr_data['asientos'] = ticket.seat_numbers
        tickets_with_qr.append({'ticket': ticket, 'qr': _generate_qr_b64(qr_data)})

    return render(request, 'point_of_sale/ticket_print.html', {
        'sale': sale,
        'tickets_with_qr': tickets_with_qr,
    })
