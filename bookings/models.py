from django.db import models
from django.utils.translation import gettext_lazy as _
from users.models import CustomUser
from listings.models import TravelListing, PackageRequest

class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]

    travel_listing = models.ForeignKey(TravelListing, on_delete=models.CASCADE, related_name='bookings')
    package_request = models.ForeignKey(PackageRequest, on_delete=models.CASCADE, related_name='bookings')
    traveler = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='travel_bookings')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='send_bookings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    package_weight = models.DecimalField(max_digits=5, decimal_places=2)  # in kg
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking {self.id} - {self.traveler.username} to {self.sender.username}"

    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.package_weight * self.price_per_kg
        super().save(*args, **kwargs)

class BookingMessage(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='booking_messages')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.username} for booking {self.booking.id}"

class BookingStatusUpdate(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='status_updates')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='booking_status_updates')
    old_status = models.CharField(max_length=20, choices=Booking.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=Booking.STATUS_CHOICES)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Status update for booking {self.booking.id}: {self.old_status} -> {self.new_status}"
