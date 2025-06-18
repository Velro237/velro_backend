from django.urls import re_path

# Use lazy imports to avoid AppRegistryNotReady error
def get_websocket_urlpatterns():
    from . import consumers
    
    return [
        re_path(r'ws/chat/(?P<conversation_id>\w+)/$', consumers.ChatConsumer.as_asgi()),
    ]

websocket_urlpatterns = get_websocket_urlpatterns() 