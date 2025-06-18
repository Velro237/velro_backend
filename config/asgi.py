"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

def get_websocket_application():
    """Lazy load websocket routing to avoid import issues"""
    from messaging.routing import websocket_urlpatterns
    from messaging.middleware import JWTAuthMiddlewareStack
    
    return JWTAuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    )

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": get_websocket_application(),
})
