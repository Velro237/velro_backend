from django.urls import path, include
from rest_framework.routers import DefaultRouter
# from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserViewSet, ProfileViewSet, UserLoginView,
    GoogleSignInView, AppleSignInView, IdTypeViewSet,TokenRefreshView, UserLogoutView
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'profile', ProfileViewSet)
router.register(r'id-types', IdTypeViewSet, basename='id-type')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', UserLoginView.as_view(), name='user_login'),
    path('logout/', UserLogoutView.as_view(), name='user_logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('google/signin/', GoogleSignInView.as_view(), name='google_signin'),
    path('apple/signin/', AppleSignInView.as_view(), name='apple_signin'),
    # ID verification is handled by the UserViewSet's verify_id_document action at /users/verify_id_document/
]