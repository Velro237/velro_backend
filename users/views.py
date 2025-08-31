from django.shortcuts import render
from rest_framework import viewsets, status, generics, permissions
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Profile, OTP, CustomUser, IdType
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer, ProfileSerializer,
    OTPSerializer, PasswordChangeSerializer, PrivacyPolicyAcceptanceSerializer,
    UserSerializer, OTPVerificationSerializer, ResendOTPSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer, SetPasswordSerializer, TelegramUserRegistrationSerializer, IdTypeSerializer,
    DiditIdVerificationSerializer, DiditPhoneSendSerializer, DiditPhoneCheckSerializer
)
from .utils import send_verification_email
import random
import string
import requests
import os
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

        # Try to find the user by email or username or phone (normalize phone)
        normalized_username = username
        if username and username.replace('+', '').isdigit():
            normalized_username = ''.join(filter(str.isdigit, username))
        try:
            user = CustomUser.objects.get(
                models.Q(email=username) |
                models.Q(username=username) |
                models.Q(phone_number=normalized_username)
            )
        except CustomUser.DoesNotExist:
            return standard_response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error=['Invalid credentials']
            )

        # Check if the password is correct
        if not user.check_password(password):
            print("Invalid password attempt for user:", user.username, "Email:", user.email)
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

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Refresh token is required']
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return standard_response(
                data={'message': 'Successfully logged out'},
                status_code=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[str(e)]
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
        if self.action in ['register', 'verify_otp', 'resend_otp', 'forgot_password', 'verify_phone_firebase', 'validate_otp']:
            return [AllowAny()]
        return super().get_permissions()

    def get_object(self):
        """
        Ensure users can only access their own account
        """
        obj = super().get_object()
        if self.request.user.is_superuser:
            return obj
        if obj != self.request.user:
            raise PermissionDenied("You can only access your own account")
        return obj

    def update(self, request, *args, **kwargs):
        """
        Ensure users can only update their own account
        """
        if not request.user.is_superuser and request.user.id != int(kwargs.get('pk')):
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
        if not request.user.is_superuser:
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
                # Normalize phone number for lookup
                normalized_identifier = ''.join(filter(str.isdigit, identifier))
                # Find user by normalized phone number
                try:
                    user = User.objects.get(phone_number=normalized_identifier)
                except User.DoesNotExist:
                    return standard_response(
                        status_code=status.HTTP_404_NOT_FOUND,
                        error=['User not found']
                    )

                try:
                    # Format phone number with E.164 format
                    phone_number = user.phone_number
                    if not phone_number.startswith('+'):
                        phone_number = '+' + phone_number
                        
                    # Prepare request data and headers for Didit.me API
                    payload = {
                        "phone_number": phone_number
                    }
                    
                    headers = {
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "X-Api-Key": settings.DIDIT_API_KEY
                    }
                    
                    # Make the API request to send verification code
                    response = requests.post(
                        settings.DIDIT_PHONE_SEND_URL,
                        headers=headers,
                        json=payload
                    )
                    
                    # Process the response
                    if response.status_code == 200:
                        response_data = response.json()
                        request_id = response_data.get('request_id')
                        api_status = response_data.get('status')
                        
                        if api_status == "Success":
                            # Create OTP record in database with request_id
                            OTP.objects.create(
                                user=user,
                                code='',  # Leave code empty as we're using request_id
                                request_id=request_id,  # Store request_id in proper field
                                purpose='password_reset'
                            )
                            
                            return standard_response(
                                data={
                                    'message': 'Password reset code sent successfully to your phone',
                                    'user_id': user.id,
                                    'request_id': request_id
                                },
                                status_code=status.HTTP_200_OK
                            )
                        else:
                            reason = response_data.get('reason', 'Unknown reason')
                            return standard_response(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                error=[f'Failed to send verification code: {reason}']
                            )
                    else:
                        return standard_response(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            error=[f'API returned error: {response.text}']
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
                # Format phone number with E.164 format
                phone_number = user.phone_number
                if not phone_number.startswith('+'):
                    phone_number = '+' + phone_number
                
                # Prepare request data and headers for Didit.me API
                payload = {
                    "phone_number": phone_number,
                    "code": verification_code
                }
                
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Api-Key": settings.DIDIT_API_KEY
                }
                
                # Make the API request to verify code
                response = requests.post(
                    settings.DIDIT_PHONE_CHECK_URL,
                    headers=headers,
                    json=payload
                )
                
                # Process the response
                if response.status_code == 200:
                    verification_data = response.json()
                    status_result = verification_data.get('status')
                    
                    if status_result != "Approved":
                        message = verification_data.get('message', 'Verification failed')
                        return standard_response(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            error=[message]
                        )
                        
                    # Mark OTP as used
                    OTP.objects.filter(
                        user=user,
                        purpose='password_reset',
                        is_used=False
                    ).update(is_used=True)
                else:
                    return standard_response(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=[f'Verification API returned error: {response.text}']
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
    
    
    ##################################################
    ##################################################            
    # endpoint to send otp code to email or phone number and validate it
    # extra action to validate that the opt send from the frontend is exist and not used
    @action(detail=False, methods=['post'])
    def validate_otp(self, request):
        user_id = request.data.get('user_id')
        verification_method = request.data.get('verification_method')  # 'email' or 'phone'
        verification_code = request.data.get('verification_code')

        if not all([user_id, verification_method, verification_code]):
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['All fields are required: user_id, verification_method, verification_code']
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

            return standard_response(
                data={'message': 'OTP is valid'},
                status_code=status.HTTP_200_OK
            )

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

                return standard_response(
                    data={'message': 'OTP is valid'},
                    status_code=status.HTTP_200_OK
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
        else:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Invalid verification method. Use "email" or "phone"']
            )
    ##################################################
    ##################################################
    @action(detail=False, methods=['post'])
    def send_phone_otp(self, request):
        """
        Send a verification code to phone number using Didit.me API
        """
        serializer = DiditPhoneSendSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
            )
            
        user = request.user
        phone_number = serializer.validated_data['phone_number']
        
        # Call Didit.me API to send verification code
        try:
            # Prepare request data and headers
            payload = {
                "phone_number": phone_number
            }
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Api-Key": settings.DIDIT_API_KEY
            }
            
            # Make the API request
            response = requests.post(
                settings.DIDIT_PHONE_SEND_URL,
                headers=headers,
                json=payload
            )
            
            # Process the response
            if response.status_code == 200:
                response_data = response.json()
                request_id = response_data.get('request_id')
                api_status = response_data.get('status')
                
                if api_status == "Success":
                    # Create OTP record in database with request_id in separate field
                    OTP.objects.create(
                        user=user,
                        code='',  # Leave code empty as we're using request_id
                        request_id=request_id,  # Store request_id in the proper field
                        purpose='phone_verification'
                    )
                    
                    # Store the phone number in user's profile for later verification
                    user.phone_number = phone_number
                    user.save()
                    
                    return standard_response(
                        data={
                            'message': 'Verification code sent successfully',
                            'request_id': request_id
                        },
                        status_code=status.HTTP_200_OK
                    )
                else:
                    reason = response_data.get('reason', 'Unknown reason')
                    return standard_response(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=[f"Failed to send verification code: {reason}"]
                    )
            else:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=[f"API returned error: {response.text}"]
                )
                
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f"An error occurred during phone verification: {str(e)}"]
            )

    @action(detail=False, methods=['post'])
    def verify_phone_otp(self, request):
        """
        Verify the phone verification code using Didit.me API
        """
        serializer = DiditPhoneCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
            )
            
        user = request.user
        phone_number = serializer.validated_data['phone_number']
        verification_code = serializer.validated_data['code']
        
        # Call Didit.me API to verify the code
        try:
            # Prepare request data and headers
            payload = {
                "phone_number": phone_number,
                "code": verification_code
            }
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Api-Key": settings.DIDIT_API_KEY
            }
            
            # Make the API request
            response = requests.post(
                settings.DIDIT_PHONE_CHECK_URL,
                headers=headers,
                json=payload
            )
            
            # Process the response
            if response.status_code == 200:
                verification_data = response.json()
                request_id = verification_data.get('request_id')
                status_result = verification_data.get('status')
                
                if status_result == "Approved":
                    # Update user's phone verification status
                    user.is_phone_verified = True
                    user.phone_number = phone_number
                    user.save()
                    
                    # Mark OTPs as used
                    OTP.objects.filter(
                        user=user,
                        purpose='phone_verification',
                        is_used=False
                    ).update(is_used=True)
                    
                    # Get phone details from the response
                    phone_details = verification_data.get('phone', {})
                    
                    return standard_response(
                        data={
                            'message': 'Phone number verified successfully',
                            'verification_status': 'approved',
                            'phone_details': {
                                'country_code': phone_details.get('country_code'),
                                'country_name': phone_details.get('country_name'),
                                'carrier': phone_details.get('carrier', {}).get('name'),
                                'carrier_type': phone_details.get('carrier', {}).get('type'),
                                'verified_at': phone_details.get('verified_at')
                            }
                        },
                        status_code=status.HTTP_200_OK
                    )
                else:
                    message = verification_data.get('message', 'Verification failed')
                    return standard_response(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=[message]
                    )
            else:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=[f"Verification API returned error: {response.text}"]
                )
                
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f"An error occurred during phone verification: {str(e)}"]
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

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_telegram(self, request):
        api_key = request.headers.get('X-Telegram-Bot-Api-Key')
        print("-----------")
        print(api_key)
        print(getattr(settings, 'TELEGRAM_BOT_API', None))
        print(settings.TELEGRAM_BOT_API)
        print("-----------")
        if not api_key or api_key != getattr(settings, 'TELEGRAM_BOT_API', None):
            return standard_response(
                status_code=status.HTTP_403_FORBIDDEN,
                error=["Invalid or missing Telegram Bot API key."]
            )
        serializer = TelegramUserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return standard_response(
                data={
                    'message': 'Registration successful.',
                    'user': UserSerializer(user).data
                },
                status_code=status.HTTP_201_CREATED
            )
        return standard_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
        )

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def verify_phone_firebase(self, request):
        """
        Verifies a user's phone number using a Firebase ID token.
        Expects: { "firebase_id_token": "...", "user_id": ... }
        """
        from django.conf import settings
        try:
            import firebase_admin
            from firebase_admin import auth as firebase_auth
        except ImportError:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=["firebase-admin is not installed on the server."]
            )

        firebase_id_token = request.data.get('firebase_id_token')
        user_id = request.data.get('user_id')
        if not firebase_id_token or not user_id:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=["firebase_id_token and user_id are required."]
            )
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return standard_response(
                status_code=status.HTTP_404_NOT_FOUND,
                error=["User not found."]
            )
        # Initialize Firebase app if not already
        if not firebase_admin._apps:
            cred = getattr(settings, 'FIREBASE_CREDENTIAL', None)
            if cred is None:
                return standard_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    error=["FIREBASE_CREDENTIAL is not configured in settings."]
                )
            firebase_admin.initialize_app(cred)
        try:
            decoded_token = firebase_auth.verify_id_token(firebase_id_token)
            print("Decoded Firebase Token: ##################33")
            print(decoded_token)
            phone_number = decoded_token.get('phone_number')
            if not phone_number:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=["No phone_number found in Firebase token."]
                )
            # Normalize phone number for comparison
            user_phone = ''.join(filter(str.isdigit, user.phone_number))
            firebase_phone = ''.join(filter(str.isdigit, phone_number))
            if user_phone != firebase_phone:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=["Phone number in Firebase token does not match user's phone number."]
                )
            user.is_phone_verified = True
            user.save()
            return standard_response(
                data={"message": "Phone number verified successfully via Firebase."},
                status_code=status.HTTP_200_OK
            )
        except firebase_auth.InvalidIdTokenError:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=["Invalid Firebase ID token."]
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f"An error occurred: {str(e)}"]
            )
                
    @action(detail=False, methods=['post'])
    def verify_id_document(self, request):
        """
        Verifies a user's identity document using the Didit.me API
        Uploads front and back images of ID and processes the verification response
        """
        serializer = DiditIdVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
            )
            
        user = request.user
        front_image = serializer.validated_data['front_image']
        back_image = serializer.validated_data['back_image']
        
        # Call Didit.me API for verification
        try:
            # Prepare files for multipart upload
            files = {
                'front_image': (front_image.name, front_image.file, front_image.content_type),
                'back_image': (back_image.name, back_image.file, back_image.content_type)
            }
            
            # Prepare headers with API key
            headers = {
                "Accept": "application/json",
                "X-Api-Key": settings.DIDIT_API_KEY
            }
            
            # Make the API request
            response = requests.post(
                settings.DIDIT_VERIFICATION_URL,
                headers=headers,
                files=files
            )
            
            # Process the response
            if response.status_code == 200:
                verification_data = response.json()
                request_id = verification_data.get('request_id')
                id_verification = verification_data.get('id_verification', {})
                status_result = id_verification.get('status')
                
                # Update user's identity verification status based on API response
                if status_result == 'Approved':
                    user.is_identity_verified = 'completed'
                elif status_result == 'Declined':
                    user.is_identity_verified = 'rejected'
                else:
                    user.is_identity_verified = 'pending'
                
                user.save()
                
                # Return the verification data
                return standard_response(
                    data={
                        'message': f'ID verification {status_result.lower()}',
                        'verification_status': user.is_identity_verified,
                        'request_id': request_id,
                        'verification_details': {
                            'document_type': id_verification.get('document_type'),
                            'full_name': id_verification.get('full_name'),
                            'issuing_state': id_verification.get('issuing_state_name'),
                            'date_of_birth': id_verification.get('date_of_birth'),
                            'expiration_date': id_verification.get('expiration_date'),
                            'gender': id_verification.get('gender'),
                            'warnings': id_verification.get('warnings', [])
                        }
                    },
                    status_code=status.HTTP_200_OK
                )
            else:
                return standard_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=[f"Verification API returned error: {response.text}"]
                )
                
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f"An error occurred during ID verification: {str(e)}"]
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

class IdTypeViewSet(StandardResponseViewSet):
    """
    API endpoint for ID types
    """
    queryset = IdType.objects.all()
    serializer_class = IdTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save()