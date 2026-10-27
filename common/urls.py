from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BannerViewSet, NotificationViewSet, FAQViewSet, ContactTicketViewSet, admin_dashboard_stats

router = DefaultRouter()
router.register('banners', BannerViewSet, basename='banner')
router.register('notifications', NotificationViewSet, basename='notification')
router.register('faqs', FAQViewSet, basename='faq')
router.register('contact', ContactTicketViewSet, basename='contact')

urlpatterns = [
    path('admin/stats/', admin_dashboard_stats, name='admin_stats'),
    path('', include(router.urls)),
]
