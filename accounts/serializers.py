from rest_framework import serializers
from .models import User, Address

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ('id', 'email', 'phone', 'first_name', 'last_name', 'full_name', 'avatar', 'is_staff', 'date_joined')
        read_only_fields = ('id', 'is_staff', 'date_joined')


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    referral_code = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = User
        fields = ('email', 'phone', 'first_name', 'last_name', 'password', 'referral_code')

    def validate_phone(self, value):
        if not value or not str(value).strip():
            return None
        val = str(value).strip()
        if User.objects.filter(phone=val).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return val

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is required.")
        val = value.strip().lower()
        if User.objects.filter(email__iexact=val).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return val

    def create(self, validated_data):
        ref_code = validated_data.pop('referral_code', None)
        if not validated_data.get('phone'):
            validated_data['phone'] = None
        user = User.objects.create_user(**validated_data)
        try:
            from referrals.models import ReferralCode
            from referrals.services import ReferralService
            ReferralCode.get_or_create_for_user(user)
            if ref_code:
                ReferralService.apply_referral_code(user, ref_code)
        except Exception:
            pass
        return user


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ('id', 'full_name', 'phone', 'address_line', 'city', 'state', 'postal_code', 'address_type', 'is_default', 'created_at')
        read_only_fields = ('id', 'created_at')
