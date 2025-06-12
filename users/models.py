from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=15, blank=True)
    is_phone_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    is_identity_verified = models.BooleanField(default=False)
    is_profile_completed = models.BooleanField(default=False)
    is_facebook_verified = models.BooleanField(default=False)
    privacy_policy_accepted = models.BooleanField(default=False)
    date_privacy_accepted = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    contact_info = models.CharField(max_length=255, blank=True)
    languages = models.CharField(max_length=255, blank=True)
    travel_history = models.TextField(blank=True)
    preferences = models.TextField(blank=True)
    identity_card = models.ImageField(upload_to='identity_cards/', blank=True, null=True)
    selfie_photo = models.ImageField(upload_to='selfies/', blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()}'s Profile"

    def save(self, *args, **kwargs):
        # Only save the profile, don't trigger user save
        super().save(*args, **kwargs)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        # Only save the profile if it exists
        if hasattr(instance, 'profile'):
            instance.profile.save()

class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
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
