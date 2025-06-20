from rest_framework import serializers
from .models import Conversation, Message
from users.serializers import UserProfileSerializer
from listings.serializers import TravelListingSerializer, PackageRequestSerializer


class MessageSerializer(serializers.ModelSerializer):
    sender = UserProfileSerializer(read_only=True)
    class Meta:
        model = Message
        fields = ('id', 'conversation', 'sender', 'content', 'is_read',
                 'created_at')
        read_only_fields = ('created_at', 'is_read')
        
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
        fields = ('participant_ids', 'travel_listing_id', 'package_request_id')

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