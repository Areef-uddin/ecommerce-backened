from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Order, ShipmentTracking, TrackingMilestone, TRACKING_STAGES_CONFIG
from .courier import get_courier_provider

User = get_user_model()

class CourierTrackingSystemTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.provider = get_courier_provider()

        # Customer 1
        self.customer1 = User.objects.create_user(
            email='priya@test.com',
            password='password123',
            first_name='Priya',
            last_name='Sharma',
            phone='+919876543210'
        )

        # Customer 2
        self.customer2 = User.objects.create_user(
            email='ananya@test.com',
            password='password123',
            first_name='Ananya',
            last_name='Patel',
            phone='+919876543211'
        )

        # Admin user
        self.admin_user = User.objects.create_superuser(
            email='admin@test.com',
            password='adminpassword',
            first_name='Admin',
            last_name='User'
        )

        # Create Order for customer 1
        self.order1 = Order.objects.create(
            user=self.customer1,
            customer_name='Priya Sharma',
            phone='+91 9876543210',
            delivery_address='123 Fashion Street, Bengaluru',
            total_amount=1999.00,
            order_status='Order Placed'
        )
        self.shipment1 = self.provider.create_shipment(self.order1)

    def test_tracking_number_generation_and_milestones(self):
        """Verify tracking number format such as TEST-FASH-1001 and all 7 milestones."""
        expected_number = f"TEST-FASH-{1000 + self.order1.id}"
        self.assertEqual(self.shipment1.tracking_number, expected_number)
        self.assertTrue(self.shipment1.is_demo_mode)
        self.assertEqual(self.shipment1.milestones.count(), 7)

        # First stage should be completed, others not completed
        first_milestone = self.shipment1.milestones.get(order_index=0)
        self.assertEqual(first_milestone.status_step, 'Order Placed')
        self.assertTrue(first_milestone.is_completed)

        last_milestone = self.shipment1.milestones.get(order_index=6)
        self.assertEqual(last_milestone.status_step, 'Delivered')
        self.assertFalse(last_milestone.is_completed)

    def test_admin_update_and_simulation(self):
        """Admin can advance tracking status through the 7 stages."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Advance to 'In Transit'
        res = self.client.post(
            f'/api/orders/orders/{self.order1.id}/simulate_tracking/',
            {
                'status': 'In Transit',
                'location': 'Mumbai Regional Sorting Hub',
                'note': 'Package is en-route on express carrier.'
            },
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        # Verify database update
        self.shipment1.refresh_from_db()
        self.assertEqual(self.shipment1.current_status, 'In Transit')
        self.assertEqual(self.shipment1.current_location, 'Mumbai Regional Sorting Hub')
        
        # Milestones 0 to 4 should now be completed
        completed_count = self.shipment1.milestones.filter(is_completed=True).count()
        self.assertEqual(completed_count, 5) # 0: Order Placed, 1: Confirmed, 2: Packed, 3: Picked Up, 4: In Transit

        # Step 6 (Delivered) MUST NOT be completed
        delivered_milestone = self.shipment1.milestones.get(order_index=6)
        self.assertFalse(delivered_milestone.is_completed)

    def test_customer_cannot_view_others_tracking(self):
        """Enforce permissions: Customer 2 cannot access Customer 1's tracking."""
        self.client.force_authenticate(user=self.customer2)
        res = self.client.get(f'/api/orders/orders/{self.order1.id}/tracking/')
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_customer_can_view_own_tracking(self):
        """Customer 1 can access their own tracking."""
        self.client.force_authenticate(user=self.customer1)
        res = self.client.get(f'/api/orders/orders/{self.order1.id}/tracking/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['tracking_number'], self.shipment1.tracking_number)
        self.assertTrue(res.data['is_demo_mode'])
        self.assertEqual(len(res.data['milestones']), 7)

    def test_non_admin_cannot_update_status(self):
        """Unauthorized customer cannot update order status."""
        self.client.force_authenticate(user=self.customer1)
        res = self.client.post(
            f'/api/orders/orders/{self.order1.id}/update_status/',
            {'status': 'Delivered'},
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
