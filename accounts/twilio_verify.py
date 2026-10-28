import logging
import re
from django.conf import settings

logger = logging.getLogger(__name__)

def format_e164(phone: str, default_country_code: str = '+91') -> str:
    """
    Normalizes any raw phone input to E.164 format.
    E.g. '7386872991' -> '+917386872991'
         '07386872991' -> '+917386872991'
         '+91 73868 72991' -> '+917386872991'
    """
    clean = re.sub(r'[^\d+]', '', phone.strip())
    if clean.startswith('+'):
        return clean
    if clean.startswith('0'):
        clean = clean[1:]
    if len(clean) == 10:
        return f"{default_country_code}{clean}"
    if clean.startswith('91') and len(clean) == 12:
        return f"+{clean}"
    return f"{default_country_code}{clean}"


def send_twilio_verification(phone_number: str, channel: str = 'sms') -> dict:
    """
    Sends an OTP using Twilio Verify v2 API.
    Uses TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_VERIFY_SERVICE_SID.
    """
    e164_phone = format_e164(phone_number)
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    service_sid = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None)

    if not account_sid or not auth_token or auth_token == '[AuthToken]':
        logger.info(f"[Twilio Verify] Skipping live Twilio API (Auth token not configured). Using local SMS simulator for {e164_phone}.")
        return {
            'success': False,
            'fallback': True,
            'reason': 'AuthToken not set. Using local OTP simulator.',
            'to': e164_phone
        }

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        verification = client.verify.v2.services(service_sid) \
            .verifications \
            .create(to=e164_phone, channel=channel)

        logger.info(f"[Twilio Verify] Sent verification to {e164_phone}: SID {verification.sid}, Status: {verification.status}")
        return {
            'success': True,
            'status': verification.status,
            'sid': verification.sid,
            'to': verification.to,
            'channel': verification.channel
        }
    except Exception as e:
        logger.error(f"[Twilio Verify Error] Failed to send verification to {e164_phone}: {e}")
        return {
            'success': False,
            'error': str(e),
            'fallback': True,
            'to': e164_phone
        }


def check_twilio_verification(phone_number: str, code: str) -> dict:
    """
    Checks an OTP code against Twilio Verify v2 API.
    """
    e164_phone = format_e164(phone_number)
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    service_sid = getattr(settings, 'TWILIO_VERIFY_SERVICE_SID', None)

    if not account_sid or not auth_token or auth_token == '[AuthToken]':
        return {
            'valid': False,
            'fallback': True,
            'reason': 'AuthToken not set'
        }

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        verification_check = client.verify.v2.services(service_sid) \
            .verification_checks \
            .create(to=e164_phone, code=code.strip())

        logger.info(f"[Twilio Verify] Check for {e164_phone}: status = {verification_check.status}")
        return {
            'valid': verification_check.status == 'approved',
            'status': verification_check.status,
            'sid': verification_check.sid,
            'to': verification_check.to
        }
    except Exception as e:
        logger.error(f"[Twilio Verify Error] Verification check error for {e164_phone}: {e}")
        return {
            'valid': False,
            'error': str(e),
            'fallback': True
        }
