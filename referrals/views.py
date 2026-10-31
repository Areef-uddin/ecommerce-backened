from decimal import Decimal
from django.db.models import Sum
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import ReferralCode, Referral, ReferralReward, ReferralConfig
from .serializers import (
    ReferralCodeSerializer,
    ReferralStatsSerializer,
    ReferralItemSerializer,
    ReferralRewardSerializer,
    ValidateReferralCodeSerializer,
    ApplyReferralCodeSerializer,
)
from .services import ReferralService


class ReferralPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class MyReferralCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ref_obj = ReferralCode.get_or_create_for_user(request.user)
        serializer = ReferralCodeSerializer(ref_obj, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class MyReferralStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ref_obj = ReferralCode.get_or_create_for_user(request.user)
        user = request.user

        referrals_qs = Referral.objects.filter(referrer=user)
        total_invites = referrals_qs.count()
        successful_referrals = referrals_qs.filter(status='successful').count()
        pending_referrals = referrals_qs.filter(status='pending').count()

        rewards_total = ReferralReward.objects.filter(
            user=user,
            is_credited=True
        ).aggregate(total=Sum('reward_amount'))['total'] or Decimal('0.00')

        config = ReferralConfig.get_config()

        serializer = ReferralStatsSerializer({
            'referral_code': ref_obj.code,
            'referral_link': ref_obj.get_referral_link(),
            'total_invites': total_invites,
            'successful_referrals': successful_referrals,
            'pending_referrals': pending_referrals,
            'rewards_earned': rewards_total,
            'min_order_for_reward': config.min_qualifying_order_value,
            'reward_per_referral': config.reward_amount_referrer,
        })
        return Response(serializer.data, status=status.HTTP_200_OK)


class MyReferralsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        referrals = Referral.objects.filter(referrer=user).select_related('referred_user').prefetch_related('rewards').order_by('-created_at')
        
        status_filter = request.query_params.get('status')
        if status_filter in ('pending', 'successful', 'rejected'):
            referrals = referrals.filter(status=status_filter)

        paginator = ReferralPagination()
        page = paginator.paginate_queryset(referrals, request)
        serializer = ReferralItemSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class ValidateReferralCodeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ValidateReferralCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data['code']
        result = ReferralService.validate_code(code, current_user=request.user)
        return Response(result, status=status.HTTP_200_OK if result['valid'] else status.HTTP_400_BAD_REQUEST)


class ApplyReferralCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ApplyReferralCodeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        code = serializer.validated_data['code']
        result = ReferralService.apply_referral_code(referred_user=request.user, code=code)
        
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


class MyReferralRewardsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rewards = ReferralReward.objects.filter(user=request.user).order_by('-credited_at')
        serializer = ReferralRewardSerializer(rewards, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TwilioWhatsAppWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        Receives webhook callbacks from Twilio for WhatsApp message status or inbound customer messages.
        """
        from_number = request.data.get('From', '')
        body = request.data.get('Body', '').strip().upper()
        sms_status = request.data.get('SmsStatus', '')
        message_sid = request.data.get('MessageSid', '')

        # Handle opt-out requests like STOP, UNSUBSCRIBE
        if body in ('STOP', 'UNSUBSCRIBE', 'CANCEL'):
            return Response({'status': 'opted_out'}, status=status.HTTP_200_OK)

        return Response({'status': 'received', 'message_sid': message_sid}, status=status.HTTP_200_OK)

