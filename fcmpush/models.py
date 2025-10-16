from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Device(models.Model):
    PLATFORM_CHOICES = [
        ("android", "Android"),
        ("ios", "iOS"),
        ("web", "Web"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="devices")
    registration_token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=32, choices=PLATFORM_CHOICES, default="web")
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.platform}"
