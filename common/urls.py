from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BannerViewSet,
    NotificationViewSet,
    FAQViewSet,
    ContactTicketViewSet,
    StoreSettingViewSet,
    FooterSectionViewSet,
    PolicyPageViewSet,
    NewsletterSubscriberViewSet,
    footer_data_view,
    admin_dashboard_stats,
)

router = DefaultRouter()
router.register('banners', BannerViewSet, basename='banner')
router.register('notifications', NotificationViewSet, basename='notification')
router.register('faqs', FAQViewSet, basename='faq')
router.register('contact', ContactTicketViewSet, basename='contact')
router.register('store-settings', StoreSettingViewSet, basename='store-settings')
router.register('footer-sections', FooterSectionViewSet, basename='footer-sections')
router.register('policies', PolicyPageViewSet, basename='policies')
router.register('newsletter', NewsletterSubscriberViewSet, basename='newsletter')

urlpatterns = [
    path('footer/', footer_data_view, name='footer_data'),
    path('admin/stats/', admin_dashboard_stats, name='admin_stats'),
    path('', include(router.urls)),
]
