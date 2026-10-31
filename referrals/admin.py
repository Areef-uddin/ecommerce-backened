from django.contrib import admin
from .models import ReferralCode, Referral, ReferralReward, ReferralNotification, ReferralConfig


@admin.register(ReferralConfig)
class ReferralConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'reward_amount_referrer', 'reward_amount_referee', 'min_qualifying_order_value', 'is_active', 'updated_at')

    def has_add_permission(self, request):
        # Singleton pattern in admin
        return not ReferralConfig.objects.exists()


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'is_active', 'created_at')
    search_fields = ('code', 'user__email', 'user__phone')
    list_filter = ('is_active', 'created_at')


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('id', 'referrer', 'referred_user', 'code_used', 'status', 'qualifying_order', 'created_at', 'qualified_at')
    search_fields = ('referrer__email', 'referred_user__email', 'code_used')
    list_filter = ('status', 'created_at')


@admin.register(ReferralReward)
class ReferralRewardAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'reward_amount', 'reward_type', 'is_credited', 'credited_at')
    search_fields = ('user__email', 'referral__code_used')
    list_filter = ('reward_type', 'is_credited', 'credited_at')


@admin.register(ReferralNotification)
class ReferralNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'channel', 'recipient_phone', 'status', 'twilio_message_sid', 'created_at')
    search_fields = ('user__email', 'recipient_phone', 'twilio_message_sid')
    list_filter = ('channel', 'status', 'created_at')
