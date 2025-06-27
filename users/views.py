from django.shortcuts import render
from rest_framework import viewsets, status, generics, permissions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Profile, OTP, CustomUser
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer, ProfileSerializer,
    OTPSerializer, PasswordChangeSerializer, PrivacyPolicyAcceptanceSerializer,
    UserSerializer, OTPVerificationSerializer, ResendOTPSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer, SetPasswordSerializer
)
from .utils import send_verification_email
import random
import string
from config.views import StandardResponseViewSet
from config.utils import standard_response
from django.db import models
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import jwt
from datetime import datetime

User = get_user_model()

class UserLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Please provide both username/email and password']
            )

        # Try to find the user by email or username
        try:
            user = CustomUser.objects.get(
                models.Q(email=username) | models.Q(username=username) | models.Q(phone_number=username)
            )
        except CustomUser.DoesNotExist:
            return standard_response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error=['Invalid credentials']
            )

        # Check if the password is correct
        if not user.check_password(password):
            return standard_response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error=['Invalid credentials']
            )

        if not user.is_active:
            return standard_response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error=['User account is disabled']
            )

        refresh = RefreshToken.for_user(user)
        
        return standard_response(
            data={
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            },
            status_code=status.HTTP_200_OK
        )

class UserViewSet(StandardResponseViewSet):
    """
    API endpoint for users
    """
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Exclude superusers from the list
        """
        return User.objects.filter(is_superuser=False)

    def get_permissions(self):
        if self.action in ['register', 'verify_otp', 'resend_otp', 'forgot_password']:
            return [AllowAny()]
        return super().get_permissions()

    def get_object(self):
        """
        Ensure users can only access their own account
        """
        obj = super().get_object()
        if obj != self.request.user:
            raise PermissionDenied("You can only access your own account")
        return obj

    def update(self, request, *args, **kwargs):
        """
        Ensure users can only update their own account
        """
        if request.user.id != int(kwargs.get('pk')):
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=["You can only update your own account"]
            )
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return standard_response(
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def perform_update(self, serializer):
        serializer.save()

    def partial_update(self, request, *args, **kwargs):
        """
        Ensure users can only partially update their own account
        """
        if request.user.id != int(kwargs.get('pk')):
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=["You can only update your own account"]
            )
        
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return standard_response(
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        """
        Ensure users can only delete their own account
        """
        if request.user.id != int(kwargs.get('pk')):
            raise PermissionDenied("You can only delete your own account")
        instance = self.get_object()
        self.perform_destroy(instance)
        return standard_response(
            data={"message": "User deleted successfully"},
            status_code=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            otp = ''.join(random.choices(string.digits, k=6))
            OTP.objects.create(user=user, code=otp, purpose='email_verification')
            try:
                send_verification_email(user, otp)
                return standard_response(
                    data={
                        'message': 'Registration successful. Please check your email for verification code.',
                        'user_id': user.id
                    },
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return standard_response(
                    data={
                        'message': 'Registration successful but email verification failed. Please try resending OTP.',
                        'user_id': user.id,
                        'warning': str(e)
                    },
                    status_code=status.HTTP_201_CREATED
                )
        return standard_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
        )

    @action(detail=False, methods=['post'])
    def verify_otp(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
            )

        user_id = serializer.validated_data['user_id']
        otp_code = serializer.validated_data['otp']
        purpose = serializer.validated_data['purpose']

        try:
            otp = OTP.objects.get(
                user_id=user_id,
                code=otp_code,
                purpose=purpose,
                is_used=False,
                created_at__gte=timezone.now() - timezone.timedelta(minutes=10)
            )
        except OTP.DoesNotExist:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Invalid or expired OTP']
            )

        otp.is_used = True
        otp.save()

        if purpose == 'email_verification':
            otp.user.is_email_verified = True
            otp.user.save()
        elif purpose == 'phone_verification':
            otp.user.is_phone_verified = True
            otp.user.save()

        return standard_response(
            data={'message': 'Verification successful'},
            status_code=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'])
    def resend_otp(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
            )

        user_id = serializer.validated_data['user_id']
        purpose = serializer.validated_data['purpose']

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return standard_response(
                status_code=status.HTTP_404_NOT_FOUND,
                error=['User not found']
            )

        # Generate new OTP
        otp = ''.join(random.choices(string.digits, k=6))
        OTP.objects.create(user=user, code=otp, purpose=purpose)

        # Send OTP via email
        try:
            if purpose == 'email_verification':
                send_verification_email(user, otp)
            elif purpose == 'password_reset':
                # You can create a different email template for password reset
                send_verification_email(user, otp)
            
            return standard_response(
                data={'message': 'OTP sent successfully'},
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f'Failed to send OTP: {str(e)}']
            )

    @action(detail=False, methods=['post'])
    def forgot_password(self, request):
        verification_method = request.data.get('verification_method')  # 'email' or 'phone'
        identifier = request.data.get('identifier')  # email or phone number

        if not verification_method or not identifier:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Verification method and identifier (email/phone) are required']
            )

        try:
            if verification_method == 'email':
                # Find user by email
                try:
                    user = User.objects.get(email=identifier)
                except User.DoesNotExist:
                    return standard_response(
                        status_code=status.HTTP_404_NOT_FOUND,
                        error=['User not found']
                    )

                # Generate OTP
                otp = ''.join(random.choices(string.digits, k=6))
                OTP.objects.create(user=user, code=otp, purpose='password_reset')

                # Send OTP via email
                try:
                    send_verification_email(user, otp)
                    return standard_response(
                        data={
                            'message': 'Password reset OTP sent successfully to your email',
                            'user_id': user.id
                        },
                        status_code=status.HTTP_200_OK
                    )
                except Exception as e:
                    return standard_response(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        error=[f'Failed to send OTP: {str(e)}']
                    )

            elif verification_method == 'phone':
                # Find user by phone number
                try:
                    user = User.objects.get(phone_number=identifier)
                except User.DoesNotExist:
                    return standard_response(
                        status_code=status.HTTP_404_NOT_FOUND,
                        error=['User not found']
                    )

                try:
                    # Initialize Twilio client
                    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    
                    # Send verification code via Twilio
                    verification = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE) \
                        .verifications \
                        .create(to=identifier, channel='sms')

                    # Create OTP record in database
                    OTP.objects.create(
                        user=user,
                        code='',  # We don't store the actual code as Twilio handles it
                        purpose='password_reset'
                    )

                    return standard_response(
                        data={
                            'message': 'Password reset OTP sent successfully to your phone',
                            'user_id': user.id,
                            'verification_sid': verification.sid
                        },
                        status_code=status.HTTP_200_OK
                    )

                except TwilioRestException as e:
                    return standard_response(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=[f'Failed to send OTP: {str(e)}']
                    )
                except Exception as e:
                    return standard_response(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        error=[f'An error occurred: {str(e)}']
                    )

            else:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=['Invalid verification method. Use "email" or "phone"']
                )

        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f'An error occurred: {str(e)}']
            )

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data['old_password']):
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=['Invalid old password']
                )
            
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return standard_response(
                data={'message': 'Password changed successfully'},
                status_code=status.HTTP_200_OK
            )
        return standard_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
        )

    @action(detail=False, methods=['post'])
    def accept_privacy_policy(self, request):
        serializer = PrivacyPolicyAcceptanceSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            user.privacy_policy_accepted = True
            user.date_privacy_accepted = timezone.now()
            user.save()
            return standard_response(
                data={'message': 'Privacy policy accepted'},
                status_code=status.HTTP_200_OK
            )
        return standard_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
        )

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return standard_response(
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def reset_password(self, request):
        user_id = request.data.get('user_id')
        verification_method = request.data.get('verification_method')  # 'email' or 'phone'
        verification_code = request.data.get('verification_code')
        new_password = request.data.get('new_password')

        if not all([user_id, verification_method, verification_code, new_password]):
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['All fields are required: user_id, verification_method, verification_code, new_password']
            )

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return standard_response(
                status_code=status.HTTP_404_NOT_FOUND,
                error=['User not found']
            )

        if verification_method == 'email':
            try:
                otp = OTP.objects.get(
                    user_id=user_id,
                    code=verification_code,
                    purpose='password_reset',
                    is_used=False,
                    created_at__gte=timezone.now() - timezone.timedelta(minutes=10)
                )
            except OTP.DoesNotExist:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=['Invalid or expired OTP']
                )

            # Mark OTP as used
            otp.is_used = True
            otp.save()

        elif verification_method == 'phone':
            try:
                # Initialize Twilio client
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                
                # Verify the code
                verification_check = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE) \
                    .verification_checks \
                    .create(to=user.phone_number, code=verification_code)

                if verification_check.status != 'approved':
                    return standard_response(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=['Invalid verification code']
                    )

                # Mark OTP as used
                OTP.objects.filter(
                    user=user,
                    purpose='password_reset',
                    is_used=False
                ).update(is_used=True)

            except TwilioRestException as e:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=[f'Verification failed: {str(e)}']
                )
            except Exception as e:
                return standard_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    error=[f'An error occurred: {str(e)}']
                )
        else:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Invalid verification method. Use "email" or "phone"']
            )

        # Update user's password
        user.set_password(new_password)
        user.save()

        return standard_response(
            data={'message': 'Password reset successful'},
            status_code=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'])
    def send_phone_otp(self, request):
        user = request.user
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Phone number is required']
            )

        try:
            # Initialize Twilio client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            # Send verification code via Twilio
            verification = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE) \
                .verifications \
                .create(to=phone_number, channel='sms')

            # Create OTP record in database
            otp = OTP.objects.create(
                user=user,
                code='',  # We don't store the actual code as Twilio handles it
                purpose='phone_verification'
            )

            return standard_response(
                data={
                    'message': 'OTP sent successfully',
                    'verification_sid': verification.sid
                },
                status_code=status.HTTP_200_OK
            )

        except TwilioRestException as e:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f'Failed to send OTP: {str(e)}']
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f'An error occurred: {str(e)}']
            )

    @action(detail=False, methods=['post'])
    def verify_phone_otp(self, request):
        user = request.user
        phone_number = request.data.get('phone_number')
        verification_code = request.data.get('verification_code')

        if not phone_number or not verification_code:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Phone number and verification code are required']
            )

        try:
            # Initialize Twilio client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            # Verify the code
            verification_check = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE) \
                .verification_checks \
                .create(to=phone_number, code=verification_code)

            if verification_check.status == 'approved':
                # Update user's phone verification status
                user.is_phone_verified = True
                user.phone_number = phone_number
                user.save()

                # Mark OTP as used
                OTP.objects.filter(
                    user=user,
                    purpose='phone_verification',
                    is_used=False
                ).update(is_used=True)

                return standard_response(
                    data={'message': 'Phone number verified successfully'},
                    status_code=status.HTTP_200_OK
                )
            else:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=['Invalid verification code']
                )

        except TwilioRestException as e:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f'Verification failed: {str(e)}']
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f'An error occurred: {str(e)}']
            )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def set_password(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
            )
        user_id = serializer.validated_data['user_id']
        password = serializer.validated_data['password']
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return standard_response(
                status_code=status.HTTP_404_NOT_FOUND,
                error=['User not found']
            )

        # Check if email is verified
        if not user.is_email_verified:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Email is not verified.']
            )

        # Check if password has already been set
        if user.has_usable_password():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Password has already been set. Use the password reset flow to change your password.']
            )

        user.set_password(password)
        user.save()
        return standard_response(
            data={'message': 'Password set successfully. You can now log in.'},
            status_code=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_google(self, request):
        """
        Secure Google registration. Requires id_token, username, phone_number.
        Verifies id_token, extracts Google profile info, and creates user with verified email.
        """
        id_token_str = request.data.get('id_token')
        username = request.data.get('username')
        phone_number = request.data.get('phone_number')

        if not all([id_token_str, username, phone_number]):
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['id_token, username, and phone_number are required']
            )

        # Verify the Google id_token
        try:
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
        except ValueError as e:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f'Invalid token: {str(e)}']
            )

        # Check if email or username already exists
        if CustomUser.objects.filter(email=email).exists():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=["A user with this email already exists."]
            )
        if CustomUser.objects.filter(username=username).exists():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=["A user with this username already exists."]
            )

        user = CustomUser.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            username=username,
            phone_number=phone_number,
            is_email_verified=True
        )
        # Do NOT set password here. User will set password later using set_password endpoint.

        return standard_response(
            data={
                'message': 'Registration successful. Please set your password using the set_password endpoint.',
                'user': UserSerializer(user).data
            },
            status_code=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def google_profile_info(self, request):
        """
        Accepts a Google id_token, verifies it, and returns first_name, last_name, and email.
        Does not create a user.
        """
        id_token_str = request.data.get('id_token')
        if not id_token_str:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Google id_token is required']
            )
        try:
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            return standard_response(
                data={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email
                },
                status_code=status.HTTP_200_OK
            )
        except ValueError as e:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f'Invalid token: {str(e)}']
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f'An error occurred: {str(e)}']
            )

class ProfileViewSet(StandardResponseViewSet):
    """
    API endpoint for user profiles
    """
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        """
        Allow any authenticated user to view profiles
        Restrict create, update, delete to profile owners
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """
        Any authenticated user can see all profiles
        """
        return Profile.objects.all()

    def get_object(self):
        """
        Any authenticated user can view any profile
        """
        return super().get_object()

    def create(self, request, *args, **kwargs):
        """
        Only allow users to create their own profile
        """
        if hasattr(request.user, 'profile'):
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Profile already exists']
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """
        Ensure the profile is created for the current user
        """
        serializer.save(user=self.request.user)

    def update(self, request, *args, **kwargs):
        """
        Only allow users to update their own profile
        """
        instance = self.get_object()
        if instance.user != request.user:
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=['You can only update your own profile']
            )
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return standard_response(
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def partial_update(self, request, *args, **kwargs):
        """
        Only allow users to partially update their own profile
        """
        instance = self.get_object()
        if instance.user != request.user:
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=['You can only update your own profile']
            )
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return standard_response(
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        """
        Only allow users to delete their own profile
        """
        instance = self.get_object()
        if instance.user != request.user:
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=['You can only delete your own profile']
            )
        self.perform_destroy(instance)
        return standard_response(
            data={'message': 'Profile deleted successfully'},
            status_code=status.HTTP_200_OK
        )

    def perform_update(self, serializer):
        serializer.save()
        # Profile completion status is automatically updated via the Profile model's save method

class TokenRefreshView(BaseTokenRefreshView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return standard_response(
            data={
                'access': response.data.get('access'),
                'refresh': response.data.get('refresh')
            },
            status_code=response.status_code
        )

class GoogleSignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Google token is required']
            )

        try:
            # Verify the token
            print(settings.GOOGLE_CLIENT_ID)
            print(token)
            idinfo = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )

            # Get user info from the token
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            google_id = idinfo['sub']

            # Try to find existing user
            try:
                user = CustomUser.objects.get(email=email)
                # Update Google ID if not set
                if not user.google_id:
                    user.google_id = google_id
                    user.save()
            except CustomUser.DoesNotExist:
                # Create new user
                username = email.split('@')[0]
                # Ensure username is unique
                base_username = username
                counter = 1
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = CustomUser.objects.create(
                    email=email,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    google_id=google_id,
                    is_email_verified=True  # Email is verified by Google
                )

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return standard_response(
                data={
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': UserSerializer(user).data
                },
                status_code=status.HTTP_200_OK
            )

        except ValueError as e:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f'Invalid token: {str(e)}']
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f'An error occurred: {str(e)}']
            )

class AppleSignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Apple token is required']
            )

        try:
            # Verify the token
            headers = {
                'kid': settings.APPLE_KEY_ID
            }
            
            # Get Apple's public key
            response = requests.get(settings.APPLE_PUBLIC_KEY_URL)
            public_key = response.json()

            # Verify the token
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=settings.APPLE_BUNDLE_ID,
                issuer='https://appleid.apple.com'
            )

            # Get user info from the token
            email = decoded.get('email')
            apple_id = decoded['sub']

            # Try to find existing user
            try:
                user = CustomUser.objects.get(email=email)
                # Update Apple ID if not set
                if not user.apple_id:
                    user.apple_id = apple_id
                    user.save()
            except CustomUser.DoesNotExist:
                # Create new user
                username = email.split('@')[0]
                # Ensure username is unique
                base_username = username
                counter = 1
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = CustomUser.objects.create(
                    email=email,
                    username=username,
                    apple_id=apple_id,
                    is_email_verified=True  # Email is verified by Apple
                )

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return standard_response(
                data={
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': UserSerializer(user).data
                },
                status_code=status.HTTP_200_OK
            )

        except jwt.InvalidTokenError as e:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f'Invalid token: {str(e)}']
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f'An error occurred: {str(e)}']
            )
