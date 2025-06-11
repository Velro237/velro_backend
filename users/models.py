from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # Add extra fields here if needed
    pass

class Profile(models.Model):
    user = models.OneToOneField('User', on_delete=models.CASCADE, related_name='profile')
    name = models.CharField(max_length=255, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    contact_info = models.CharField(max_length=255, blank=True)
    languages = models.CharField(max_length=255, blank=True)
    travel_history = models.TextField(blank=True)
    preferences = models.TextField(blank=True)

    def __str__(self):
        return self.user.username
