from rest_framework import serializers
from .models import Booking, BookingMessage, BookingStatusUpdate
from users.serializers import UserProfileSerializer
from listings.serializers import TravelListingSerializer, PackageRequestSerializer

class BookingMessageSerializer(serializers.ModelSerializer):
    sender = UserProfileSerializer(read_only=True)

    class Meta:
        model = BookingMessage
        fields = ('id', 'booking', 'sender', 'message', 'created_at')
        read_only_fields = ('created_at',)

class BookingStatusUpdateSerializer(serializers.ModelSerializer):
    updated_by = UserProfileSerializer(read_only=True)

    class Meta:
        model = BookingStatusUpdate
        fields = ('id', 'booking', 'updated_by', 'old_status', 'new_status', 'reason', 'created_at')
        read_only_fields = ('created_at',)

class BookingSerializer(serializers.ModelSerializer):
    traveler = UserProfileSerializer(read_only=True)
    sender = UserProfileSerializer(read_only=True)
    travel_listing = TravelListingSerializer(read_only=True)
    package_request = PackageRequestSerializer(read_only=True)
    messages = BookingMessageSerializer(many=True, read_only=True)
    status_updates = BookingStatusUpdateSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = (
            'id', 'travel_listing', 'package_request', 'traveler', 'sender',
            'status', 'package_weight', 'price_per_kg', 'total_price',
            'currency', 'notes', 'created_at', 'updated_at', 'messages', 'status_updates'
        )
        read_only_fields = ('created_at', 'updated_at', 'total_price')

class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = (
            'travel_listing', 'package_request', 'package_weight',
            'price_per_kg', 'currency', 'notes'
        )

    def validate(self, data):
        travel_listing = data['travel_listing']
        package_request = data['package_request']
        package_weight = data['package_weight']

        # Get the current user from context
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Check if user is the owner of the package request
        if user and package_request.user != user:
            raise serializers.ValidationError(
                "Only the owner of the package request can create a booking for it"
            )

        # Check if travel listing has enough space
        if package_weight > travel_listing.maximum_weight_in_kg:
            raise serializers.ValidationError(
                "Package weight exceeds available space in travel listing"
            )

        # Check if price is within acceptable range
        if data['price_per_kg'] > travel_listing.price_per_kg:
            raise serializers.ValidationError(
                "Price per kilo exceeds the maximum allowed by the travel listing"
            )

        return data

    def create(self, validated_data):
        travel_listing = validated_data['travel_listing']
        package_request = validated_data['package_request']
        
        booking = Booking.objects.create(
            traveler=travel_listing.user,
            sender=package_request.user,
            **validated_data
        )

        # Create initial status update
        BookingStatusUpdate.objects.create(
            booking=booking,
            updated_by=package_request.user,
            old_status='',
            new_status='pending',
            reason='Booking created'
        )

        return booking

class BookingStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Booking.STATUS_CHOICES)
    reason = serializers.CharField(required=False, allow_blank=True) 