from django.db import models
from users.models import CustomUser
from listings.models import TravelListing

# Create your models here.

class EventLog(models.Model):
    EVENT_TYPE_CHOICES = [
        ("order_click", "Order Click"),
        ("message_click", "Message Click"),
    ]
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="event_logs")
    trip = models.ForeignKey(TravelListing, on_delete=models.CASCADE, related_name="event_logs")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.event_type} - {self.trip.id} at {self.timestamp}"
