from django.db import models
from django.utils.translation import gettext_lazy as _
from users.models import CustomUser
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

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
    pickup_country = models.ForeignKey('Country', on_delete=models.PROTECT, related_name='pickup_listings')
    pickup_region = models.ForeignKey('Region', on_delete=models.PROTECT, related_name='pickup_listings')
    destination_country = models.ForeignKey('Country', on_delete=models.PROTECT, related_name='destination_listings')
    destination_region = models.ForeignKey('Region', on_delete=models.PROTECT, related_name='destination_listings')
    travel_date = models.DateField()
    travel_time = models.TimeField()
    mode_of_transport = models.ForeignKey(TransportType, on_delete=models.PROTECT)
    maximum_weight_in_kg = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.TextField(blank=True)
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_document = models.DecimalField(max_digits=10, decimal_places=2)
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
        return f"{self.pickup_country.name} to {self.destination_country.name} - {self.travel_date}"

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
    pickup_country = models.ForeignKey('Country', on_delete=models.CASCADE, related_name='pickup_alerts')
    pickup_region = models.ForeignKey('Region', on_delete=models.CASCADE, related_name='pickup_alerts')
    destination_country = models.ForeignKey('Country', on_delete=models.CASCADE, related_name='destination_alerts')
    destination_region = models.ForeignKey('Region', on_delete=models.CASCADE, related_name='destination_alerts')
    from_travel_date = models.DateField()
    to_travel_date = models.DateField(null=True, blank=True)
    notify_for_any_pickup_city = models.BooleanField(default=False)
    notify_for_any_destination_city = models.BooleanField(default=False)
    notify_me = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Alert: {self.pickup_country} to {self.destination_country} - {self.from_travel_date} to {self.to_travel_date}"

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
