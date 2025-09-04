from rest_framework import serializers
from .models import TravelListing, PackageRequest, Alert, Country, Region, TransportType, PackageType, Review, LocationData
from decimal import Decimal
from django.db import models

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'is_popular', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class RegionSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)

    class Meta:
        model = Region
        fields = ['id', 'name', 'country', 'country_name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class RegionWithCountrySerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Region
        fields = ['id', 'name', 'country', 'display_name']

    def get_display_name(self, obj):
        return f"{obj.name}, {obj.country.name}"

class TransportTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportType
        fields = ['id', 'name', 'description']

class PackageTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageType
        fields = ['id', 'name', 'description']

class LocationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationData
        fields = ['id', 'name', 'country', 'country_code', 'created_at']
        read_only_fields = ['id', 'created_at']


class TravelListingSerializer(serializers.ModelSerializer):
    # Legacy fields for backward compatibility
    pickup = RegionWithCountrySerializer(source='pickup_region', read_only=True)
    destination = RegionWithCountrySerializer(source='destination_region', read_only=True)
    pickup_region_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='pickup_region', write_only=True, required=False)
    destination_region_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='destination_region', write_only=True, required=False)
    
    # New location fields
    pickup_location_data = LocationDataSerializer(source='pickup_location', read_only=True)
    destination_location_data = LocationDataSerializer(source='destination_location', read_only=True)
    pickup_region = serializers.DictField(write_only=True, required=False)
    destination_region = serializers.DictField(write_only=True, required=False)
    
    mode_of_transport = TransportTypeSerializer(read_only=True)
    mode_of_transport_id = serializers.PrimaryKeyRelatedField(queryset=TransportType.objects.all(), source='mode_of_transport', write_only=True)
    
    def validate(self, data):
        """
        Validate the data for travel listing creation/update based on fullSuitcaseOnly flag
        """
        fullSuitcaseOnly = data.get('fullSuitcaseOnly', False)
        
        # If fullSuitcaseOnly is enabled
        if fullSuitcaseOnly:
            # Price per suitcase must be provided
            if 'price_full_suitcase' not in data or data.get('price_full_suitcase') is None:
                raise serializers.ValidationError({
                    "price_full_suitcase": "Price per suitcase is required when fullSuitcaseOnly is enabled."
                })
            
            # Set standard values for fullSuitcaseOnly mode
            data['maximum_weight_in_kg'] = 23.00
            
            # Zero out other pricing fields if they're in the data
            for field in ['price_per_kg', 'price_per_document', 'price_per_phone', 
                         'price_per_tablet', 'price_per_pc', 'price_per_file']:
                if field in data:
                    data[field] = 0.00
        else:
            # In normal mode, price_per_kg is required
            if 'price_per_kg' not in data or data.get('price_per_kg') is None:
                raise serializers.ValidationError({
                    "price_per_kg": "Price per kg is required when not in fullSuitcaseOnly mode."
                })
            
        return data

    class Meta:
        model = TravelListing
        fields = [
            'id', 'user', 
            # Legacy location fields
            'pickup', 'pickup_region_id', 'destination', 'destination_region_id',
            # New location fields
            'pickup_location_data', 'destination_location_data', 'pickup_region', 'destination_region',
            'travel_date', 'travel_time', 'mode_of_transport', 'mode_of_transport_id', 'maximum_weight_in_kg',
            'notes', 'fullSuitcaseOnly', 'price_per_kg', 'price_per_document', 'price_per_phone',
            'price_per_tablet', 'price_per_pc', 'price_per_file', 'price_full_suitcase', 'currency', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at', 'pickup', 'destination', 'mode_of_transport', 'pickup_location_data', 'destination_location_data']

    def create(self, validated_data):
        # Handle location data in different formats
        if 'pickup_region' in validated_data and isinstance(validated_data['pickup_region'], dict):
            pickup_data = validated_data.pop('pickup_region')
            # Create LocationData object
            pickup_location = LocationData.objects.create(
                name=pickup_data.get('name'),
                country=pickup_data.get('country'),
                country_code=pickup_data.get('countryCode')
            )
            validated_data['pickup_location'] = pickup_location
        elif 'pickup_region' in validated_data and not isinstance(validated_data['pickup_region'], dict):
            # Legacy format using ID
            pickup_region = validated_data.pop('pickup_region')
            validated_data['pickup_region'] = pickup_region
            validated_data['pickup_country'] = pickup_region.country
        
        if 'destination_region' in validated_data and isinstance(validated_data['destination_region'], dict):
            dest_data = validated_data.pop('destination_region')
            # Create LocationData object
            dest_location = LocationData.objects.create(
                name=dest_data.get('name'),
                country=dest_data.get('country'),
                country_code=dest_data.get('countryCode')
            )
            validated_data['destination_location'] = dest_location
        elif 'destination_region' in validated_data and not isinstance(validated_data['destination_region'], dict):
            # Legacy format using ID
            destination_region = validated_data.pop('destination_region')
            validated_data['destination_region'] = destination_region
            validated_data['destination_country'] = destination_region.country
        
        # Note: Validation logic is now handled in the validate method
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Handle location data in different formats
        if 'pickup_region' in validated_data:
            if isinstance(validated_data['pickup_region'], dict):
                pickup_data = validated_data.pop('pickup_region')
                # Update or create LocationData object
                if instance.pickup_location:
                    pickup_location = instance.pickup_location
                    pickup_location.name = pickup_data.get('name')
                    pickup_location.country = pickup_data.get('country')
                    pickup_location.country_code = pickup_data.get('countryCode')
                    pickup_location.save()
                else:
                    pickup_location = LocationData.objects.create(
                        name=pickup_data.get('name'),
                        country=pickup_data.get('country'),
                        country_code=pickup_data.get('countryCode')
                    )
                instance.pickup_location = pickup_location
            else:
                # Legacy format using ID
                pickup_region = validated_data.pop('pickup_region')
                instance.pickup_region = pickup_region
                instance.pickup_country = pickup_region.country
        
        if 'destination_region' in validated_data:
            if isinstance(validated_data['destination_region'], dict):
                dest_data = validated_data.pop('destination_region')
                # Update or create LocationData object
                if instance.destination_location:
                    dest_location = instance.destination_location
                    dest_location.name = dest_data.get('name')
                    dest_location.country = dest_data.get('country')
                    dest_location.country_code = dest_data.get('countryCode')
                    dest_location.save()
                else:
                    dest_location = LocationData.objects.create(
                        name=dest_data.get('name'),
                        country=dest_data.get('country'),
                        country_code=dest_data.get('countryCode')
                    )
                instance.destination_location = dest_location
            else:
                # Legacy format using ID
                destination_region = validated_data.pop('destination_region')
                instance.destination_region = destination_region
                instance.destination_country = destination_region.country
            
        # Note: Validation logic is now handled in the validate method
        # Any update that changes fullSuitcaseOnly will trigger the validate method
        
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from users.serializers import UserProfileSerializer  # Lazy import to avoid circular import
        representation['user'] = UserProfileSerializer(instance.user).data
        return representation

class PackageRequestSerializer(serializers.ModelSerializer):
    travel_listing = serializers.PrimaryKeyRelatedField(queryset=TravelListing.objects.all())
    package_types = serializers.PrimaryKeyRelatedField(queryset=PackageType.objects.all(), many=True, required=False)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = PackageRequest
        fields = [
            'id', 'user', 'travel_listing', 'package_description', 'weight',
            'number_of_document', 'number_of_phone', 'number_of_tablet',
            'number_of_pc', 'number_of_full_suitcase', 
            'package_types', 'total_price', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'status', 'created_at', 'updated_at', 'total_price']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from users.serializers import UserProfileSerializer  # Lazy import to avoid circular import
        representation['user'] = UserProfileSerializer(instance.user).data
        representation['package_types'] = PackageTypeSerializer(instance.package_types.all(), many=True).data
        return representation

    def validate(self, data):
        """
        Ensure the travel listing is published and the user is not the owner.
        Also check that package_description is provided if weight is greater than 0.
        Also check that requested weight does not exceed available weight and travel has not started.
        """
        weight = data.get('weight', getattr(self.instance, 'weight', Decimal('0.0')))
        description = data.get('package_description', getattr(self.instance, 'package_description', ''))

        if Decimal(weight) > 0 and not description.strip():
            raise serializers.ValidationError({
                "package_description": "A description is required when specifying a weight."
            })
        # Ensure travel listing is published and user is not the owner
        request = self.context.get('request')
        travel_listing = data.get('travel_listing')
        if travel_listing:
            if travel_listing.status != 'published':
                raise serializers.ValidationError({
                    "travel_listing": "You can only create a package request for a published travel listing."
                })
            if request and travel_listing.user == request.user:
                raise serializers.ValidationError({
                    "travel_listing": "You cannot create a package request for your own travel listing."
                })
            # Check travel has not started
            from datetime import datetime, time
            now = datetime.now()
            travel_datetime = datetime.combine(travel_listing.travel_date, travel_listing.travel_time)
            if travel_datetime <= now:
                raise serializers.ValidationError({
                    "travel_listing": "You cannot create a package request for a travel that has already started."
                })
            # Check available weight
            # Sum accepted package weights for this travel listing
            from listings.models import PackageRequest
            accepted_weight = PackageRequest.objects.filter(
                travel_listing=travel_listing, status='accepted'
            ).aggregate(models.Sum('weight'))['weight__sum'] or Decimal('0.0')
            available_weight = travel_listing.maximum_weight_in_kg - accepted_weight
            if Decimal(weight) > available_weight:
                raise serializers.ValidationError({
                    "weight": f"Requested weight ({weight}kg) exceeds available capacity ({available_weight}kg)."
                })
        return data

    def _calculate_price(self, validated_data, travel_listing):
        price = Decimal('0.0')
        
        # Handle case where fields might not be in validated_data (on update)
        instance = getattr(self, 'instance', None)

        def get_value(field_name):
            return validated_data.get(field_name, getattr(instance, field_name, 0))
            
        if travel_listing.fullSuitcaseOnly:
            # In fullSuitcaseOnly mode, only count full suitcases
            num_suitcases = get_value('number_of_full_suitcase')
            if num_suitcases and travel_listing.price_full_suitcase:
                price += Decimal(num_suitcases) * Decimal(travel_listing.price_full_suitcase)
        else:
            # Normal mode - calculate based on weight and individual items
            
            # Price per kg
            weight = get_value('weight')
            if weight and travel_listing.price_per_kg:
                price += Decimal(weight) * Decimal(travel_listing.price_per_kg)
    
            # Price per item
            item_prices = {
                'number_of_document': travel_listing.price_per_document,
                'number_of_phone': travel_listing.price_per_phone,
                'number_of_tablet': travel_listing.price_per_tablet,
                'number_of_pc': travel_listing.price_per_pc,
                'number_of_full_suitcase': travel_listing.price_full_suitcase,
            }
    
            for field, item_price in item_prices.items():
                count = get_value(field)
                if count and item_price:
                    price += Decimal(count) * Decimal(item_price)
                    
        return price

    def create(self, validated_data):
        travel_listing = validated_data['travel_listing']
        total_price = self._calculate_price(validated_data, travel_listing)
        validated_data['total_price'] = total_price
        return super().create(validated_data)

    def update(self, instance, validated_data):
        travel_listing = validated_data.get('travel_listing', instance.travel_listing)
        total_price = self._calculate_price(validated_data, travel_listing)
        validated_data['total_price'] = total_price
        return super().update(instance, validated_data)

class AlertSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    pickup_country = CountrySerializer(read_only=True)
    pickup_country_id = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), source='pickup_country', write_only=True)
    pickup_region = RegionSerializer(read_only=True)
    pickup_region_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='pickup_region', write_only=True)
    destination_country = CountrySerializer(read_only=True)
    destination_country_id = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), source='destination_country', write_only=True)
    destination_region = RegionSerializer(read_only=True)
    destination_region_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='destination_region', write_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'user',
            'pickup_country', 'pickup_country_id',
            'pickup_region', 'pickup_region_id',
            'destination_country', 'destination_country_id',
            'destination_region', 'destination_region_id',
            'from_travel_date', 'to_travel_date',
            'notify_for_any_pickup_city', 'notify_for_any_destination_city',
            'notify_me',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user', 'created_at', 'updated_at',
            'pickup_country', 'pickup_region', 'destination_country', 'destination_region'
        ]

class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.ReadOnlyField(source='reviewer.username')
    travel_listing = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Review
        fields = ['id', 'travel_listing', 'package_request', 'reviewer', 'rate', 'description', 'created_at']
        read_only_fields = ['id', 'reviewer', 'created_at', 'travel_listing']

    def validate(self, data):
        request = self.context['request']
        user = request.user
        package_request = data.get('package_request')
        # Only package request owner can review
        if package_request.user != user:
            raise serializers.ValidationError('You can only review as the package request owner.')
        # Only if package request is completed
        if package_request.status != 'completed':
            raise serializers.ValidationError('You can only review after the package request is completed.')
        travel_listing = package_request.travel_listing
        # Only one review per travel listing per user
        if Review.objects.filter(travel_listing=travel_listing, reviewer=user).exists():
            raise serializers.ValidationError('You have already reviewed this travel listing.')
        data['travel_listing'] = travel_listing
        return data

    def create(self, validated_data):
        # travel_listing is set in validate
        return super().create(validated_data) 