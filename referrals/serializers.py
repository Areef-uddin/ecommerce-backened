from rest_framework import serializers
from .models import ReferralCode, Referral, ReferralReward, ReferralConfig


def mask_name(full_name: str) -> str:
    """Mask a name for privacy (e.g. 'Rahul Sharma' -> 'R***l S***a', 'John' -> 'J***n')."""
    if not full_name:
        return "Friend"
    parts = full_name.strip().split()
    masked_parts = []
    for p in parts:
        if len(p) <= 2:
            masked_parts.append(p[0] + "*")
        else:
            masked_parts.append(p[0] + "*" * (len(p) - 2) + p[-1])
    return " ".join(masked_parts)


class ReferralCodeSerializer(serializers.ModelSerializer):
    referral_link = serializers.SerializerMethodField()

    class Meta:
        model = ReferralCode
        fields = ('code', 'referral_link', 'is_active', 'created_at')

    def get_referral_link(self, obj):
        request = self.context.get('request')
        base_url = request.build_absolute_uri('/') if request else None
        return obj.get_referral_link(base_url)


class ReferralStatsSerializer(serializers.Serializer):
    referral_code = serializers.CharField()
    referral_link = serializers.CharField()
    total_invites = serializers.IntegerField()
    successful_referrals = serializers.IntegerField()
    pending_referrals = serializers.IntegerField()
    rewards_earned = serializers.DecimalField(max_digits=10, decimal_places=2)
    min_order_for_reward = serializers.DecimalField(max_digits=10, decimal_places=2)
    reward_per_referral = serializers.DecimalField(max_digits=10, decimal_places=2)


class ReferralItemSerializer(serializers.ModelSerializer):
    friend_name = serializers.SerializerMethodField()
    referral_date = serializers.DateTimeField(source='created_at', format="%d %b %Y, %I:%M %p")
    reward_amount = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = ('id', 'friend_name', 'status', 'code_used', 'referral_date', 'qualified_at', 'reward_amount')

    def get_friend_name(self, obj):
        name = obj.referred_user.full_name or obj.referred_user.first_name or obj.referred_user.email.split('@')[0]
        return mask_name(name)

    def get_reward_amount(self, obj):
        reward = obj.rewards.filter(is_credited=True).first()
        if reward:
            return float(reward.reward_amount)
        if obj.status == 'pending':
            cfg = ReferralConfig.get_config()
            return float(cfg.reward_amount_referrer)
        return 0.0


class ReferralRewardSerializer(serializers.ModelSerializer):
    credited_date = serializers.DateTimeField(source='credited_at', format="%d %b %Y, %I:%M %p")

    class Meta:
        model = ReferralReward
        fields = ('id', 'reward_amount', 'reward_type', 'is_credited', 'credited_date', 'notes')


class ValidateReferralCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20, required=True)


class ApplyReferralCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=20, required=True)
