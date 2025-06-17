import json
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_message_to_conversation(conversation_id, message_data):
    """
    Send a message to all users in a conversation through WebSocket
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{conversation_id}',
        {
            'type': 'chat_message',
            'message': message_data
        }
    )

def send_typing_indicator(conversation_id, user_id, is_typing):
    """
    Send typing indicator to all users in a conversation through WebSocket
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{conversation_id}',
        {
            'type': 'typing_indicator',
            'user_id': user_id,
            'is_typing': is_typing
        }
    ) 