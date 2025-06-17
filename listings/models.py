from django.db import models
from django.utils.translation import gettext_lazy as _
from users.models import CustomUser
from django.conf import settings

class TravelListing(models.Model):
    STATUS_CHOICES = [
        ('drafted', 'Drafted'),
        ('published', 'Published'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    TRANSPORT_CHOICES = [
        ('plane', 'Plane'),
        ('bus', 'Bus'),
        ('train', 'Train'),
        ('ship', 'Ship'),
        ('car', 'Car'),
        ('motorcycle', 'Motorcycle'),
        ('bicycle', 'Bicycle'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pickup_country = models.ForeignKey('Country', on_delete=models.PROTECT, related_name='pickup_listings')
    pickup_region = models.ForeignKey('Region', on_delete=models.PROTECT, related_name='pickup_listings')
    destination_country = models.ForeignKey('Country', on_delete=models.PROTECT, related_name='destination_listings')
    destination_region = models.ForeignKey('Region', on_delete=models.PROTECT, related_name='destination_listings')
    travel_date = models.DateField()
    travel_time = models.TimeField()
    mode_of_transport = models.CharField(max_length=20, choices=TRANSPORT_CHOICES)
    maximum_weight_in_kg = models.DecimalField(max_digits=5, decimal_places=2)
    notes = models.TextField(blank=True)
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_document = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_phone = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_tablet = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_pc = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_file = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.pickup_country.name} to {self.destination_country.name} - {self.travel_date}"

class PackageRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]

    PACKAGE_TYPE_CHOICES = [
        ('DOCUMENT', 'Document'),                     # Papers, certificates, ID cards
        ('SMALL_PARCEL', 'Small Parcel'),             # Phones, books, accessories
        ('MEDIUM_PARCEL', 'Medium Parcel'),           # Clothing, shoes, electronics
        ('LARGE_PARCEL', 'Large Parcel'),             # Luggage-sized, boxed items
        ('FRAGILE_ITEM', 'Fragile Item'),             # Glass, electronics
        ('PERISHABLE_ITEM', 'Perishable Item'),       # Food, plants
        ('MEDICINE', 'Medicine/Pharmaceutical'),      # Needs traveler approval
        ('VALUABLE_ITEM', 'Valuable Item'),           # Laptops, jewelry
        ('OTHER', 'Other (Specify in description)'),  # For edge cases
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    travel_listing = models.ForeignKey(TravelListing, on_delete=models.CASCADE)
    package_description = models.TextField()
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    pickup_address = models.TextField()
    receiver_address = models.TextField()
    receiver_phone_number = models.CharField(max_length=20)
    package_type = models.CharField(max_length=20, choices=PACKAGE_TYPE_CHOICES)
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
    pickup_country = models.CharField(max_length=100)
    pickup_region = models.CharField(max_length=100)
    destination_country = models.CharField(max_length=100)
    destination_region = models.CharField(max_length=100)
    travel_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Alert: {self.pickup_country} to {self.destination_country} - {self.travel_date}"

    class Meta:
        ordering = ['-created_at']

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True)
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
