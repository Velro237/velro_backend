from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from config.utils import upload_image, delete_image, optimized_image_url, auto_crop_url

class BaseUser(AbstractUser):
    class Meta:
        abstract = True

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class IdType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
IDENTITY_VERIFICATION_CHOICES = [
    ('pending', 'Pending'),
    ('rejected', 'Rejected'),
    ('completed', 'Completed'),
]

class CustomUser(BaseUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    apple_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    is_identity_verified = models.CharField(
        max_length=10,
        choices=IDENTITY_VERIFICATION_CHOICES,
        default='pending',
    )
    is_profile_completed = models.BooleanField(default=False)
    is_facebook_verified = models.BooleanField(default=False)
    privacy_policy_accepted = models.BooleanField(default=False)
    date_privacy_accepted = models.DateTimeField(null=True, blank=True)
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'phone_number']

    def __str__(self):
        return self.email

class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    contact_info = models.CharField(max_length=255, blank=True)
    languages = models.CharField(max_length=255, blank=True)
    travel_history = models.TextField(blank=True)
    preferences = models.TextField(blank=True)
    address = models.TextField(blank=True, null=True)
    city_of_residence = models.ForeignKey("listings.Region", on_delete=models.SET_NULL, null=True, blank=True, related_name='residents')
    id_type = models.ForeignKey(IdType, on_delete=models.SET_NULL, null=True, blank=True)
    issue_country = models.ForeignKey("listings.Country", on_delete=models.SET_NULL, null=True, blank=True)
    
    profile_picture_url = models.CharField(max_length=255, blank=True, null=True)
    front_side_identity_card_url = models.CharField(max_length=255, blank=True, null=True)
    back_side_identity_card_url = models.CharField(max_length=255, blank=True, null=True)
    selfie_photo_url = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()}'s Profile"


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        # Only save the profile if it exists
        if hasattr(instance, 'profile'):
            instance.profile.save()

class OTP(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    purpose = models.CharField(max_length=20, choices=[
        ('email_verification', 'Email Verification'),
        ('phone_verification', 'Phone Verification'),
        ('password_reset', 'Password Reset')
    ])

    def __str__(self):
        return f"OTP for {self.user.email} - {self.purpose}"

    class Meta:
        ordering = ['-created_at']
