from django.urls import path
from .views import (
    MyReferralCodeView,
    MyReferralStatsView,
    MyReferralsListView,
    ValidateReferralCodeView,
    ApplyReferralCodeView,
    MyReferralRewardsView,
    TwilioWhatsAppWebhookView,
)

urlpatterns = [
    path('my-code/', MyReferralCodeView.as_view(), name='referral-my-code'),
    path('my-stats/', MyReferralStatsView.as_view(), name='referral-my-stats'),
    path('my-referrals/', MyReferralsListView.as_view(), name='referral-my-referrals'),
    path('validate/', ValidateReferralCodeView.as_view(), name='referral-validate'),
    path('apply/', ApplyReferralCodeView.as_view(), name='referral-apply'),
    path('rewards/', MyReferralRewardsView.as_view(), name='referral-rewards'),
    path('whatsapp/webhook/', TwilioWhatsAppWebhookView.as_view(), name='referral-whatsapp-webhook'),
]
