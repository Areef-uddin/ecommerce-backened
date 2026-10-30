from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch
from rest_framework.test import APIClient
from rest_framework import status
from django.test import override_settings
from .models import CartItem, Order, OrderItem, ReturnTimeline, ShipmentTracking, TrackingMilestone, TRACKING_STAGES_CONFIG
from common.models import Notification
from .courier import get_courier_provider
from products.models import Category, Product

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

    def test_buy_again_readds_order_products_and_merges_existing_cart_quantity(self):
        category = Category.objects.create(name='Buy Again Test', slug='buy-again-test')
        product = Product.objects.create(
            name='Buy Again Shirt',
            slug='buy-again-shirt',
            category=category,
            description='Test product',
            price='1200.00',
        )
        OrderItem.objects.create(
            order=self.order1,
            product=product,
            product_name=product.name,
            price=product.price,
            quantity=2,
            size='M',
            color='Blue',
        )
        CartItem.objects.create(
            user=self.customer1,
            product=product,
            quantity=1,
            size='M',
            color='Blue',
        )
        self.client.force_authenticate(user=self.customer1)

        response = self.client.post(
            f'/api/orders/orders/{self.order1.id}/buy_again/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['added_items'], 1)
        self.assertEqual(
            CartItem.objects.get(user=self.customer1, product=product).quantity,
            3,
        )
    def test_non_admin_cannot_update_status(self):
        """Unauthorized customer cannot update order status."""
        self.client.force_authenticate(user=self.customer1)
        res = self.client.post(
            f'/api/orders/orders/{self.order1.id}/update_status/',
            {'status': 'Delivered'},
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_shipped_filter_includes_in_flight_statuses(self):
        self.client.force_authenticate(user=self.customer1)
        shipping_orders = []
        for stage in ['Picked Up', 'In Transit', 'Shipped', 'Out for Delivery']:
            shipping_orders.append(Order.objects.create(
                user=self.customer1,
                customer_name='Priya Sharma',
                phone='+91 9876543210',
                delivery_address='123 Fashion Street, Bengaluru',
                total_amount=100,
                order_status=stage,
            ).id)
        delivered = Order.objects.create(
            user=self.customer1,
            customer_name='Priya Sharma',
            phone='+91 9876543210',
            delivery_address='123 Fashion Street, Bengaluru',
            total_amount=100,
            order_status='Delivered',
        )

        response = self.client.get('/api/orders/orders/?status=Shipped')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {order['id'] for order in response.data}
        self.assertTrue(set(shipping_orders).issubset(returned_ids))
        self.assertNotIn(delivered.id, returned_ids)

    def test_customer_processing_filter_contains_only_unshipped_orders(self):
        self.client.force_authenticate(user=self.customer1)
        processing_ids = []
        for stage in ['Processing', 'Placed', 'Order Placed', 'Confirmed', 'Packed']:
            processing_ids.append(Order.objects.create(
                user=self.customer1,
                customer_name='Priya Sharma',
                phone='+91 9876543210',
                delivery_address='123 Fashion Street, Bengaluru',
                total_amount=100,
                order_status=stage,
            ).id)
        shipped = Order.objects.create(
            user=self.customer1,
            customer_name='Priya Sharma',
            phone='+91 9876543210',
            delivery_address='123 Fashion Street, Bengaluru',
            total_amount=100,
            order_status='Shipped',
        )

        response = self.client.get('/api/orders/orders/?status=Processing')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {order['id'] for order in response.data}
        self.assertTrue(set(processing_ids).issubset(returned_ids))
        self.assertNotIn(shipped.id, returned_ids)

    def test_cod_payment_is_recorded_paid_on_delivery(self):
        order = Order.objects.create(
            user=self.customer1,
            customer_name='Priya Sharma',
            phone='+91 9876543210',
            delivery_address='123 Fashion Street, Bengaluru',
            total_amount=100,
            payment_method='Cash on Delivery',
            payment_status='Pending',
            order_status='Order Placed',
        )
        shipment = self.provider.create_shipment(order)

        self.provider.update_status(shipment.tracking_number, 'Delivered')

        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'Paid')

    def test_return_refund_requires_delivery_and_received_item(self):
        category = Category.objects.create(name='Test', slug='test')
        product = Product.objects.create(
            name='Test item', slug='test-item', category=category,
            description='Test item', price=100,
        )
        order = Order.objects.create(
            user=self.customer1,
            customer_name='Priya Sharma',
            phone='+91 9876543210',
            delivery_address='123 Fashion Street, Bengaluru',
            item_total=100,
            total_amount=100,
            payment_method='Cash on Delivery',
            payment_status='Pending',
            order_status='Order Placed',
        )
        item = OrderItem.objects.create(
            order=order, product=product, product_name=product.name,
            price=100, quantity=1,
        )
        shipment = self.provider.create_shipment(order)
        self.provider.update_status(shipment.tracking_number, 'Delivered')

        self.client.force_authenticate(user=self.customer1)
        missing_item = self.client.post('/api/orders/returns/', {
            'order_id': order.id,
            'reason': 'Defective',
            'pickup_type': 'Pickup',
        }, format='json')
        self.assertEqual(missing_item.status_code, status.HTTP_400_BAD_REQUEST)

        created = self.client.post('/api/orders/returns/', {
            'order_id': order.id,
            'order_item_id': item.id,
            'reason': 'Defective',
            'pickup_type': 'Pickup',
        }, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(str(created.data['refund_amount']), '100.00')
        self.assertEqual([event['status'] for event in created.data['timeline']], ['Initiated'])
        order_detail = self.client.get(f'/api/orders/orders/{order.id}/')
        self.assertTrue(order_detail.data['return_eligible'])
        self.assertEqual(order_detail.data['returns'][0]['id'], created.data['id'])
        self.assertEqual(Notification.objects.filter(user=self.customer1).count(), 1)

        self.client.force_authenticate(user=self.admin_user)
        refund_id = created.data['id']
        premature_refund = self.client.post(
            f'/api/orders/returns/{refund_id}/update_status/',
            {'status': 'Refund Processed', 'manual_refund_confirmed': True}, format='json'
        )
        self.assertEqual(premature_refund.status_code, status.HTTP_400_BAD_REQUEST)

        scheduled = self.client.post(
            f'/api/orders/returns/{refund_id}/update_status/',
            {'status': 'Pickup Scheduled'}, format='json'
        )
        self.assertEqual(scheduled.status_code, status.HTTP_200_OK)
        received = self.client.post(
            f'/api/orders/returns/{refund_id}/update_status/',
            {'status': 'Pickup Received'}, format='json'
        )
        self.assertEqual(received.status_code, status.HTTP_200_OK)
        refunded = self.client.post(
            f'/api/orders/returns/{refund_id}/update_status/',
            {'status': 'Refund Processed', 'manual_refund_confirmed': True}, format='json'
        )
        self.assertEqual(refunded.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [event.status for event in ReturnTimeline.objects.filter(return_request_id=refund_id)],
            ['Initiated', 'Pickup Scheduled', 'Pickup Received', 'Refund Processed'],
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'Refunded')
        self.client.force_authenticate(user=self.customer1)
        refreshed_order = self.client.get(f'/api/orders/orders/{order.id}/')
        self.assertEqual(refreshed_order.data['payment_status'], 'Refunded')
        self.assertEqual(refreshed_order.data['returns'][0]['status'], 'Refund Processed')
        self.assertEqual(Notification.objects.filter(user=self.customer1).count(), 4)

    def test_razorpay_refund_stays_pending_until_gateway_confirms_processing(self):
        category = Category.objects.create(name='Online Return', slug='online-return')
        product = Product.objects.create(
            name='Online return item', slug='online-return-item', category=category,
            description='Online return test item', price=250,
        )
        order = Order.objects.create(
            user=self.customer1,
            customer_name='Priya Sharma',
            phone='+91 9876543210',
            delivery_address='123 Fashion Street, Bengaluru',
            item_total=250,
            total_amount=250,
            payment_method='Razorpay',
            payment_status='Paid',
            payment_reference='pay_return_test',
            order_status='Order Placed',
        )
        item = OrderItem.objects.create(order=order, product=product, product_name=product.name, price=250)
        shipment = self.provider.create_shipment(order)
        self.provider.update_status(shipment.tracking_number, 'Delivered')

        self.client.force_authenticate(user=self.customer1)
        created = self.client.post('/api/orders/returns/', {
            'order_id': order.id,
            'order_item_id': item.id,
            'reason': 'Defective',
            'pickup_type': 'Pickup',
        }, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        return_id = created.data['id']

        self.client.force_authenticate(user=self.admin_user)
        self.client.post(f'/api/orders/returns/{return_id}/update_status/', {'status': 'Pickup Scheduled'}, format='json')
        self.client.post(f'/api/orders/returns/{return_id}/update_status/', {'status': 'Pickup Received'}, format='json')
        with override_settings(RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='test-secret'):
            with patch('orders.views.razorpay.Client') as client_factory:
                gateway = client_factory.return_value
                gateway.payment.refund.return_value = {'id': 'rfnd_return_test', 'status': 'pending'}
                pending = self.client.post(
                    f'/api/orders/returns/{return_id}/update_status/',
                    {'status': 'Refund Processed'}, format='json',
                )
                self.assertEqual(pending.status_code, status.HTTP_200_OK)
                self.assertEqual(pending.data['status'], 'Refund Pending')
                self.assertEqual(gateway.payment.refund.call_args.args[0], 'pay_return_test')

                gateway.refund.fetch.return_value = {'id': 'rfnd_return_test', 'status': 'pending'}
                still_pending = self.client.post(
                    f'/api/orders/returns/{return_id}/update_status/',
                    {'status': 'Refund Processed'}, format='json',
                )
                self.assertEqual(still_pending.status_code, status.HTTP_202_ACCEPTED)

                gateway.refund.fetch.return_value = {'id': 'rfnd_return_test', 'status': 'processed'}
                processed = self.client.post(
                    f'/api/orders/returns/{return_id}/update_status/',
                    {'status': 'Refund Processed'}, format='json',
                )
                self.assertEqual(processed.status_code, status.HTTP_200_OK)
                self.assertEqual(processed.data['status'], 'Refund Processed')

        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'Refunded')

    def test_authorized_razorpay_payment_is_captured_and_retry_is_idempotent(self):
        category = Category.objects.create(name='Payment Test', slug='payment-test')
        product = Product.objects.create(
            name='Payment item', slug='payment-item', category=category,
            description='Payment test item', price=100,
        )
        CartItem.objects.create(user=self.customer1, product=product, quantity=1)
        self.client.force_authenticate(user=self.customer1)
        body = {
            'razorpay_order_id': 'order_verified_test',
            'razorpay_payment_id': 'pay_verified_test',
            'razorpay_signature': 'valid-test-signature',
        }

        with override_settings(RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='test-secret'):
            with patch('orders.views.razorpay.Client') as client_factory:
                gateway = client_factory.return_value
                gateway.order.fetch.return_value = {
                    'notes': {'user_id': str(self.customer1.id)},
                    'amount': 10000,
                    'currency': 'INR',
                }
                gateway.payment.fetch.return_value = {
                    'order_id': body['razorpay_order_id'],
                    'status': 'authorized',
                    'amount': 10000,
                    'currency': 'INR',
                }
                gateway.payment.capture.return_value = {
                    'order_id': body['razorpay_order_id'],
                    'status': 'captured',
                    'amount': 10000,
                    'currency': 'INR',
                }

                first = self.client.post('/api/orders/orders/verify_razorpay_payment/', body, format='json')
                self.assertEqual(first.status_code, status.HTTP_201_CREATED)
                self.assertEqual(first.data['payment_status'], 'Paid')
                self.assertEqual(Order.objects.get(id=first.data['id']).payment_reference, body['razorpay_payment_id'])
                gateway.payment.capture.assert_called_once_with(body['razorpay_payment_id'], {
                    'amount': 10000,
                    'currency': 'INR',
                })

                retry = self.client.post('/api/orders/orders/verify_razorpay_payment/', body, format='json')
                self.assertEqual(retry.status_code, status.HTTP_200_OK)
                self.assertEqual(retry.data['id'], first.data['id'])
                gateway.order.fetch.assert_called_once_with(body['razorpay_order_id'])
