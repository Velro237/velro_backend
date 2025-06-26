from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TravelListing, Alert
from django.contrib.auth import get_user_model
from messaging.utils import send_notification_to_user
from messaging.models import Notification
from messaging.serializers import NotificationSerializer
from datetime import date

User = get_user_model()

@receiver(post_save, sender=TravelListing)
def notify_alerts_on_travel_listing(sender, instance, created, **kwargs):
    if not created:
        return

    print(f" {instance.id} - {instance.destination_country} - {instance.destination_region}")
    alerts = Alert.objects.filter(
        pickup_country=instance.pickup_country,
        pickup_region=instance.pickup_region,
        destination_country=instance.destination_country,
        destination_region=instance.destination_region,
        from_travel_date__lte=instance.travel_date,
        # notify_me=True,
        is_active=True
    )

    alerts = alerts.filter(
        to_travel_date__isnull=True
    ) | alerts.filter(
        to_travel_date__gte=instance.travel_date
    )
    for alert in alerts.distinct():
        user = alert.user
        notification = Notification.objects.create(
            user=user,
            travel_listing=instance,
            message=f"A new travel listing matches your alert: {instance}"
        )
        # Send notification via Django Channels
        serializer = NotificationSerializer(notification)
        send_notification_to_user(user.id, serializer.data) 