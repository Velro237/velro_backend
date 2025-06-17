from django.contrib import admin
from .models import TravelListing, PackageRequest, Alert, Country, Region, ListingImage

class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1

@admin.register(TravelListing)
class TravelListingAdmin(admin.ModelAdmin):
    list_display = ('user', 'pickup_country', 'pickup_region', 'destination_country', 
                   'destination_region', 'travel_date', 'mode_of_transport', 'status')
    list_filter = ('status', 'mode_of_transport', 'pickup_country', 'destination_country')
    search_fields = ('user__username', 'pickup_country__name', 'destination_country__name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ListingImageInline]
    date_hierarchy = 'travel_date'
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'status')
        }),
        ('Location Details', {
            'fields': ('pickup_country', 'pickup_region', 'destination_country', 'destination_region')
        }),
        ('Travel Details', {
            'fields': ('travel_date', 'travel_time', 'mode_of_transport', 'maximum_weight_in_kg', 'notes')
        }),
        ('Pricing', {
            'fields': ('price_per_kg', 'price_per_document', 'price_per_phone', 'price_per_tablet', 
                      'price_per_pc', 'price_per_file')
        }),
    )

@admin.register(PackageRequest)
class PackageRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'travel_listing', 'weight', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'package_description', 'travel_listing__title')
    date_hierarchy = 'created_at'
    inlines = [ListingImageInline]

@admin.register(ListingImage)
class ListingImageAdmin(admin.ModelAdmin):
    list_display = ('travel_listing', 'image', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('travel_listing__title',)

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_at', 'updated_at')
    search_fields = ('name', 'code')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'created_at', 'updated_at')
    list_filter = ('country',)
    search_fields = ('name', 'country__name')
    ordering = ('country', 'name')
    readonly_fields = ('created_at', 'updated_at')
