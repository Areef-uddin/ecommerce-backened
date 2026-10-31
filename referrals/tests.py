from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from orders.models import Order
from .models import ReferralCode, Referral, ReferralReward, ReferralConfig
from .services import ReferralService

User = get_user_model()


class ReferralSystemTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Referrer User
        self.referrer = User.objects.create_user(
            email='referrer@example.com',
            password='password123',
            phone='+919876543210',
            first_name='Rahul',
            last_name='Sharma'
        )

        # Create Referee User
        self.referee = User.objects.create_user(
            email='referee@example.com',
            password='password123',
            phone='+919123456789',
            first_name='Amit',
            last_name='Verma'
        )

        # Create Referral Code for Referrer
        self.ref_code = ReferralCode.get_or_create_for_user(self.referrer)

    def test_referral_code_generation(self):
        self.assertTrue(self.ref_code.code.startswith('SH'))
        self.assertEqual(len(self.ref_code.code), 8)
        self.assertIn(self.ref_code.code, self.ref_code.get_referral_link())

    def test_validate_referral_code(self):
        # Valid code
        res = ReferralService.validate_code(self.ref_code.code, current_user=self.referee)
        self.assertTrue(res['valid'])
        self.assertEqual(res['referrer_name'], 'Rahul')

        # Self-referral prevention
        res_self = ReferralService.validate_code(self.ref_code.code, current_user=self.referrer)
        self.assertFalse(res_self['valid'])
        self.assertIn('cannot refer yourself', res_self['detail'].lower())

        # Invalid code
        res_invalid = ReferralService.validate_code('INVALID99', current_user=self.referee)
        self.assertFalse(res_invalid['valid'])

    def test_apply_referral_code_and_prevent_duplicates(self):
        # Apply code
        apply_res = ReferralService.apply_referral_code(self.referee, self.ref_code.code)
        self.assertTrue(apply_res['success'])

        ref = Referral.objects.filter(referred_user=self.referee).first()
        self.assertIsNotNone(ref)
        self.assertEqual(ref.status, 'pending')
        self.assertEqual(ref.referrer, self.referrer)

        # Prevent duplicate application
        apply_duplicate = ReferralService.apply_referral_code(self.referee, self.ref_code.code)
        self.assertFalse(apply_duplicate['success'])
        self.assertIn('already used', apply_duplicate['detail'].lower())

    def test_order_qualification_and_reward_crediting(self):
        # Apply referral
        ReferralService.apply_referral_code(self.referee, self.ref_code.code)

        # 1. Order below min qualifying threshold (default 300)
        low_order = Order.objects.create(
            user=self.referee,
            order_number='#SHLOW001',
            total_amount=Decimal('150.00'),
            order_status='Placed',
            payment_status='Paid'
        )
        qualified_low = ReferralService.process_order_qualification(low_order)
        self.assertFalse(qualified_low)
        self.assertEqual(Referral.objects.get(referred_user=self.referee).status, 'pending')

        # 2. Qualifying Order
        qualifying_order = Order.objects.create(
            user=self.referee,
            order_number='#SHQUAL001',
            total_amount=Decimal('999.00'),
            order_status='Placed',
            payment_status='Paid'
        )
        qualified = ReferralService.process_order_qualification(qualifying_order)
        self.assertTrue(qualified)

        ref = Referral.objects.get(referred_user=self.referee)
        self.assertEqual(ref.status, 'successful')
        self.assertEqual(ref.qualifying_order, qualifying_order)
        self.assertIsNotNone(ref.qualified_at)

        # Reward credited
        reward = ReferralReward.objects.filter(referral=ref, user=self.referrer).first()
        self.assertIsNotNone(reward)
        self.assertEqual(reward.reward_amount, Decimal('100.00'))
        self.assertTrue(reward.is_credited)

        # 3. Duplicate order should not reward again
        second_order = Order.objects.create(
            user=self.referee,
            order_number='#SHQUAL002',
            total_amount=Decimal('1200.00'),
            order_status='Placed',
            payment_status='Paid'
        )
        qualified_second = ReferralService.process_order_qualification(second_order)
        self.assertFalse(qualified_second)
        self.assertEqual(ReferralReward.objects.filter(referral=ref).count(), 1)

    def test_api_my_code_and_stats(self):
        self.client.force_authenticate(user=self.referrer)

        # GET /api/referrals/my-code/
        res_code = self.client.get('/api/referrals/my-code/')
        self.assertEqual(res_code.status_code, status.HTTP_200_OK)
        self.assertEqual(res_code.data['code'], self.ref_code.code)

        # Apply referral to referee and qualify
        ReferralService.apply_referral_code(self.referee, self.ref_code.code)
        order = Order.objects.create(
            user=self.referee,
            order_number='#SHAPITEST01',
            total_amount=Decimal('899.00'),
            order_status='Placed',
            payment_status='Paid'
        )
        ReferralService.process_order_qualification(order)

        # GET /api/referrals/my-stats/
        res_stats = self.client.get('/api/referrals/my-stats/')
        self.assertEqual(res_stats.status_code, status.HTTP_200_OK)
        self.assertEqual(res_stats.data['total_invites'], 1)
        self.assertEqual(res_stats.data['successful_referrals'], 1)
        self.assertEqual(res_stats.data['pending_referrals'], 0)
        self.assertEqual(float(res_stats.data['rewards_earned']), 100.0)

        # GET /api/referrals/my-referrals/
        res_list = self.client.get('/api/referrals/my-referrals/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data['results']), 1)
        # Check privacy masking
        self.assertIn('*', res_list.data['results'][0]['friend_name'])
