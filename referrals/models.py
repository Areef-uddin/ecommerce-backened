import random
import string
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


def generate_unique_referral_code(length=8):
    """Generate a clean, uppercase alphanumeric referral code (e.g. SH7A29KX)."""
    chars = ''.join(c for c in string.ascii_uppercase + string.digits if c not in '01IO')
    rand_part = ''.join(random.choices(chars, k=length - 2))
    return f"SH{rand_part}"


class ReferralCode(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_code_profile'
    )
    code = models.CharField(max_length=20, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Referral Code'
        verbose_name_plural = 'Referral Codes'

    def __str__(self):
        return f"{self.user.email} - {self.code}"

    @classmethod
    def get_or_create_for_user(cls, user):
        ref_obj, created = cls.objects.get_or_create(user=user)
        if not ref_obj.code:
            code = generate_unique_referral_code()
            while cls.objects.filter(code=code).exists():
                code = generate_unique_referral_code()
            ref_obj.code = code
            ref_obj.save(update_fields=['code'])
        return ref_obj

    def get_referral_link(self, frontend_url=None):
        base = frontend_url or getattr(settings, 'REFERRAL_FRONTEND_URL', getattr(settings, 'REFERRAL_BASE_URL', 'https://ecommerce-customerapp.vercel.app'))
        base = base.rstrip('/')
        return f"{base}/#/register?ref={self.code}"


class Referral(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Qualification'),
        ('successful', 'Successful'),
        ('rejected', 'Rejected'),
    )

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_sent'
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_received'
    )
    code_used = models.CharField(max_length=20, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    qualifying_order = models.ForeignKey(
        'orders.Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='qualifying_referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    qualified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Referral'
        verbose_name_plural = 'Referrals'

    def __str__(self):
        return f"Referral: {self.referrer.email} -> {self.referred_user.email} ({self.status})"


class ReferralReward(models.Model):
    REWARD_TYPE_CHOICES = (
        ('wallet_credit', 'Wallet Credit'),
        ('discount_coupon', 'Discount Coupon'),
        ('cashback', 'Cashback'),
    )

    referral = models.ForeignKey(
        Referral,
        on_delete=models.CASCADE,
        related_name='rewards'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_rewards'
    )
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('100.00'))
    reward_type = models.CharField(max_length=30, choices=REWARD_TYPE_CHOICES, default='wallet_credit')
    is_credited = models.BooleanField(default=True)
    credited_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-credited_at']
        verbose_name = 'Referral Reward'
        verbose_name_plural = 'Referral Rewards'

    def __str__(self):
        return f"Reward: ₹{self.reward_amount} for {self.user.email}"


class ReferralNotification(models.Model):
    CHANNEL_CHOICES = (
        ('whatsapp', 'WhatsApp'),
        ('in_app', 'In-App'),
        ('sms', 'SMS'),
    )
    STATUS_CHOICES = (
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referral_notifications'
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='whatsapp')
    recipient_phone = models.CharField(max_length=30)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    twilio_message_sid = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Referral Notification'
        verbose_name_plural = 'Referral Notifications'

    def __str__(self):
        return f"Notification to {self.recipient_phone} ({self.status})"


class ReferralConfig(models.Model):
    """Admin-configurable settings for referral rewards."""
    reward_amount_referrer = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('100.00'),
        help_text="Reward credited to referrer upon successful qualification (₹)"
    )
    reward_amount_referee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text="Welcome reward credited to referred user upon signup/first order (₹)"
    )
    min_qualifying_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('300.00'),
        help_text="Minimum order value required to qualify referral (₹)"
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Referral Configuration'
        verbose_name_plural = 'Referral Configuration'

    def __str__(self):
        return f"Config (Referrer: ₹{self.reward_amount_referrer}, Min Order: ₹{self.min_qualifying_order_value})"

    @classmethod
    def get_config(cls):
        cfg = cls.objects.first()
        if not cfg:
            cfg = cls.objects.create(
                reward_amount_referrer=Decimal('100.00'),
                reward_amount_referee=Decimal('50.00'),
                min_qualifying_order_value=Decimal('300.00'),
                is_active=True
            )
        return cfg

