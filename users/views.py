from django.shortcuts import render
from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Profile, OTP, User
from .serializers import (
    UserRegistrationSerializer, UserProfileSerializer, ProfileSerializer,
    OTPSerializer, PasswordChangeSerializer, PrivacyPolicyAcceptanceSerializer,
    UserSerializer, OTPVerificationSerializer, ResendOTPSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer
)
from .utils import send_verification_email
import random
import string
from config.views import StandardResponseViewSet
from config.utils import standard_response

User = get_user_model()

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
            # Generate and send OTP for email verification
            otp = ''.join(random.choices(string.digits, k=6))
            OTP.objects.create(user=user, code=otp, purpose='email_verification')
            
            try:
                # Send verification email
                send_verification_email(user, otp)
                return standard_response(
                    data={
                        'message': 'Registration successful. Please check your email for verification code.',
                        'user_id': user.id
                    },
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                # If email sending fails, still return success but with a warning
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
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
            )

        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
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
                    'message': 'Password reset OTP sent successfully',
                    'user_id': user.id
                },
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return standard_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=[f'Failed to send OTP: {str(e)}']
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
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=[f"{field}: {error[0]}" for field, error in serializer.errors.items()]
            )

        user_id = serializer.validated_data['user_id']
        otp_code = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        try:
            otp = OTP.objects.get(
                user_id=user_id,
                code=otp_code,
                purpose='password_reset',
                is_used=False,
                created_at__gte=timezone.now() - timezone.timedelta(minutes=1000)
            )
        except OTP.DoesNotExist:
            return standard_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=['Invalid or expired OTP']
            )

        # Mark OTP as used
        otp.is_used = True
        otp.save()

        # Update user's password
        user = otp.user
        user.set_password(new_password)
        user.save()

        return standard_response(
            data={'message': 'Password reset successful'},
            status_code=status.HTTP_200_OK
        )

class ProfileViewSet(StandardResponseViewSet):
    """
    API endpoint for user profiles
    """
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_object(self):
        return self.request.user.profile

    def perform_update(self, serializer):
        serializer.save()
        # Profile completion status is automatically updated via the Profile model's save method
