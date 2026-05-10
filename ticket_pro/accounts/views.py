from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils import timezone

from entry_scanner.models import TicketEntry
from evente.models import Event
from point_of_sale.models import Sale


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return '/dashboard/'


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def dashboard(request):
    today = timezone.now().date()
    active_events = Event.objects.filter(is_active=True).prefetch_related('ticket_types')

    sales_today = Sale.objects.filter(sale_date__date=today).count()
    entries_today = TicketEntry.objects.filter(entered_at__date=today).count()
    total_events = active_events.count()

    events_summary = []
    for event in active_events[:5]:
        sold = sum(tt.sold_quantity for tt in event.ticket_types.all())
        entries = TicketEntry.objects.filter(ticket__sale__event=event).count()
        events_summary.append({
            'event': event,
            'sold': sold,
            'entries': entries,
            'pct': round((event.sold_percentage), 1),
        })

    return render(request, 'accounts/dashboard.html', {
        'user': request.user,
        'sales_today': sales_today,
        'entries_today': entries_today,
        'total_events': total_events,
        'events_summary': events_summary,
    })
