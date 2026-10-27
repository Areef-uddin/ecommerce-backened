from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
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

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_otp_view(request):
    identifier = request.data.get('identifier', '').strip()
    if not identifier:
        return Response({'detail': 'Phone number or email is required'}, status=status.HTTP_400_BAD_REQUEST)

    otp_obj = OTPVerification.generate_otp(identifier)
    print(f"[AUTH SMS SERVICE] OTP for {identifier}: {otp_obj.code}")
    return Response({
        'message': f'OTP sent successfully to {identifier}',
        'identifier': identifier,
        'otp': otp_obj.code,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def verify_otp_view(request):
    identifier = request.data.get('identifier', '').strip()
    code = request.data.get('code', '').strip()

    if not identifier or not code:
        return Response({'detail': 'Identifier and code are required'}, status=status.HTTP_400_BAD_REQUEST)

    otp = OTPVerification.objects.filter(identifier=identifier, code=code).first()
    if not otp or not otp.is_valid():
        return Response({'detail': 'Invalid or expired OTP code'}, status=status.HTTP_400_BAD_REQUEST)

    otp.is_verified = True
    otp.save()

    # Find or create user with this identifier
    user = None
    if '@' in identifier:
        user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            user = User.objects.create_user(email=identifier, first_name='Shopper')
    else:
        user = User.objects.filter(phone=identifier).first()
        if not user:
            email_placeholder = f"user_{identifier[-6:]}@stylehub.com"
            user = User.objects.create_user(email=email_placeholder, phone=identifier, first_name='Shopper')

    token_data = get_tokens_for_user(user)
    return Response({
        'message': 'OTP verified successfully',
        **token_data
    }, status=status.HTTP_200_OK)

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def profile_view(request):
    user = request.user
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response(serializer.data)
    
    serializer = UserSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by('-is_default', '-created_at')

    def perform_create(self, serializer):
        is_first = not Address.objects.filter(user=self.request.user).exists()
        serializer.save(user=self.request.user, is_default=serializer.validated_data.get('is_default', is_first))
