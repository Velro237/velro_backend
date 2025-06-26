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

def send_notification_to_user(user_id, notification_data):
    """
    Send a notification to a user through WebSocket
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'notifications_{user_id}',
        {
            'type': 'user_notification',
            'notification': notification_data
        }
    ) 


# {'id': 2, 'user': 3, 'travel_listing': 6, 'message': 'A new travel listing matches your alert: France to Germany - 2024-07-01', 'is_read': False, 'created_at': '2025-06-25T14:40:44.316274Z'}