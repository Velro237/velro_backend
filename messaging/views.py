from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import Conversation, Message, MessageAttachment
from .serializers import (
    ConversationSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageAttachmentSerializer
)
from .utils import send_message_to_conversation, send_typing_indicator
from config.views import StandardResponseViewSet

# Create your views here.

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(
            Q(participants=user) |
            Q(travel_listing__user=user) |
            Q(package_request__user=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == 'create':
            return ConversationCreateSerializer
        return ConversationSerializer

    def perform_create(self, serializer):
        conversation = serializer.save()
        conversation.participants.add(self.request.user)

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
        return Message.objects.filter(
            Q(conversation__participants=user) |
            Q(conversation__travel_listing__user=user) |
            Q(conversation__package_request__user=user)
        ).distinct().order_by('-created_at')

class MessageAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = MessageAttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return MessageAttachment.objects.filter(
            Q(message__conversation__participants=user) |
            Q(message__conversation__travel_listing__user=user) |
            Q(message__conversation__package_request__user=user)
        ).distinct()

    def perform_create(self, serializer):
        message_id = self.request.data.get('message')
        user = self.request.user
        
        # Check if user has access to the message
        message = get_object_or_404(
            Message.objects.filter(
                Q(conversation__participants=user) |
                Q(conversation__travel_listing__user=user) |
                Q(conversation__package_request__user=user)
            ),
            id=message_id
        )
        attachment = serializer.save(message=message)
        
        # Send updated message through WebSocket
        message_data = MessageSerializer(message).data
        send_message_to_conversation(message.conversation.id, message_data)
