from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Profile, OTP, DiditVerificationSession
from django.utils import timezone
from listings.models import Region, Country
from listings.serializers import RegionSerializer, CountrySerializer
from .models import IdType
from django.conf import settings
from config.utils import upload_image, delete_image, optimized_image_url, auto_crop_url
import json

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model
    """
    location = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'first_name', 'last_name', 'is_active', 'date_joined',
                  'profile', 'is_identity_verified', 'is_phone_verified', 'location']
        read_only_fields = ['id', 'date_joined']

    def get_location(self, obj):
        if hasattr(obj, 'profile') and obj.profile:
            # Try to get location from preferences
            preferences = obj.profile.preferences
            if isinstance(preferences, dict) and 'location' in preferences:
                return preferences['location']
            elif isinstance(preferences, str) and preferences.strip():
                import json
                try:
                    prefs_dict = json.loads(preferences)
                    if 'location' in prefs_dict:
                        return prefs_dict['location']
                except:
                    pass
            # Fall back to country and city of residence
            location_data = {}
            if obj.profile.country_of_residence:
                location_data['country'] = obj.profile.country_of_residence
            if hasattr(obj.profile, 'city_of_residence') and obj.profile.city_of_residence:
                location_data['name'] = obj.profile.city_of_residence.name
                if obj.profile.city_of_residence.country:
                    location_data['country'] = obj.profile.city_of_residence.country.name
                    location_data['countryCode'] = obj.profile.city_of_residence.country.code
            return location_data if location_data else None
        return None


class UserRegistrationSerializer(serializers.ModelSerializer):
    # Only using direct location object approach
    user_location = serializers.JSONField(required=False)

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'phone_number', 'user_location')

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
        # Extract location data
        user_location = validated_data.pop('user_location', None)

        # Extract password (if provided) or mark as unusable
        password = validated_data.pop('password', None)

        # Ensure phone number is normalized before saving
        validated_data['phone_number'] = ''.join(filter(str.isdigit, validated_data['phone_number']))

        user = User.objects.create(
            email=validated_data['email'],
            username=validated_data['username'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone_number=validated_data['phone_number']
        )

        if password:
            user.set_password(password)  # hash password
        else:
            user.set_unusable_password()

        # Make user inactive until OTP verification
        user.is_active = False
        user.save()

        # Update profile with location data
        if hasattr(user, 'profile') and user_location:
            profile = user.profile

            # Process location data if provided
            if (
                    isinstance(user_location, dict)
                    and 'name' in user_location
                    and 'country' in user_location
                    and ('country_code' in user_location or 'countryCode' in user_location)
            ):
                from listings.models import LocationData
                from django.db import IntegrityError

                location_data = {
                    'name': user_location['name'],
                    'country': user_location['country'],
                    'country_code': user_location.get('country_code') or user_location.get('countryCode')
                }

                try:
                    location, created = LocationData.objects.get_or_create(**location_data)
                except IntegrityError:
                    try:
                        location = LocationData.objects.get(**location_data)
                    except LocationData.DoesNotExist:
                        raise

                preferences = profile.preferences or {}
                if isinstance(preferences, str) and preferences.strip():
                    import json
                    try:
                        preferences = json.loads(preferences)
                    except:
                        preferences = {}
                elif not isinstance(preferences, dict):
                    preferences = {}

                preferences['location'] = {
                    'id': location.id,
                    'name': location.name,
                    'country': location.country,
                    'countryCode': location.country_code
                }
                profile.preferences = preferences
                profile.save()

        return user


class IdTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdType
        fields = ['id', 'name', 'description']


class ProfileSerializer(serializers.ModelSerializer):
    # Legacy fields - will be deprecated
    city_of_residence = serializers.SerializerMethodField()  # mapped from user_location
    city_of_residence_id = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.all(), source='city_of_residence',
        write_only=True, required=False
    )
    issue_country = CountrySerializer(read_only=True)
    issue_country_id = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(), source='issue_country',
        write_only=True, required=False
    )

    # New field for direct location data
    user_location_data = serializers.SerializerMethodField(read_only=True)
    user_location_input = serializers.DictField(write_only=True, required=False)

    id_type = IdTypeSerializer(read_only=True)
    id_type_id = serializers.PrimaryKeyRelatedField(
        queryset=IdType.objects.all(), source='id_type', write_only=True,
        required=False
    )

    profile_picture = serializers.ImageField(write_only=True, required=False)
    front_side_identity_card = serializers.ImageField(write_only=True, required=False)
    back_side_identity_card = serializers.ImageField(write_only=True, required=False)
    selfie_photo = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Profile
        fields = (
            'id',
            'full_name',
            'gender',
            'date_of_birth',
            'nationality',
            'country_of_residence',
            'kyc_method',
            'two_factor_enabled',
            'device_fingerprint',
            'ip_address_last_login',
            'app_version',
            'device_os',
            'referral_code_used',
            'last_active',
            'total_trips_created',
            'total_offer_sent',
            'total_offer_received',
            'total_completed_deliveries',
            'average_rating',
            'total_rating_received',
            'preferred_payment_method',
            'notification_setting',
            'profile_picture',
            'profile_picture_url',
            'contact_info',
            'languages',
            'travel_history',
            'preferences',
            'selfie_photo_url',
            'selfie_photo',
            'address',
            # Legacy location fields
            'city_of_residence',
            'city_of_residence_id',
            'issue_country',
            'issue_country_id',
            # New location fields
            'user_location_data',
            'user_location_input',
            'id_type',
            'id_type_id',
            'front_side_identity_card_url',
            'front_side_identity_card',
            'back_side_identity_card_url',
            'back_side_identity_card',
            'created_at',
            'updated_at'
        )
        read_only_fields = (
            'created_at', 'updated_at', 'city_of_residence', 'id_type',
            'issue_country', 'user_location_data'
        )

    def get_city_of_residence(self, obj):
        # Map user_location to legacy city_of_residence
        if obj.user_location:
            return {
                'id': obj.user_location.id,
                'name': obj.user_location.name,
                'country': obj.user_location.country,
                'countryCode': obj.user_location.country_code
            }
        return None

    def get_user_location_data(self, obj):
        # Return new user_location_data
        if obj.user_location:
            return {
                'id': obj.user_location.id,
                'name': obj.user_location.name,
                'country': obj.user_location.country,
                'countryCode': obj.user_location.country_code
            }
        return None


    def create(self, validated_data):
        profile_picture = validated_data.pop('profile_picture', None)
        front_side_identity_card = validated_data.pop('front_side_identity_card', None)
        back_side_identity_card = validated_data.pop('back_side_identity_card', None)
        selfie_photo = validated_data.pop('selfie_photo', None)

        instance = Profile.objects.create(**validated_data)
        if profile_picture:
            instance.profile_picture_url = upload_image(profile_picture, f"verlo/profile/profile_{instance.user.id}")
        if front_side_identity_card:
            instance.front_side_identity_card_url = upload_image(front_side_identity_card,
                                                                 f"verlo/front_id/front_id_{instance.user.id}")
        if back_side_identity_card:
            instance.back_side_identity_card_url = upload_image(back_side_identity_card,
                                                                f"verlo/back_id/back_id_{instance.user.id}")
        if selfie_photo:
            instance.selfie_photo_url = upload_image(selfie_photo, f"verlo/selfie/selfie_{instance.user.id}")
        instance.save()
        return instance

    def to_internal_value(self, data):
        """Handle both form data and JSON format for location fields"""
        # Handle form data format for user_location_input
        location_name = data.get('user_location_input[name]')
        location_country = data.get('user_location_input[country]')
        location_country_code = data.get('user_location_input[countryCode]')
        # Also support pickup_location_input[...] as an alias (backward compatibility)
        pickup_location_name = data.get('pickup_location_input[name]')
        pickup_location_country = data.get('pickup_location_input[country]')
        pickup_location_country_code = data.get('pickup_location_input[countryCode]')

        # Handle JSON format for user_location_input
        json_location_input = data.get('user_location_input')

        try:
            print(
                f"DEBUG ProfileSerializer.to_internal_value: content_type= {getattr(getattr(self, 'context', {}).get('request'), 'content_type', None)}")
            print(f"DEBUG ProfileSerializer.to_internal_value: data keys: {list(data.keys())}")
            print(
                f"DEBUG ProfileSerializer.to_internal_value: user_location_input name={location_name} country={location_country} countryCode={location_country_code}")
            print(
                f"DEBUG ProfileSerializer.to_internal_value: pickup_location_input name={pickup_location_name} country={pickup_location_country} countryCode={pickup_location_country_code}")
            print(f"DEBUG ProfileSerializer.to_internal_value: json_location_input={json_location_input}")
        except Exception:
            pass

        # Create a mutable copy of data
        data = data.copy()

        # Handle JSON format first (preferred format)
        if json_location_input and isinstance(json_location_input, dict):
            # JSON format is already in the correct structure
            if all(key in json_location_input for key in ['name', 'country', 'countryCode']):
                print(f"DEBUG ProfileSerializer.to_internal_value: Using JSON format location: {json_location_input}")
                # Ensure it's properly formatted for the update method
                data['user_location_input'] = json_location_input
        # Convert form data to nested dict format (for backward compatibility)
        elif location_name and location_country and location_country_code:
            data['user_location_input'] = {
                'name': location_name,
                'country': location_country,
                'countryCode': location_country_code
            }
            # Remove the flattened form fields
            data.pop('user_location_input[name]', None)
            data.pop('user_location_input[country]', None)
            data.pop('user_location_input[countryCode]', None)
            print(
                f"DEBUG ProfileSerializer.to_internal_value: Converted form data to nested format: {data.get('user_location_input')}")
        elif pickup_location_name and pickup_location_country and pickup_location_country_code:
            data['user_location_input'] = {
                'name': pickup_location_name,
                'country': pickup_location_country,
                'countryCode': pickup_location_country_code
            }
            data.pop('pickup_location_input[name]', None)
            data.pop('pickup_location_input[country]', None)
            data.pop('pickup_location_input[countryCode]', None)
            print(
                f"DEBUG ProfileSerializer.to_internal_value: Converted pickup_* to nested format: {data.get('user_location_input')}")

        # Call parent class to continue validation
        ret = super().to_internal_value(data)

        # Ensure user_location_input is included in validated data
        if 'user_location_input' in data:
            ret['user_location_input'] = data['user_location_input']
            print(
                f"DEBUG ProfileSerializer.to_internal_value: Added user_location_input to ret: {ret['user_location_input']}")

        return ret

    def update(self, instance, validated_data):
        print(f"DEBUG ProfileSerializer.update: validated_data keys= {list(validated_data.keys())}")
        profile_picture = validated_data.pop('profile_picture', None)
        front_side_identity_card = validated_data.pop('front_side_identity_card', None)
        back_side_identity_card = validated_data.pop('back_side_identity_card', None)
        selfie_photo = validated_data.pop('selfie_photo', None)

        # Handle new location format
        user_location_input = validated_data.pop('user_location_input', None)
        print(f"DEBUG ProfileSerializer.update: user_location_input= {user_location_input}")

        if user_location_input and isinstance(user_location_input, dict):
            # Check if we have the required location fields
            if 'name' in user_location_input and 'country' in user_location_input and 'countryCode' in user_location_input:
                from listings.models import LocationData
                from django.db import IntegrityError

                print(
                    f"DEBUG ProfileSerializer.update: Creating LocationData with: name={user_location_input['name']}, country={user_location_input['country']}, country_code={user_location_input['countryCode']}")

                # Prepare location data
                location_data = {
                    'name': user_location_input['name'],
                    'country': user_location_input['country'],
                    'country_code': user_location_input['countryCode']
                }

                # Create or get LocationData object with race condition handling
                try:
                    user_location, created = LocationData.objects.get_or_create(**location_data)
                except IntegrityError:
                    # Handle race condition where another user created the same location
                    try:
                        user_location = LocationData.objects.get(**location_data)
                        created = False
                    except LocationData.DoesNotExist:
                        # If still not found, raise the original error
                        raise

                print(
                    f"DEBUG ProfileSerializer.update: LocationData created/found: {user_location}, created: {created}")

                # Link it to the profile
                instance.user_location = user_location
                print(f"DEBUG ProfileSerializer.update: Set instance.user_location to: {instance.user_location}")

                # Also store in preferences for backward compatibility
                preferences = instance.preferences
                if isinstance(preferences, str) and preferences.strip():
                    import json
                    try:
                        preferences = json.loads(preferences)
                    except:
                        preferences = {}
                elif not isinstance(preferences, dict):
                    preferences = {}

                preferences['location'] = {
                    'id': user_location.id,
                    'name': user_location.name,
                    'country': user_location.country,
                    'countryCode': user_location.country_code
                }
                # Convert preferences to JSON string
                instance.preferences = json.dumps(preferences)
                print(f"DEBUG ProfileSerializer.update: Updated preferences with location: {preferences['location']}")
            else:
                print(
                    f"DEBUG ProfileSerializer.update: Missing required location fields in user_location_input: {user_location_input}")
        else:
            print(f"DEBUG ProfileSerializer.update: No user_location_input found or not a dict")

        # Update Profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if profile_picture:
            instance.profile_picture_url = upload_image(profile_picture, f"verlo/profile/profile_{instance.user.id}")

        if front_side_identity_card:
            instance.front_side_identity_card_url = upload_image(front_side_identity_card,
                                                                 f"verlo/front_id/front_id_{instance.user.id}")

        if back_side_identity_card:
            instance.back_side_identity_card_url = upload_image(back_side_identity_card,
                                                                f"verlo/back_id/back_id_{instance.user.id}")

        if selfie_photo:
            instance.selfie_photo_url = upload_image(selfie_photo, f"verlo/selfie/selfie_{instance.user.id}")

        instance.save()
        print(f"DEBUG ProfileSerializer.update: Saved instance with user_location: {instance.user_location}")
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
        # Ensure phone number is normalized before saving
        validated_data['phone_number'] = ''.join(filter(str.isdigit, validated_data['phone_number']))
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


class DiditVerificationSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiditVerificationSession
        fields = (
            'id', 'user', 'session_id', 'session_number', 'session_token',
            'vendor_data', 'metadata', 'status', 'workflow_id',
            'callback_url', 'verification_url', 'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at', 'user')


class DiditIdVerificationSerializer(serializers.Serializer):
    session_id = serializers.CharField(required=True)
    session_number = serializers.IntegerField(required=False, allow_null=True)
    session_token = serializers.CharField(required=True)
    vendor_data = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    metadata = serializers.JSONField(required=False)
    status = serializers.CharField(required=True)
    workflow_id = serializers.CharField(required=True)
    callback = serializers.URLField(required=False, allow_blank=True)
    url = serializers.URLField(required=False, allow_blank=True)


class DiditPhoneSendSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True, help_text="Phone number in E.164 format (e.g. +14155552671)")

    def validate_phone_number(self, value):
        # Basic E.164 validation - must start with + followed by digits
        if not value.startswith('+') or not value[1:].isdigit():
            raise serializers.ValidationError("Phone number must be in E.164 format (e.g. +14155552671)")
        return value


class DiditPhoneCheckSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True, help_text="Phone number in E.164 format (e.g. +14155552671)")
    code = serializers.CharField(required=True, min_length=4, max_length=8)

    def validate_phone_number(self, value):
        # Basic E.164 validation - must start with + followed by digits
        if not value.startswith('+') or not value[1:].isdigit():
            raise serializers.ValidationError("Phone number must be in E.164 format (e.g. +14155552671)")
        return value
