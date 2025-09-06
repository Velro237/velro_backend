from django.urls import re_path
from . import consumers

# Use lazy imports to avoid AppRegistryNotReady error
def get_websocket_urlpatterns():
    return [
        re_path(r'ws/chat/(?P<conversation_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
        re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    ]

websocket_urlpatterns = get_websocket_urlpatterns() 

from django.urls import re_path
from . import consumers

def get_websocket_urlpatterns():
    return [
        re_path(r'ws/chat/(?P<conversation_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
        re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
        re_path(r'ws/ping/$', consumers.PingConsumer.as_asgi()),  # ← add this
    ]

websocket_urlpatterns = get_websocket_urlpatterns()
