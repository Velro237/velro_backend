from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

def send_verification_email(user, otp_code):
    """
    Send verification email with OTP code
    """
    subject = 'Verify Your Email - P2P Kilosales'
    
    try:
        # Debug prints
        print("Email Settings:")
        print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
        print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
        print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
        print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
        print(f"EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 'Not set'}")
        
        # Render the HTML template
        html_message = render_to_string('email_verification.html', {
            'user': user,
            'otp_code': otp_code
        })
        
        # Create plain text version
        plain_message = strip_tags(html_message)
        
        print(f"\nAttempting to send verification email to {user.email}")
        print(f"Email content: {plain_message}")
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"Verification email sent successfully to {user.email}")
    except Exception as e:
        print(f"Failed to send verification email to {user.email}: {str(e)}")
        raise 