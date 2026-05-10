"""Mercado Pago preference creation helper."""
from django.conf import settings


def create_preference(order, mp_items: list, payer_email: str, payer_name: str) -> dict:
    """
    Create a Mercado Pago payment preference for a PendingOrder.
    Returns a dict with keys: success, preference_id, init_point,
    sandbox_init_point, error (on failure).
    """
    access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '')
    if not access_token:
        return {'success': False, 'error': 'MERCADOPAGO_ACCESS_TOKEN no configurado en settings.'}

    try:
        import mercadopago
    except ImportError:
        return {'success': False, 'error': 'Paquete mercadopago no instalado.'}

    try:
        sdk = mercadopago.SDK(access_token)
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
        currency = getattr(settings, 'MP_CURRENCY_ID', 'MXN')

        # Ensure unit_price is float with 2 decimal places
        items_payload = [
            {
                'id': str(item.get('id', '')),
                'title': item['title'],
                'quantity': int(item['quantity']),
                'unit_price': round(float(item['unit_price']), 2),
                'currency_id': currency,
            }
            for item in mp_items
        ]

        preference_data = {
            'items': items_payload,
            'payer': {
                'name': payer_name,
                'email': payer_email,
            },
            'back_urls': {
                'success': f'{site_url}/api/v1/payment/result/?status=success',
                'failure': f'{site_url}/api/v1/payment/result/?status=failure',
                'pending': f'{site_url}/api/v1/payment/result/?status=pending',
            },
            'auto_return': 'approved',
            'notification_url': f'{site_url}/api/v1/payment/webhook/',
            'external_reference': str(order.pk),
            'expires': True,
            'expiration_date_from': order.created_at.isoformat(),
            'expiration_date_to': order.expires_at.isoformat(),
        }

        result = sdk.preference().create(preference_data)
        http_status = result.get('status')
        response = result.get('response', {})

        if http_status == 201:
            return {
                'success': True,
                'preference_id': response['id'],
                'init_point': response['init_point'],
                'sandbox_init_point': response.get('sandbox_init_point', ''),
            }

        return {
            'success': False,
            'error': response.get('message', f'Error MP (HTTP {http_status})'),
        }

    except Exception as exc:
        return {'success': False, 'error': str(exc)}


def get_payment_info(payment_id: str) -> dict:
    """Retrieve payment details from Mercado Pago."""
    access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '')
    if not access_token:
        return {'success': False, 'error': 'MERCADOPAGO_ACCESS_TOKEN no configurado.'}
    try:
        import mercadopago
        sdk = mercadopago.SDK(access_token)
        result = sdk.payment().get(payment_id)
        return {'success': True, 'payment': result.get('response', {})}
    except Exception as exc:
        return {'success': False, 'error': str(exc)}
