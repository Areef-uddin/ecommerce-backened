from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    register_view,
    login_view,
    admin_login_view,
    admin_customers_view,
    send_otp_view,
    verify_otp_view,
    profile_view,
    AddressViewSet
)

router = DefaultRouter()
router.register('addresses', AddressViewSet, basename='address')

urlpatterns = [
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    path('admin-login/', admin_login_view, name='admin_login'),
    path('admin/customers/', admin_customers_view, name='admin_customers'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('otp/send/', send_otp_view, name='send_otp'),
    path('otp/verify/', verify_otp_view, name='verify_otp'),
    path('profile/', profile_view, name='profile'),
    path('', include(router.urls)),
]
