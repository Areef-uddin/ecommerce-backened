from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q
from .models import User, OTPVerification, Address
from .serializers import UserSerializer, RegisterSerializer, AddressSerializer

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': UserSerializer(user).data
    }

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        token_data = get_tokens_for_user(user)
        return Response({
            'message': 'Registration successful',
            **token_data
        }, status=status.HTTP_201_CREATED)

    errors = serializer.errors
    error_msg = 'Registration failed'
    if isinstance(errors, dict):
        first_field = next(iter(errors))
        first_err = errors[first_field]
        if isinstance(first_err, list) and first_err:
            error_msg = f"{first_err[0]}"
        else:
            error_msg = f"{first_field}: {first_err}"

    return Response({'detail': error_msg, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    email_or_phone = request.data.get('email_or_phone', '').strip()
    password = request.data.get('password', '')

    if not email_or_phone or not password:
        return Response({'detail': 'Email/Phone and password are required'}, status=status.HTTP_400_BAD_REQUEST)

    # Allow login with either email or phone
    user = None
    if '@' in email_or_phone:
        user = User.objects.filter(email__iexact=email_or_phone).first()
    else:
        user = User.objects.filter(phone=email_or_phone).first()

    if user and user.check_password(password):
        if not user.is_active:
            return Response({'detail': 'User account is disabled'}, status=status.HTTP_403_FORBIDDEN)
        token_data = get_tokens_for_user(user)
        return Response(token_data, status=status.HTTP_200_OK)

    return Response({'detail': 'Invalid email/phone or password'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def google_auth_view(request):
    """
    Authenticate or Register user dynamically using Google credentials
    """
    email = request.data.get('email', '').strip().lower()
    full_name = request.data.get('name', '').strip()
    avatar = request.data.get('avatar', '')

    if not email:
        return Response({'detail': 'Google email is required'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(email=email).first()
    if not user:
        name_parts = full_name.split(' ') if full_name else [email.split('@')[0]]
        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            avatar=avatar or 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400',
            is_active=True
        )
        user.set_unusable_password()
        user.save()
    else:
        if avatar and (not user.avatar or 'placeholder' in user.avatar):
            user.avatar = avatar
            user.save()

    token_data = get_tokens_for_user(user)
    return Response({
        'message': 'Google authentication successful',
        **token_data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def admin_login_view(request):
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    user = User.objects.filter(email__iexact=email).first()
    if user and user.check_password(password):
        if not user.is_staff:
            return Response({'detail': 'Access denied: Staff privileges required'}, status=status.HTTP_403_FORBIDDEN)
        token_data = get_tokens_for_user(user)
        return Response(token_data, status=status.HTTP_200_OK)

    return Response({'detail': 'Invalid admin credentials'}, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def admin_customers_view(request):
    customers = User.objects.filter(is_staff=False).order_by('-date_joined')
    data = []
    for c in customers:
        orders_count = c.orders.count()
        data.append({
            'id': c.id,
            'email': c.email,
            'phone': c.phone or '-',
            'full_name': c.full_name,
            'avatar': c.avatar or 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400',
            'orders_count': orders_count,
            'joined': c.date_joined.strftime('%d %b %Y'),
            'status': 'Active' if c.is_active else 'Disabled'
        })
    return Response(data)

from .twilio_verify import send_twilio_verification, check_twilio_verification, format_e164

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_otp_view(request):
    identifier = request.data.get('identifier', '').strip()
    channel = request.data.get('channel', 'sms')
    if not identifier:
        return Response({'detail': 'Phone number or email is required'}, status=status.HTTP_400_BAD_REQUEST)

    # 1. Always generate a local database OTP backup for simulator/demo resilience
    otp_obj = OTPVerification.generate_otp(identifier)

    # 2. If identifier is a phone number, dispatch real SMS via Twilio Verify v2
    twilio_response = None
    if '@' not in identifier:
        e164_phone = format_e164(identifier)
        twilio_response = send_twilio_verification(e164_phone, channel=channel)
        print(f"[Twilio Verify v2] Sending verification to {e164_phone} via channel '{channel}' -> {twilio_response}")

    print(f"[AUTH OTP SERVICE] Active OTP for {identifier}: {otp_obj.code}")

    response_payload = {
        'message': f'Verification code sent successfully to {identifier}',
        'identifier': identifier,
        'otp': otp_obj.code, # Included for instant developer/simulator testing
    }
    if twilio_response:
        response_payload['twilio'] = twilio_response

    return Response(response_payload, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_otp_view(request):
    identifier = request.data.get('identifier', '').strip()
    code = request.data.get('code', '').strip()

    if not identifier or not code:
        return Response({'detail': 'Identifier and code are required'}, status=status.HTTP_400_BAD_REQUEST)

    # Normalize phone digits for flexible matching
    digits = ''.join(filter(str.isdigit, identifier))
    last10 = digits[-10:] if len(digits) >= 10 else digits

    # 1. Attempt Twilio Verify v2 check first if it's a phone number
    is_verified = False
    verification_source = 'local'
    if '@' not in identifier:
        e164_phone = format_e164(identifier)
        twilio_check = check_twilio_verification(e164_phone, code)
        if twilio_check.get('valid'):
            is_verified = True
            verification_source = 'twilio_verify_v2'
            print(f"[Twilio Verify v2] OTP code verified successfully for {e164_phone}!")

    # 2. If not verified via Twilio, verify against local OTP record
    if not is_verified:
        otp = OTPVerification.objects.filter(
            Q(identifier=identifier) |
            Q(identifier=last10) |
            Q(identifier=f"+91{last10}"),
            code=code
        ).order_by('-created_at').first()

        if otp and otp.is_valid():
            otp.is_verified = True
            otp.save()
            is_verified = True
            verification_source = 'local_otp'

    if not is_verified:
        return Response({'detail': 'Invalid or expired verification code'}, status=status.HTTP_400_BAD_REQUEST)

    # Find or create user with this identifier
    user = None
    if '@' in identifier:
        user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            user = User.objects.create_user(email=identifier, first_name='Shopper')
    else:
        # Check by phone (full, 10-digit, with country code) or legacy placeholder email
        user = User.objects.filter(
            Q(phone=identifier) |
            Q(phone=last10) |
            Q(phone=f"+91{last10}") |
            Q(email=f"user_{last10[-6:]}@stylehub.com")
        ).first()

        if not user:
            email_placeholder = f"user_{last10[-6:]}@stylehub.com"
            if User.objects.filter(email=email_placeholder).exists():
                email_placeholder = f"user_{last10}_{int(timezone.now().timestamp())}@stylehub.com"
            user = User.objects.create_user(
                email=email_placeholder,
                phone=f"+91{last10}",
                first_name='Shopper'
            )
        else:
            if not user.phone or user.phone != f"+91{last10}":
                user.phone = f"+91{last10}"
                user.save(update_fields=['phone'])

    token_data = get_tokens_for_user(user)
    return Response({
        'message': f'Verification successful ({verification_source})',
        **token_data
    }, status=status.HTTP_200_OK)

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def profile_view(request):
    import base64
    import os
    import time
    from django.conf import settings

    user = request.user
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response(serializer.data)
    
    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

    # 1. Handle avatar file upload or base64 image data
    if 'avatar' in request.FILES:
        try:
            avatar_file = request.FILES['avatar']
            avatar_dir = os.path.join(settings.MEDIA_ROOT, 'avatars')
            os.makedirs(avatar_dir, exist_ok=True)
            ext = os.path.splitext(avatar_file.name)[1] or '.png'
            filename = f'user_{user.id}_{int(time.time())}{ext}'
            filepath = os.path.join(avatar_dir, filename)
            with open(filepath, 'wb+') as dest:
                for chunk in avatar_file.chunks():
                    dest.write(chunk)
            user.avatar = request.build_absolute_uri(f'{settings.MEDIA_URL}avatars/{filename}')
        except Exception as e:
            print(f"Error saving avatar file: {e}")
    elif 'avatar' in data and str(data['avatar']).startswith('data:image'):
        try:
            raw_data = str(data['avatar'])
            header, b64_data = raw_data.split(';base64,', 1)
            ext = '.png'
            if 'jpeg' in header or 'jpg' in header:
                ext = '.jpg'
            elif 'webp' in header:
                ext = '.webp'
            avatar_dir = os.path.join(settings.MEDIA_ROOT, 'avatars')
            os.makedirs(avatar_dir, exist_ok=True)
            filename = f'user_{user.id}_{int(time.time())}{ext}'
            filepath = os.path.join(avatar_dir, filename)
            with open(filepath, 'wb') as dest:
                dest.write(base64.b64decode(b64_data))
            user.avatar = request.build_absolute_uri(f'{settings.MEDIA_URL}avatars/{filename}')
        except Exception as e:
            print(f"Error decoding base64 avatar: {e}")
    elif 'avatar' in data and str(data['avatar']).strip():
        user.avatar = str(data['avatar']).strip()

    # 2. Handle Name
    if 'full_name' in data:
        full_name = str(data.get('full_name', '')).strip()
        if full_name:
            parts = full_name.split(' ', 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ''
        else:
            user.first_name = ''
            user.last_name = ''
    elif 'first_name' in data or 'last_name' in data:
        if 'first_name' in data:
            user.first_name = str(data['first_name']).strip()
        if 'last_name' in data:
            user.last_name = str(data['last_name']).strip()

    # 3. Handle Email
    if 'email' in data:
        new_email = str(data['email']).strip().lower()
        if new_email and new_email != user.email:
            if User.objects.filter(email__iexact=new_email).exclude(id=user.id).exists():
                return Response({'email': ['This email is already in use by another account.']}, status=status.HTTP_400_BAD_REQUEST)
            user.email = new_email

    # 4. Handle Phone
    if 'phone' in data:
        new_phone = str(data['phone']).strip()
        if new_phone and new_phone != user.phone:
            if User.objects.filter(phone=new_phone).exclude(id=user.id).exists():
                return Response({'phone': ['This phone number is already registered to another account.']}, status=status.HTTP_400_BAD_REQUEST)
            user.phone = new_phone

    user.save()
    serializer = UserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by('-is_default', '-created_at')

    def perform_create(self, serializer):
        is_first = not Address.objects.filter(user=self.request.user).exists()
        serializer.save(user=self.request.user, is_default=serializer.validated_data.get('is_default', is_first))
