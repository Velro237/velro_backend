import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
import base64
from config.utils import upload_image
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        print("Connected now 11111111111111111111111111")
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        print("Disconnected now 222222222222222222222222222")
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
                attachments = text_data_json.get('attachments', [])

                # Save message to database and get serializable dict
                message_data = await self.save_message(content, attachments)
                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message_data
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
    def save_message(self, content, attachments):
        # Import models here to avoid circular imports
        from .models import Conversation, Message, MessageAttachment
        
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.scope['user'],
            content=content
        )
        print("========================================")
        print(attachments)
        print("========================================")
        # Handle attachments
        for attachment in attachments:
            file_data = base64.b64decode(attachment['data'])
            file_name = attachment['name']
            file_type = attachment['type']
            print("+++++++++++++++++++++++++++++++++++++")
            print(file_data)
            print(file_name)
            print(file_type)
            print("++++++++++++++++++++++++++++++++++++++")
            file_url = upload_image(file_data, public_id=f'message_attachments/{message.id}/{file_name}')
            print("File URL after upload:", file_url)
            MessageAttachment.objects.create(
                message=message,
                # file=ContentFile(file_data, name=file_name),
                file_url=file_url,
                file_name=file_name,
                file_type=file_type
            )

        # Prepare serializable message dict
        result = {
            'id': message.id,
            'content': message.content,
            'sender': {
                'id': message.sender.id,
                'username': message.sender.username,
                'email': message.sender.email
            },
            'created_at': message.created_at.isoformat(),
            'attachments': [
                {
                    'id': att.id,
                    'file_name': att.file_name,
                    'file_type': att.file_type,
                    'file_url': att.file_url,
                }
                for att in message.attachments.all()
            ]
        } 

        print("Returning message dict:", result)
        return result

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        self.room_group_name = f'notifications_{self.user.id}'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def user_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))
    


# Simple infra test: accept immediately and echo messages
from channels.generic.websocket import AsyncWebsocketConsumer
import json

class PingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()  # accept ASAP

    async def receive(self, text_data=None, bytes_data=None):
        await self.send(text_data=text_data or json.dumps({"pong": True}))
