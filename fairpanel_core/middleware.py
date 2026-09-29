from django.contrib.auth import get_user_model
from django.core import signing
from django.utils.deprecation import MiddlewareMixin


class CheckerBearerMiddleware(MiddlewareMixin):
    """Authenticate explicit, expiring API bearer tokens for local acceptance checks."""

    def process_request(self, request):
        if not request.path.startswith('/api/v1/'):
            return None
        scheme, separator, token = request.headers.get('Authorization', '').partition(' ')
        if not separator or scheme.lower() != 'bearer' or not token:
            return None
        try:
            user_id = signing.TimestampSigner(salt='fairpanel-checker').unsign(
                token, max_age=12 * 60 * 60)
        except signing.BadSignature:
            return None
        user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
        if user:
            request.user = user
            request.checker_bearer_authenticated = True
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        if getattr(request, 'checker_bearer_authenticated', False):
            request._dont_enforce_csrf_checks = True
        return None
