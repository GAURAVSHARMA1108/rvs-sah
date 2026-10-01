import hashlib
from rest_framework import authentication, exceptions
from django.utils import timezone
from .models import APIKey

class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication for external API consumers and the Embeddable Widget.
    Supports:
    - Authorization: Bearer sk_live_...
    - X-API-Key: sk_live_...
    - URL query parameter: ?api_key=sk_live_...
    """

    def authenticate(self, request):
        raw_key = None

        # 1. Header: Authorization: Bearer <key>
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            raw_key = auth_header[7:].strip()
        
        # 2. Header: X-API-Key: <key>
        if not raw_key:
            raw_key = request.headers.get('X-API-Key', '').strip()

        # 3. Query Parameter: ?api_key=<key>
        if not raw_key:
            raw_key = request.query_params.get('api_key', '').strip()

        if not raw_key:
            return None  # Pass to next authentication class (e.g. SessionAuthentication)

        if len(raw_key) < 16 or not raw_key.startswith('sk_'):
            raise exceptions.AuthenticationFailed('Invalid API key format. Key must start with sk_.')

        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        try:
            api_key = APIKey.objects.select_related('user').get(
                key_hash=key_hash,
                is_active=True
            )
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid or revoked API key.')

        if not api_key.user.is_active:
            raise exceptions.AuthenticationFailed('User account associated with this API key is deactivated.')

        # Update last used timestamp without heavy db lock
        APIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        # Attach key object to request for downstream plan verification
        request.api_key = api_key
        return (api_key.user, api_key)
