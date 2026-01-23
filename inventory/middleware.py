import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class SimpleVisitorLogMiddleware(MiddlewareMixin):
    def __call__(self, request):
        # Log visitor information
        ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        logger.info(f"Visitor IP: {ip}, User-Agent: {user_agent}")
        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip