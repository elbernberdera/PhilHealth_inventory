import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class SimpleVisitorLogMiddleware(MiddlewareMixin):
    def __call__(self, request):
        response = self.get_response(request)
        
        logger.info(
            f"{request.method} {request.path} - {response.status_code}",
            extra={
                'client_ip': self.get_client_ip(request),
                'device': self.get_device_type(request.META.get('HTTP_USER_AGENT', 'Unknown')),
            }
        )
        
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
    
    def get_device_type(self, user_agent):
        user_agent_lower = user_agent.lower()
        
        if any(x in user_agent_lower for x in ['mobile', 'android', 'iphone']):
            return 'Mobile'
        elif any(x in user_agent_lower for x in ['tablet', 'ipad']):
            return 'Tablet'
        return 'Desktop'