import logging
import os
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import (
    ReferralCode,
    Referral,
    ReferralReward,
    ReferralNotification,
    ReferralConfig,
)

logger = logging.getLogger(__name__)


class TwilioWhatsAppService:
    """
    Production-ready Twilio WhatsApp Business API integration.
    Securely loads credentials from environment variables.
    Never exposes credentials to the frontend.
    """

    @classmethod
    def is_configured(cls) -> bool:
        sid = os.environ.get('TWILIO_ACCOUNT_SID', getattr(settings, 'TWILIO_ACCOUNT_SID', '')).strip()
        token = os.environ.get('TWILIO_AUTH_TOKEN', getattr(settings, 'TWILIO_AUTH_TOKEN', '')).strip()
        return bool(sid and token)

    @classmethod
    def get_client(cls):
        if not cls.is_configured():
            return None
        try:
            from twilio.rest import Client
            sid = os.environ.get('TWILIO_ACCOUNT_SID', getattr(settings, 'TWILIO_ACCOUNT_SID', '')).strip()
            token = os.environ.get('TWILIO_AUTH_TOKEN', getattr(settings, 'TWILIO_AUTH_TOKEN', '')).strip()
            return Client(sid, token)
        except Exception as e:
            logger.error(f"[TwilioWhatsAppService] Failed to initialize client: {e}")
            return None

    @classmethod
    def format_whatsapp_number(cls, phone: str) -> str:
        """Format an Indian or international phone number for Twilio WhatsApp (whatsapp:+91...)"""
        if not phone:
            return ""
        clean = ''.join(c for c in phone if c.isdigit() or c == '+')
        if not clean.startswith('+'):
            if len(clean) == 10:
                clean = f"+91{clean}"
            else:
                clean = f"+{clean}"
        return f"whatsapp:{clean}"

    @classmethod
    def send_whatsapp_message(cls, to_phone: str, message_body: str, user=None) -> dict:
        """
        Sends a WhatsApp message via Twilio.
        Logs every notification in ReferralNotification table.
        """
        from_number = os.environ.get(
            'TWILIO_WHATSAPP_FROM',
            getattr(settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        ).strip()
        if not from_number.startswith('whatsapp:'):
            from_number = f"whatsapp:{from_number}"

        to_formatted = cls.format_whatsapp_number(to_phone)
        if not to_formatted:
            logger.warning("[TwilioWhatsAppService] Missing destination phone number.")
            return {'success': False, 'error': 'Invalid phone number'}

        client = cls.get_client()
        if not client:
            logger.warning("[TwilioWhatsAppService] Twilio credentials not configured; message logged only.")
            if user:
                ReferralNotification.objects.create(
                    user=user,
                    channel='whatsapp',
                    recipient_phone=to_formatted,
                    message=message_body,
                    status='queued',
                    error_message='Twilio credentials not configured'
                )
            return {'success': True, 'queued': True, 'sid': 'MOCK_DEV_SID'}

        try:
            message = client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_formatted
            )
            logger.info(f"[TwilioWhatsAppService] Sent WhatsApp message SID: {message.sid} to {to_formatted}")
            if user:
                ReferralNotification.objects.create(
                    user=user,
                    channel='whatsapp',
                    recipient_phone=to_formatted,
                    message=message_body,
                    status='sent',
                    twilio_message_sid=message.sid
                )
            return {'success': True, 'sid': message.sid}
        except Exception as exc:
            logger.error(f"[TwilioWhatsAppService] Error sending message: {exc}")
            if user:
                ReferralNotification.objects.create(
                    user=user,
                    channel='whatsapp',
                    recipient_phone=to_formatted,
                    message=message_body,
                    status='failed',
                    error_message=str(exc)
                )
            return {'success': False, 'error': str(exc)}

    @classmethod
    def notify_referrer_reward_unlocked(cls, referrer_user, referred_user, reward_amount: Decimal):
        """Send celebratory WhatsApp update to the referrer when an order qualifies the referral."""
        phone = getattr(referrer_user, 'phone', None)
        if not phone:
            return

        friend_name = referred_user.first_name or referred_user.full_name or "Your friend"
        msg = (
            f"🎉 *StyleHub Referral Reward Unlocked!*\n\n"
            f"Great news! {friend_name} has completed their first eligible order using your referral code.\n\n"
            f"🎁 *Reward Earned:* ₹{reward_amount:.2f}\n"
            f"The reward has been credited to your StyleHub account.\n\n"
            f"Keep inviting friends to earn more rewards!"
        )
        return cls.send_whatsapp_message(to_phone=phone, message_body=msg, user=referrer_user)

    @classmethod
    def notify_referrer_friend_joined(cls, referrer_user, referred_user):
        """Send WhatsApp update when a friend registers using their referral link."""
        phone = getattr(referrer_user, 'phone', None)
        if not phone:
            return

        friend_name = referred_user.first_name or "A friend"
        msg = (
            f"👋 *StyleHub Alert!*\n\n"
            f"{friend_name} just joined StyleHub using your referral link!\n\n"
            f"Once they place their first order, your referral reward will be automatically credited.\n"
            f"Thank you for sharing StyleHub!"
        )
        return cls.send_whatsapp_message(to_phone=phone, message_body=msg, user=referrer_user)


class ReferralService:
    """Core business logic for referral codes, validation, application, and order qualification."""

    @classmethod
    def validate_code(cls, code: str, current_user=None) -> dict:
        """Validate if a referral code exists, is active, and is not a self-referral."""
        if not code or not str(code).strip():
            return {'valid': False, 'detail': 'Referral code cannot be empty.'}

        code_clean = str(code).strip().upper()
        ref_code = ReferralCode.objects.filter(code__iexact=code_clean, is_active=True).select_related('user').first()
        if not ref_code:
            return {'valid': False, 'detail': 'Invalid or inactive referral code.'}

        if current_user and current_user.is_authenticated and ref_code.user_id == current_user.id:
            return {'valid': False, 'detail': 'You cannot refer yourself.'}

        referrer_name = ref_code.user.first_name or ref_code.user.full_name or 'StyleHub Member'
        return {
            'valid': True,
            'code': ref_code.code,
            'referrer_name': referrer_name,
            'detail': f'Valid referral code from {referrer_name}.'
        }

    @classmethod
    @transaction.atomic
    def apply_referral_code(cls, referred_user, code: str) -> dict:
        """
        Apply a referral code to a registered user.
        Strict guarantees:
        - Only 1 referral per referred user (cannot change referral ownership after signup)
        - Cannot refer self
        - Atomic and duplicate-safe
        """
        if not referred_user or not referred_user.is_authenticated:
            return {'success': False, 'detail': 'Authentication required.'}

        # Check if user was already referred
        if Referral.objects.filter(referred_user=referred_user).exists():
            return {'success': False, 'detail': 'You have already used a referral code.'}

        val = cls.validate_code(code, current_user=referred_user)
        if not val['valid']:
            return {'success': False, 'detail': val['detail']}

        ref_code = ReferralCode.objects.get(code__iexact=val['code'])
        referrer = ref_code.user

        referral = Referral.objects.create(
            referrer=referrer,
            referred_user=referred_user,
            code_used=ref_code.code,
            status='pending'
        )

        # Notify referrer via WhatsApp in background
        try:
            TwilioWhatsAppService.notify_referrer_friend_joined(referrer, referred_user)
        except Exception as e:
            logger.warning(f"Twilio friend joined notification failed: {e}")

        return {
            'success': True,
            'referral_id': referral.id,
            'referrer_name': val['referrer_name'],
            'detail': f"Referral code applied successfully from {val['referrer_name']}!"
        }

    @classmethod
    @transaction.atomic
    def process_order_qualification(cls, order) -> bool:
        """
        Called when an order is completed/paid.
        Verifies if customer was referred, checks qualifying conditions,
        creates ReferralReward atomically, updates referral status to 'successful',
        and triggers Twilio WhatsApp notification.
        """
        if not order or not order.user:
            return False

        # Find pending referral for this user with select_for_update for atomicity
        referral = Referral.objects.select_for_update().filter(
            referred_user=order.user,
            status='pending'
        ).first()

        if not referral:
            return False  # No pending referral for this user

        config = ReferralConfig.get_config()
        if not config.is_active:
            logger.info("Referral qualification skipped: referral system is currently paused in config.")
            return False

        # Check order amount requirement
        order_total = Decimal(str(order.total_amount or 0))
        if order_total < config.min_qualifying_order_value:
            logger.info(
                f"Order {order.order_number} (₹{order_total}) below min qualifying value ₹{config.min_qualifying_order_value}."
            )
            return False

        # Ensure order is not cancelled or failed
        if str(order.order_status).lower() in ('cancelled', 'failed'):
            return False

        # Mark referral successful
        referral.status = 'successful'
        referral.qualifying_order = order
        referral.qualified_at = timezone.now()
        referral.save(update_fields=['status', 'qualifying_order', 'qualified_at'])

        # Create ReferralReward for referrer (atomic, duplicate-protected)
        reward_amount = config.reward_amount_referrer
        reward, created = ReferralReward.objects.get_or_create(
            referral=referral,
            user=referral.referrer,
            defaults={
                'reward_amount': reward_amount,
                'reward_type': 'wallet_credit',
                'is_credited': True,
                'credited_at': timezone.now(),
                'notes': f"Earned from referral of {order.user.email} (Order {order.order_number})"
            }
        )

        logger.info(
            f"[Referral Qualification] Credited ₹{reward_amount} to referrer {referral.referrer.email} for order {order.order_number}."
        )

        # Trigger Twilio WhatsApp notification
        try:
            TwilioWhatsAppService.notify_referrer_reward_unlocked(
                referrer_user=referral.referrer,
                referred_user=order.user,
                reward_amount=reward_amount
            )
        except Exception as e:
            logger.error(f"[TwilioWhatsAppService] Notification error: {e}")

        return True

    @classmethod
    @transaction.atomic
    def handle_order_cancellation(cls, order):
        """
        If an order that qualified a referral is cancelled or refunded,
        revert the referral status to pending and mark the reward.
        """
        referral = Referral.objects.select_for_update().filter(
            qualifying_order=order,
            status='successful'
        ).first()

        if referral:
            referral.status = 'pending'
            referral.qualifying_order = None
            referral.qualified_at = None
            referral.save(update_fields=['status', 'qualifying_order', 'qualified_at'])

            ReferralReward.objects.filter(referral=referral).update(
                is_credited=False,
                notes=f"Voided due to order {order.order_number} cancellation."
            )
            logger.info(f"Reverted referral qualification for order {order.order_number}.")

