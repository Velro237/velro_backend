from rest_framework import serializers
from .models import Conversation, Message, MessageAttachment, Notification
from users.serializers import UserProfileSerializer
from listings.serializers import TravelListingSerializer, PackageRequestSerializer
from config.utils import upload_image


class MessageAttachmentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = MessageAttachment
        fields = ('id', 'file', 'file_name', 'file_url', 'file_type', 'created_at')
        read_only_fields = ('file_name', 'file_url', 'file_type', 'created_at')

    def create(self, validated_data):
        file = validated_data.pop('file', None)
        # Set file_name and file_type automatically from the uploaded file
        if file:
            validated_data['file_name'] = file.name
            validated_data['file_type'] = getattr(file, 'content_type', '')
        instance = MessageAttachment.objects.create(**validated_data)

        if file:
            file_url = upload_image(file, public_id=f'message_attachments/{instance.message.id}/{file.name}')
            instance.file_url = file_url
            instance.save()
        return instance

    def update(self, instance, validated_data):
        file = validated_data.pop('file', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if file:
            instance.file_name = file.name
            instance.file_type = getattr(file, 'content_type', '')
            file_url = upload_image(file, public_id=f'message_attachments/{instance.message.id}/{file.name}')
            instance.file_url = file_url

        instance.save()
        return instance


class MessageSerializer(serializers.ModelSerializer):
    sender = UserProfileSerializer(read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    uploaded_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Message
        fields = ('id', 'conversation', 'sender', 'content', 'is_read',
                  'created_at', 'attachments', 'uploaded_files')
        read_only_fields = ('created_at', 'is_read')

    def create(self, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])
        message = Message.objects.create(**validated_data)

        # Handle file attachments
        for file in uploaded_files:
            file_url = upload_image(file, public_id=f'message_attachments/{message.id}/{file.name}')
            MessageAttachment.objects.create(
                message=message,
                # file=file,
                file_url=file_url,
                file_name=file.name,
                file_type=file.content_type
            )

        return message

    def update(self, instance, validated_data):
        uploaded_files = validated_data.pop('uploaded_files', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Handle file attachments
        if uploaded_files:
            for file in uploaded_files:
                file_url = upload_image(file, public_id=f'message_attachments/{instance.id}/{file.name}')
                MessageAttachment.objects.create(
                    message=instance,
                    # file=file,
                    file_url=file_url,
                    file_name=file.name,
                    file_type=file.content_type
                )

        instance.save()
        return instance


class ConversationSerializer(serializers.ModelSerializer):
    participants = UserProfileSerializer(many=True, read_only=True)
    travel_listing = TravelListingSerializer(read_only=True)
    package_request = PackageRequestSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ('id', 'participants', 'travel_listing', 'package_request',
                  'created_at', 'updated_at', 'last_message', 'unread_count')
        read_only_fields = ('created_at', 'updated_at')

    def get_last_message(self, obj):
        last_message = obj.messages.last()
        if last_message:
            return MessageSerializer(last_message).data
        return None

    def get_unread_count(self, obj):
        user = self.context['request'].user
        return obj.messages.filter(is_read=False).exclude(sender=user).count()


class ConversationCreateSerializer(serializers.ModelSerializer):
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )
    travel_listing_id = serializers.IntegerField(required=False)
    package_request_id = serializers.IntegerField(required=False)

    class Meta:
        model = Conversation
        fields = ('id', 'participant_ids', 'travel_listing_id', 'package_request_id')
        read_only_fields = ('id',)

    def validate(self, data):
        if not data.get('travel_listing_id') and not data.get('package_request_id'):
            raise serializers.ValidationError(
                "Either travel_listing_id or package_request_id must be provided"
            )
        return data

    def create(self, validated_data):
        participant_ids = validated_data.pop('participant_ids')
        travel_listing_id = validated_data.pop('travel_listing_id', None)
        package_request_id = validated_data.pop('package_request_id', None)

        conversation = Conversation.objects.create(
            travel_listing_id=travel_listing_id,
            package_request_id=package_request_id
        )

        # Add participants
        conversation.participants.add(*participant_ids)

        return conversation


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'user', 'travel_listing', 'message', 'is_read', 'created_at')
        read_only_fields = ('created_at',)
