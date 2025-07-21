from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q, Avg, Sum, F, DateField, DateTimeField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from users.models import CustomUser
from listings.models import TravelListing, PackageRequest
from reporting.models import EventLog
from datetime import datetime, timedelta
from config.views import StandardResponseViewSet

class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser

class AdminMetricsViewSet(StandardResponseViewSet):
    permission_classes = [IsSuperUser]

    @action(detail=False, methods=['get'])
    def total_users(self, request):
        """
        Returns the total number of users in the system.
        """
        return self._standardize_response(Response({'total_users': CustomUser.objects.count()}))

    @action(detail=False, methods=['get'])
    def new_users(self, request):
        """
        Returns the number of new users per day, week, month, and year.
        """
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        year_ago = today - timedelta(days=365)
        data = {
            'per_day': CustomUser.objects.filter(date_joined__date=today).count(),
            'per_week': CustomUser.objects.filter(date_joined__date__gte=week_ago).count(),
            'per_month': CustomUser.objects.filter(date_joined__date__gte=month_ago).count(),
            'per_year': CustomUser.objects.filter(date_joined__date__gte=year_ago).count(),
        }
        return self._standardize_response(Response(data))

    @action(detail=False, methods=['get'])
    def verified_travelers(self, request):
        """
        Returns the number of users with completed identity verification.
        """
        return self._standardize_response(Response({'verified_travelers': CustomUser.objects.filter(is_identity_verified='completed').count()}))

    @action(detail=False, methods=['get'])
    def total_trips(self, request):
        """
        Returns the total number of trips (TravelListing).
        """
        return self._standardize_response(Response({'total_trips': TravelListing.objects.count()}))

    @action(detail=False, methods=['get'])
    def trips_per_day(self, request):
        """
        Returns the number of trips created per day.
        """
        data = TravelListing.objects.annotate(day=TruncDay('created_at')).values('day').annotate(count=Count('id')).order_by('day')
        return self._standardize_response(Response({'trips_per_day': list(data)}))

    @action(detail=False, methods=['get'])
    def trips_per_week(self, request):
        """
        Returns the number of trips created per week.
        """
        data = TravelListing.objects.annotate(week=TruncWeek('created_at')).values('week').annotate(count=Count('id')).order_by('week')
        return self._standardize_response(Response({'trips_per_week': list(data)}))

    @action(detail=False, methods=['get'])
    def trips_per_month(self, request):
        """
        Returns the number of trips created per month.
        """
        data = TravelListing.objects.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
        return self._standardize_response(Response({'trips_per_month': list(data)}))

    @action(detail=False, methods=['get'])
    def trips_per_year(self, request):
        """
        Returns the number of trips created per year.
        """
        data = TravelListing.objects.annotate(year=TruncYear('created_at')).values('year').annotate(count=Count('id')).order_by('year')
        return self._standardize_response(Response({'trips_per_year': list(data)}))

    @action(detail=False, methods=['get'])
    def avg_price_per_kg(self, request):
        """
        Returns the average price per kg for all trips.
        """
        avg_price = TravelListing.objects.aggregate(avg=Avg('price_per_kg'))['avg']
        return self._standardize_response(Response({'avg_price_per_kg': avg_price}))

    @action(detail=False, methods=['get'])
    def total_kg_offered(self, request):
        """
        Returns the total kg offered across all trips.
        """
        total_kg = TravelListing.objects.aggregate(total=Sum('maximum_weight_in_kg'))['total']
        return self._standardize_response(Response({'total_kg_offered': total_kg}))

    @action(detail=False, methods=['get'])
    def routes(self, request):
        """
        Returns the most popular routes (pickup/destination region pairs).
        """
        data = TravelListing.objects.values('pickup_region__name', 'destination_region__name').annotate(count=Count('id')).order_by('-count')
        return self._standardize_response(Response({'routes': list(data)}))

    @action(detail=False, methods=['get'])
    def total_package_requests(self, request):
        """
        Returns the total number of package requests.
        """
        return self._standardize_response(Response({'total_package_requests': PackageRequest.objects.count()}))

    @action(detail=False, methods=['get'])
    def package_status_distribution(self, request):
        """
        Returns the distribution of package request statuses.
        """
        data = PackageRequest.objects.values('status').annotate(count=Count('id'))
        return self._standardize_response(Response({'status_distribution': list(data)}))

    @action(detail=False, methods=['get'])
    def offers_per_trip(self, request):
        """
        Returns the number of offers per trip.
        """
        data = PackageRequest.objects.values('travel_listing').annotate(offers=Count('id')).order_by('-offers')
        return self._standardize_response(Response({'offers_per_trip': list(data)}))

    @action(detail=False, methods=['get'])
    def total_kg_sold(self, request):
        """
        Returns the total kg sold (accepted or completed package requests).
        """
        total_kg = PackageRequest.objects.filter(status__in=['accepted', 'completed']).aggregate(total=Sum('weight'))['total']
        return self._standardize_response(Response({'total_kg_sold': total_kg}))

    @action(detail=False, methods=['get'])
    def kg_sold_vs_available(self, request):
        """
        Returns the kg sold vs available (offered) in the system.
        """
        kg_sold = PackageRequest.objects.filter(status__in=['accepted', 'completed']).aggregate(total=Sum('weight'))['total'] or 0
        kg_available = TravelListing.objects.aggregate(total=Sum('maximum_weight_in_kg'))['total'] or 0
        return self._standardize_response(Response({'kg_sold': kg_sold, 'kg_available': kg_available}))

    @action(detail=False, methods=['get'])
    def offer_to_message_ratio(self, request):
        """
        Returns the ratio of users who clicked order vs message.
        """
        order_users = EventLog.objects.filter(event_type='order_click').values('user').distinct().count()
        message_users = EventLog.objects.filter(event_type='message_click').values('user').distinct().count()
        ratio = order_users / message_users if message_users else None
        return self._standardize_response(Response({'offer_to_message_ratio': ratio, 'order_users': order_users, 'message_users': message_users}))

    @action(detail=False, methods=['get'])
    def dau_wau_mau(self, request):
        """
        Returns daily, weekly, and monthly active users (DAU, WAU, MAU).
        """
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        dau = EventLog.objects.filter(timestamp__date=today).values('user').distinct().count()
        wau = EventLog.objects.filter(timestamp__date__gte=week_ago).values('user').distinct().count()
        mau = EventLog.objects.filter(timestamp__date__gte=month_ago).values('user').distinct().count()
        return self._standardize_response(Response({'DAU': dau, 'WAU': wau, 'MAU': mau}))

    @action(detail=False, methods=['get'])
    def trip_creators_vs_senders(self, request):
        """
        Returns the ratio of trip creators to senders.
        """
        trip_creators = CustomUser.objects.filter(travellisting__isnull=False).distinct().count()
        senders = CustomUser.objects.filter(packagerequest__isnull=False).distinct().count()
        ratio = trip_creators / senders if senders else None
        return self._standardize_response(Response({'trip_creators': trip_creators, 'senders': senders, 'ratio': ratio}))

    @action(detail=False, methods=['get'])
    def avg_time_to_first_package_request(self, request):
        """
        Returns the average time (in hours) from trip creation to first package request.
        """
        from django.db.models import Min, F, ExpressionWrapper, DurationField
        trips = TravelListing.objects.annotate(
            first_request_time=Min('package_requests__created_at')
        ).exclude(first_request_time=None).annotate(
            time_to_first_request=ExpressionWrapper(
                F('first_request_time') - F('created_at'), output_field=DurationField()
            )
        )
        avg_seconds = trips.aggregate(avg=Avg('time_to_first_request'))['avg']
        avg_hours = avg_seconds.total_seconds() / 3600 if avg_seconds else None
        return self._standardize_response(Response({'avg_time_to_first_package_request_hours': avg_hours}))

    @action(detail=False, methods=['get'])
    def package_request_response_time_buckets(self, request):
        """
        Returns the distribution of package request response times in buckets.
        """
        from django.db.models import F, ExpressionWrapper, DurationField
        buckets = {'<24h': 0, '24-48h': 0, '48-72h': 0, '>72h': 0}
        requests = PackageRequest.objects.exclude(status='pending').annotate(
            response_time=ExpressionWrapper(F('updated_at') - F('created_at'), output_field=DurationField())
        )
        for req in requests:
            hours = req.response_time.total_seconds() / 3600 if req.response_time else None
            if hours is not None:
                if hours < 24:
                    buckets['<24h'] += 1
                elif hours < 48:
                    buckets['24-48h'] += 1
                elif hours < 72:
                    buckets['48-72h'] += 1
                else:
                    buckets['>72h'] += 1
        return self._standardize_response(Response({'response_time_buckets': buckets}))

    @action(detail=False, methods=['get'])
    def route_saturation(self, request):
        """
        Returns the unfilled kg for each route (pickup/destination pair).
        """
        from django.db.models import Sum
        data = []
        routes = TravelListing.objects.values('pickup_region__name', 'destination_region__name', 'id', 'maximum_weight_in_kg')
        for route in routes:
            accepted_kg = PackageRequest.objects.filter(
                travel_listing_id=route['id'], status='accepted'
            ).aggregate(total=Sum('weight'))['total'] or 0
            unfilled_kg = float(route['maximum_weight_in_kg']) - float(accepted_kg)
            data.append({
                'pickup': route['pickup_region__name'],
                'destination': route['destination_region__name'],
                'unfilled_kg': unfilled_kg
            })
        return self._standardize_response(Response({'route_saturation': data}))

    @action(detail=False, methods=['get'])
    def cancellation_dispute_rates(self, request):
        """
        Returns the cancellation rates for trips and package requests.
        """
        total_trips = TravelListing.objects.count()
        canceled_trips = TravelListing.objects.filter(status='canceled').count()
        trip_cancel_rate = canceled_trips / total_trips if total_trips else 0
        total_requests = PackageRequest.objects.count()
        canceled_requests = PackageRequest.objects.filter(status='rejected').count()
        request_cancel_rate = canceled_requests / total_requests if total_requests else 0
        return self._standardize_response(Response({
            'trip_cancel_rate': trip_cancel_rate,
            'request_cancel_rate': request_cancel_rate
        }))

    @action(detail=False, methods=['get'])
    def funnel_conversion(self, request):
        """
        Returns funnel conversion metrics: travel created, request sent, request accepted, delivery confirmed.
        """
        travel_created = TravelListing.objects.count()
        request_sent = PackageRequest.objects.count()
        request_accepted = PackageRequest.objects.filter(status='accepted').count()
        delivery_confirmed = PackageRequest.objects.filter(status='completed').count()
        return self._standardize_response(Response({
            'travel_created': travel_created,
            'request_sent': request_sent,
            'request_accepted': request_accepted,
            'delivery_confirmed': delivery_confirmed
        }))

    @action(detail=False, methods=['get'])
    def dashboard_data(self, request):
        """
        Aggregates key metrics for graphical dashboard display.
        Returns data for users, trips, package requests, and activity over time.
        """
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        year_ago = today - timedelta(days=365)

        # Users over time
        users_per_day = list(CustomUser.objects.annotate(day=TruncDay('date_joined')).values('day').annotate(count=Count('id')).order_by('day'))
        users_per_month = list(CustomUser.objects.annotate(month=TruncMonth('date_joined')).values('month').annotate(count=Count('id')).order_by('month'))

        # Trips over time
        trips_per_day = list(TravelListing.objects.annotate(day=TruncDay('created_at')).values('day').annotate(count=Count('id')).order_by('day'))
        trips_per_month = list(TravelListing.objects.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month'))

        # Package requests over time
        requests_per_day = list(PackageRequest.objects.annotate(day=TruncDay('created_at')).values('day').annotate(count=Count('id')).order_by('day'))
        requests_per_month = list(PackageRequest.objects.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month'))

        # Popular routes
        popular_routes = list(TravelListing.objects.values('pickup_region__name', 'destination_region__name').annotate(count=Count('id')).order_by('-count')[:10])

        # Package status distribution
        package_status_dist = list(PackageRequest.objects.values('status').annotate(count=Count('id')))

        # DAU, WAU, MAU
        dau = EventLog.objects.filter(timestamp__date=today).values('user').distinct().count()
        wau = EventLog.objects.filter(timestamp__date__gte=week_ago).values('user').distinct().count()
        mau = EventLog.objects.filter(timestamp__date__gte=month_ago).values('user').distinct().count()

        data = {
            'users_per_day': users_per_day,
            'users_per_month': users_per_month,
            'trips_per_day': trips_per_day,
            'trips_per_month': trips_per_month,
            'requests_per_day': requests_per_day,
            'requests_per_month': requests_per_month,
            'popular_routes': popular_routes,
            'package_status_distribution': package_status_dist,
            'DAU': dau,
            'WAU': wau,
            'MAU': mau,
        }
        return self._standardize_response(Response(data))
