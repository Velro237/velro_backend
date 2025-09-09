from django.db import models
from django.utils.translation import gettext_lazy as _
from users.models import CustomUser
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from config.utils import upload_image, delete_image, optimized_image_url, auto_crop_url
from django.contrib.postgres.fields import JSONField
class TransportType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class TravelListing(models.Model):
    STATUS_CHOICES = [
        ('drafted', 'Drafted'),
        ('published', 'Published'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
        ('fully-booked', 'Fully Booked'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Legacy fields - kept for backwards compatibility
    pickup_country = models.ForeignKey('Country', on_delete=models.PROTECT, related_name='pickup_listings', null=True, blank=True)
    pickup_region = models.ForeignKey('Region', on_delete=models.PROTECT, related_name='pickup_listings', null=True, blank=True)
    destination_country = models.ForeignKey('Country', on_delete=models.PROTECT, related_name='destination_listings', null=True, blank=True)
    destination_region = models.ForeignKey('Region', on_delete=models.PROTECT, related_name='destination_listings', null=True, blank=True)
    
    # New fields for direct location data
    pickup_location = models.ForeignKey('LocationData', on_delete=models.PROTECT, related_name='pickup_listings', null=True, blank=True)
    destination_location = models.ForeignKey('LocationData', on_delete=models.PROTECT, related_name='destination_listings', null=True, blank=True)
    travel_date = models.DateField()
    travel_time = models.TimeField()
    mode_of_transport = models.ForeignKey(TransportType, on_delete=models.PROTECT)
    maximum_weight_in_kg = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.TextField(blank=True)
    fullSuitcaseOnly = models.BooleanField(default=False)
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_document = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_phone = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_tablet = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_pc = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_file = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_full_suitcase = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.pickup_location and self.destination_location:
            pickup_name = f"{self.pickup_location.name}, {self.pickup_location.country}"
            destination_name = f"{self.destination_location.name}, {self.destination_location.country}"
        else:
            pickup_name = f"{self.pickup_region.name}, {self.pickup_country.name}" if self.pickup_region else "Unknown"
            destination_name = f"{self.destination_region.name}, {self.destination_country.name}" if self.destination_region else "Unknown"
            
        return f"{pickup_name} to {destination_name} - {self.travel_date}"

class PackageType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class PackageRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    travel_listing = models.ForeignKey(TravelListing, on_delete=models.CASCADE, related_name='package_requests')
    package_description = models.TextField(blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Weight in KG for items not counted by unit.")
    
    number_of_document = models.PositiveIntegerField(default=0)
    number_of_phone = models.PositiveIntegerField(default=0)
    number_of_tablet = models.PositiveIntegerField(default=0)
    number_of_pc = models.PositiveIntegerField(default=0)
    number_of_full_suitcase = models.PositiveIntegerField(default=0)

    package_types = models.ManyToManyField(PackageType, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, editable=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Package request from {self.user.username} for {self.travel_listing}"

class ListingImage(models.Model):
    travel_listing = models.ForeignKey(TravelListing, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    package_request = models.ForeignKey(PackageRequest, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    image = models.ImageField(upload_to='listings/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.travel_listing:
            return f"Image for travel listing {self.travel_listing.id}"
        return f"Image for package request {self.package_request.id}"
    class Meta:
        ordering = ['-is_primary', '-created_at']

class Alert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Use LocationData for storing location information - keep nullable for now
    pickup_location = models.ForeignKey('LocationData', on_delete=models.CASCADE, related_name='pickup_alerts', null=True, blank=True)
    destination_location = models.ForeignKey('LocationData', on_delete=models.CASCADE, related_name='destination_alerts', null=True, blank=True)
    
    from_travel_date = models.DateField()
    to_travel_date = models.DateField(null=True, blank=True)
    notify_for_any_pickup_city = models.BooleanField(default=False)
    notify_for_any_destination_city = models.BooleanField(default=False)
    notify_me = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        pickup = f"{self.pickup_location.name}, {self.pickup_location.country}"
        destination = f"{self.destination_location.name}, {self.destination_location.country}"
        to_date = f" to {self.to_travel_date}" if self.to_travel_date else ""
        return f"Alert: {pickup} to {destination} - {self.from_travel_date}{to_date}"

    class Meta:
        ordering = ['-created_at']

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True)
    is_popular = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Countries"
        ordering = ['name']

class Region(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='regions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}, {self.country.name}"

    class Meta:
        unique_together = ['name', 'country']
        ordering = ['country', 'name']

class LocationData(models.Model):
    """Model for storing flexible location data without requiring database entries"""
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    country_code = models.CharField(max_length=2)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name}, {self.country} ({self.country_code})"
    
    class Meta:
        verbose_name_plural = "Location Data"
        unique_together = ['name', 'country', 'country_code']


class Review(models.Model):
    travel_listing = models.ForeignKey('TravelListing', on_delete=models.CASCADE, related_name='reviews')
    package_request = models.ForeignKey('PackageRequest', on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rate = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('travel_listing', 'reviewer')
        ordering = ['-created_at']

    def __str__(self):
        return f"Review by {self.reviewer} for {self.travel_listing} ({self.rate})"
