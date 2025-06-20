import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        print("jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj")
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        print("kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk")
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            print(message_type)
            if message_type == 'message':
                content = text_data_json.get('content')
                # Save message to database
                message = await self.save_message(content)
                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': {
                            'id': message.id,
                            'content': message.content,
                            'sender': {
                                'id': message.sender.id,
                                'username': message.sender.username,
                                'email': message.sender.email
                            },
                            'created_at': message.created_at.isoformat(),
                        }
                    }
                )
            elif message_type == 'typing':
                # Handle typing indicator
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'typing_indicator',
                        'user_id': self.scope['user'].id,
                        'username': self.scope['user'].username,
                        'is_typing': text_data_json.get('is_typing', False)
                    }
                )
        except Exception as e:
            import traceback
            print("Exception in receive:", e)
            traceback.print_exc()
            # Send error to client
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error: {str(e)}'
            }))

    async def chat_message(self, event):
        # Send message to WebSocket
        print("the event message is", event['message'])
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))

    async def typing_indicator(self, event):
        # Send typing indicator to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_typing': event['is_typing']
        }))

    @database_sync_to_async
    def save_message(self, content):
        # Import models here to avoid circular imports
        from .models import Conversation, Message
        
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.scope['user'],
            content=content
        )
        return message 