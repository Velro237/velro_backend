from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Profile, OTP
from django.utils import timezone
from listings.models import Region, Country
from listings.serializers import RegionSerializer, CountrySerializer
from .models import IdType
from django.conf import settings
from config.utils import upload_image, delete_image, optimized_image_url, auto_crop_url
User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'first_name', 'last_name', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'phone_number')

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_phone_number(self, value):
        phone = ''.join(filter(str.isdigit, value))
        if len(phone) < 10 or len(phone) > 15:
            raise serializers.ValidationError("Phone number must be between 10 and 15 digits")
        if User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return phone

    def create(self, validated_data):
        user = User.objects.create(
            email=validated_data['email'],
            username=validated_data['username'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone_number=validated_data['phone_number']
        )
        user.set_unusable_password()
        user.save()
        return user

class IdTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdType
        fields = ['id', 'name', 'description']

class ProfileSerializer(serializers.ModelSerializer):
    city_of_residence = RegionSerializer(read_only=True)
    city_of_residence_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='city_of_residence', write_only=True, required=False)
    id_type = IdTypeSerializer(read_only=True)
    id_type_id = serializers.PrimaryKeyRelatedField(queryset=IdType.objects.all(), source='id_type', write_only=True, required=False)
    issue_country = CountrySerializer(read_only=True)
    issue_country_id = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), source='issue_country', write_only=True, required=False)
   
    profile_picture = serializers.ImageField(write_only=True, required=False)
    front_side_identity_card = serializers.ImageField(write_only=True, required=False)
    back_side_identity_card = serializers.ImageField(write_only=True, required=False)
    selfie_photo = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Profile
        fields = (
            'profile_picture_url', 'profile_picture', 'contact_info', 'languages', 'travel_history', 
            'preferences', 'selfie_photo_url', 'selfie_photo', 'address',
            'city_of_residence', 'city_of_residence_id',
            'id_type', 'id_type_id',
            'issue_country', 'issue_country_id',
            'front_side_identity_card_url', 'front_side_identity_card', 'back_side_identity_card_url', 'back_side_identity_card',
            'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at', 'city_of_residence', 'id_type', 'issue_country')
    
    def create(self, validated_data):
        profile_picture = validated_data.pop('profile_picture', None)
        front_side_identity_card = validated_data.pop('front_side_identity_card', None)
        back_side_identity_card = validated_data.pop('back_side_identity_card', None)
        selfie_photo = validated_data.pop('selfie_photo', None) 

        instance = Profile.objects.create(**validated_data)
        if profile_picture:
            instance.profile_picture_url = upload_image(profile_picture, f"verlo/profile/profile_{instance.user.id}")
        if front_side_identity_card:
            instance.front_side_identity_card_url = upload_image(front_side_identity_card, f"verlo/front_id/front_id_{instance.user.id}")
        if back_side_identity_card:
            instance.back_side_identity_card_url = upload_image(back_side_identity_card, f"verlo/back_id/back_id_{instance.user.id}")
        if selfie_photo:
            instance.selfie_photo_url = upload_image(selfie_photo, f"verlo/selfie/selfie_{instance.user.id}")  
        instance.save() 
        return instance

    def update(self, instance, validated_data):
        profile_picture = validated_data.pop('profile_picture', None)
        front_side_identity_card = validated_data.pop('front_side_identity_card', None)
        back_side_identity_card = validated_data.pop('back_side_identity_card', None)
        selfie_photo = validated_data.pop('selfie_photo', None)

        # Update Profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if profile_picture:
            # if instance.profile_picture_url:
            #     delete_image(instance.profile_picture_url.split('/')[-1].split('.')[0])
            instance.profile_picture_url = upload_image(profile_picture, f"verlo/profile/profile_{instance.user.id}")
        
        if front_side_identity_card:
            instance.front_side_identity_card_url = upload_image(front_side_identity_card, f"verlo/front_id/front_id_{instance.user.id}")
        
        if back_side_identity_card:
            instance.back_side_identity_card_url = upload_image(back_side_identity_card, f"verlo/back_id/back_id_{instance.user.id}")
        
        if selfie_photo:
            instance.selfie_photo_url = upload_image(selfie_photo, f"verlo/selfie/selfie_{instance.user.id}")

        instance.save()
        return instance

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

class SetPasswordSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match"})
        return data

class TelegramUserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'phone_number', 'password', 'confirm_password')

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': "Passwords don't match"})
        return data

    def validate_email(self, value):
        if value:
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_phone_number(self, value):
        phone = ''.join(filter(str.isdigit, value))
        if len(phone) < 10 or len(phone) > 15:
            raise serializers.ValidationError("Phone number must be between 10 and 15 digits")
        if User.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return phone

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        user = User.objects.create(
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            username=validated_data['username'],
            phone_number=validated_data['phone_number'],
            is_phone_verified=True,
            email=validated_data.get('email', None) or None
        )
        user.set_password(validated_data['password'])
        user.save()
        return user 