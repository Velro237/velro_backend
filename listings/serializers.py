from rest_framework import serializers
from .models import TravelListing, PackageRequest, Alert, Country, Region

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class RegionSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)

    class Meta:
        model = Region
        fields = ['id', 'name', 'country', 'country_name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class TravelListingSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    pickup_country_name = serializers.CharField(source='pickup_country.name', read_only=True)
    pickup_region_name = serializers.CharField(source='pickup_region.name', read_only=True)
    destination_country_name = serializers.CharField(source='destination_country.name', read_only=True)
    destination_region_name = serializers.CharField(source='destination_region.name', read_only=True)

    class Meta:
        model = TravelListing
        fields = [
            'id', 'user', 'pickup_country', 'pickup_country_name',
            'pickup_region', 'pickup_region_name', 'destination_country',
            'destination_country_name', 'destination_region', 'destination_region_name',
            'travel_date', 'travel_time', 'mode_of_transport', 'maximum_weight_in_kg',
            'notes', 'price_per_kg', 'price_per_document', 'price_per_phone',
            'price_per_tablet', 'price_per_pc', 'price_per_file', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

class PackageRequestSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    travel_listing = serializers.PrimaryKeyRelatedField(queryset=TravelListing.objects.filter(status='published'))
    package_type_display = serializers.CharField(source='get_package_type_display', read_only=True)

    class Meta:
        model = PackageRequest
        fields = [
            'id', 'user', 'travel_listing', 'package_description', 'weight',
            'pickup_address', 'receiver_address', 'receiver_phone_number',
            'package_type', 'package_type_display', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'status', 'created_at', 'updated_at']

class AlertSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Alert
        fields = [
            'id', 'user', 'pickup_country', 'pickup_region',
            'destination_country', 'destination_region', 'travel_date',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at'] 