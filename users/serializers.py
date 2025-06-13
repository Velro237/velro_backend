from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Profile, OTP
from django.utils import timezone

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'phone_number', 'password', 'confirm_password')

    def validate_phone_number(self, value):
        # Remove any spaces, dashes, or parentheses
        phone = ''.join(filter(str.isdigit, value))
        
        # Check if the phone number has a valid length (adjust these rules as needed)
        if len(phone) < 10 or len(phone) > 15:
            raise serializers.ValidationError("Phone number must be between 10 and 15 digits")
        
        return phone

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords don't match")
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data)
        return user

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('profile_picture', 'contact_info', 'languages', 'travel_history', 
                 'preferences', 'identity_card', 'selfie_photo')
        read_only_fields = ('created_at', 'updated_at')

class UserProfileSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'phone_number',
                 'is_email_verified', 'is_phone_verified', 'is_identity_verified',
                 'is_profile_completed', 'is_facebook_verified', 'profile', 'verification_status')
        read_only_fields = ('id', 'email', 'is_email_verified', 'is_phone_verified',
                          'is_identity_verified', 'is_profile_completed', 'is_facebook_verified')

    def get_verification_status(self, obj):
        return {
            'email_verified': obj.is_email_verified,
            'phone_verified': obj.is_phone_verified,
            'identity_verified': obj.is_identity_verified,
            'profile_completed': obj.is_profile_completed,
            'facebook_verified': obj.is_facebook_verified
        }

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        
        # Update User fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update Profile fields if profile data is provided
        if profile_data and hasattr(instance, 'profile'):
            profile = instance.profile
            profile_serializer = ProfileSerializer(profile, data=profile_data, partial=True)
            if profile_serializer.is_valid():
                profile_serializer.save()
            else:
                raise serializers.ValidationError(profile_serializer.errors)

        return instance

    def to_representation(self, instance):
        """
        Ensure we always return the latest data
        """
        representation = super().to_representation(instance)
        if hasattr(instance, 'profile'):
            representation['profile'] = ProfileSerializer(instance.profile).data
        return representation

    def validate(self, data):
        """
        Add custom validation if needed
        """
        return data

class OTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTP
        fields = ('code', 'purpose')
        read_only_fields = ('created_at', 'is_used')

class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("New passwords don't match")
        return data

class PrivacyPolicyAcceptanceSerializer(serializers.Serializer):
    accepted = serializers.BooleanField(required=True)

    def validate(self, data):
        if not data['accepted']:
            raise serializers.ValidationError("You must accept the privacy policy to continue")
        return data

class OTPVerificationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    purpose = serializers.ChoiceField(
        required=True,
        choices=['email_verification', 'phone_verification', 'password_reset']
    )

    def validate_user_id(self, value):
        try:
            User.objects.get(id=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value

class ResendOTPSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    purpose = serializers.ChoiceField(
        required=True,
        choices=['email_verification', 'phone_verification', 'password_reset']
    )

    def validate_user_id(self, value):
        try:
            User.objects.get(id=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        try:
            User.objects.get(email=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist")

class ResetPasswordSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)

    def validate_user_id(self, value):
        try:
            User.objects.get(id=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match"})
        return data 