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

    try:
        print(f"Travel listing created: {instance.id}")
        
        # Handle alerts that match location data for listings created with new format
        if instance.pickup_location and instance.destination_location:
            alerts = Alert.objects.filter(
                pickup_location__name__icontains=instance.pickup_location.name,
                pickup_location__country__icontains=instance.pickup_location.country,
                destination_location__name__icontains=instance.destination_location.name,
                destination_location__country__icontains=instance.destination_location.country,
                from_travel_date__lte=instance.travel_date,
                is_active=True
            )
        # Handle alerts for listings created with legacy format
        elif instance.pickup_country and instance.destination_country:
            alerts = Alert.objects.filter(
                pickup_country=instance.pickup_country,
                pickup_region=instance.pickup_region,
                destination_country=instance.destination_country,
                destination_region=instance.destination_region,
                from_travel_date__lte=instance.travel_date,
                is_active=True
            )
        else:
            # Skip notification if no location data is available
            return

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
    except Exception as e:
        # Log the error but don't prevent the travel listing from being created
        print(f"Error in travel listing signal: {str(e)}")
        import traceback
        traceback.print_exc() 