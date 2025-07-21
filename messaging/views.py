from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Conversation, Message, MessageAttachment, Notification
from .serializers import (
    ConversationSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageAttachmentSerializer, NotificationSerializer
)
from .utils import send_message_to_conversation, send_typing_indicator
from config.views import StandardResponseViewSet
from .permissions import IsMessageOwner
from config.utils import standard_response

# Create your views here.

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(participants=user).distinct()


    def get_serializer_class(self):
        if self.action == 'create':
            return ConversationCreateSerializer
        return ConversationSerializer

    def perform_create(self, serializer):
        conversation = serializer.save()
        user_ids = {self.request.user.id}

        # Add travel_listing owner if exists
        if conversation.travel_listing and conversation.travel_listing.user:
            user_ids.add(conversation.travel_listing.user.id)

        # Add package_request owner if exists
        if conversation.package_request and conversation.package_request.user:
            user_ids.add(conversation.package_request.user.id)

        conversation.participants.add(*user_ids)

        # Log message_click event if related to a trip
        if conversation.travel_listing:
            from reporting.models import EventLog
            EventLog.objects.create(
                event_type='message_click',
                user=self.request.user,
                trip=conversation.travel_listing
            )

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        messages = conversation.messages.all()
        
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        conversation = self.get_object()
        serializer = MessageSerializer(data=request.data)
        
        if serializer.is_valid():
            message = serializer.save(
                conversation=conversation,
                sender=request.user
            )
            
            # Send message through WebSocket
            message_data = MessageSerializer(message).data
            send_message_to_conversation(conversation.id, message_data)
            
            return Response(message_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def typing(self, request, pk=None):
        conversation = self.get_object()
        is_typing = request.data.get('is_typing', False)
        
        # Send typing indicator through WebSocket
        send_typing_indicator(conversation.id, request.user.id, is_typing)
        
        return Response({'status': 'success'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        user = request.user
        conversations = self.get_queryset()
        
        unread_counts = {}
        for conversation in conversations:
            unread_counts[conversation.id] = conversation.messages.filter(
                is_read=False
            ).exclude(
                sender=user
            ).count()
        
        return Response(unread_counts)

class MessageViewSet(StandardResponseViewSet):
    """
    API endpoint for messages
    """
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(conversation__participants=user).distinct().order_by('-created_at')

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsMessageOwner()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        message = self.get_object()
        message.is_read = True
        message.save()
        return standard_response(data=self.get_serializer(message).data, status_code=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='mark_multiple_as_read')
    def mark_multiple_as_read(self, request):
        message_ids = request.data.get('message_ids', [])
        if not isinstance(message_ids, list) or not all(isinstance(mid, int) for mid in message_ids):
            return standard_response(error=['message_ids must be a list of integers.'], status_code=status.HTTP_400_BAD_REQUEST)
        user = request.user
        # Only mark as read messages the user has access to
        messages = Message.objects.filter(id__in=message_ids, conversation__participants=user)
        updated_count = messages.update(is_read=True)
        # Return the updated messages
        serializer = self.get_serializer(messages, many=True)
        return standard_response(data={'updated_count': updated_count, 'messages': serializer.data}, status_code=status.HTTP_200_OK)


class MessageAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return MessageAttachment.objects.filter(message__conversation__participants=user).distinct()

    def perform_create(self, serializer):
        message_id = self.request.data.get('message')
        user = self.request.user
        
        # Check if user has access to the message
        message = get_object_or_404(
            Message.objects.filter(conversation__participants=user),
            id=message_id
        )
        attachment = serializer.save(message=message)
        
        # Send updated message through WebSocket
        message_data = MessageSerializer(message).data
        send_message_to_conversation(message.conversation.id, message_data)

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        notifications = self.get_queryset().filter(is_read=False)
        notifications.update(is_read=True)
        return Response({'status': 'all marked as read'})