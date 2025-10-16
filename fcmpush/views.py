from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from .models import Device
from .serializers import DeviceSerializer
from .fcm import send_to_token, send_to_tokens
from config.views import StandardResponseViewSet

class DeviceViewSet(StandardResponseViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        token = request.data.get("registration_token")
        platform = request.data.get("platform", "web")

        if not token:
            return self._standardize_response(Response({"detail": "registration_token is required"}, status=status.HTTP_400_BAD_REQUEST))

        device, created = Device.objects.update_or_create(
            registration_token=token,
            defaults={"user": request.user, "platform": platform},
        )
        serializer = self.get_serializer(device)
        return self._standardize_response(Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK))
    



@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def notify_user(request):
    title = request.data.get("title", "Hello")
    body = request.data.get("body", "This is a test notification")
    data = request.data.get("data", {})

    print("the title is: ", title)
    print("the body is: ", body)
    print("the data is: ", data)
    tokens = list(request.user.devices.values_list("registration_token", flat=True))
    if not tokens:
        return Response({"detail": "No registered devices found."}, status=404)

    response = send_to_tokens(tokens, title, body, data)
    return Response({
        "success": response.success_count,
        "failure": response.failure_count,
    })
