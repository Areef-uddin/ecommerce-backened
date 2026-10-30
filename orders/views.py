from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db import transaction
import razorpay
from .models import CartItem, Coupon, Order, OrderItem, OrderTimeline, ReturnRequest, ShipmentTracking, TrackingMilestone, TRACKING_STAGES_CONFIG
from .serializers import CartItemSerializer, OrderSerializer, ReturnRequestSerializer, ShipmentTrackingSerializer
from .courier import get_courier_provider
from products.models import Product
from accounts.models import Address

class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user).select_related('product')

    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        size = request.data.get('size', 'M')
        color = request.data.get('color', 'Pink')

        product = Product.objects.filter(id=product_id).first()
        if not product:
            return Response({'detail': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            product=product,
            size=size,
            color=color,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        serializer = self.get_serializer(cart_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        items = self.get_queryset()
        item_total = sum(item.product.price * item.quantity for item in items)
        
        # Calculate discount or coupon if provided
        coupon_code = request.query_params.get('coupon')
        discount_amount = Decimal('0.00')
        coupon_applied = False
        if coupon_code:
            coupon = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
            if coupon and item_total >= coupon.min_order_value:
                discount_amount = min(coupon.discount_amount, item_total)
                coupon_applied = True
        elif item_total > Decimal('2000.00'):
            # Default discount for demo matching screenshot (300 off)
            discount_amount = Decimal('300.00')

        delivery_charges = Decimal('0.00') # FREE
        final_total = max(Decimal('0.00'), item_total - discount_amount + delivery_charges)

        return Response({
            'count': items.count(),
            'item_total': str(item_total),
            'discount_amount': str(discount_amount),
            'delivery_charges': 'FREE' if delivery_charges == 0 else str(delivery_charges),
            'final_total': str(final_total),
            'coupon_applied': coupon_applied
        })

    @action(detail=False, methods=['post'])
    def apply_coupon(self, request):
        code = request.data.get('code', '').strip()
        coupon = Coupon.objects.filter(code__iexact=code, is_active=True).first()
        if not coupon:
            return Response({'detail': 'Invalid or expired coupon code'}, status=status.HTTP_400_BAD_REQUEST)
        
        items = self.get_queryset()
        item_total = sum(item.product.price * item.quantity for item in items)
        if item_total < coupon.min_order_value:
            return Response({'detail': f'Minimum order amount of ₹{coupon.min_order_value} required for this coupon'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': 'Coupon applied successfully!',
            'code': coupon.code,
            'discount_amount': str(coupon.discount_amount)
        })

    @action(detail=False, methods=['delete'])
    def clear(self, request):
        self.get_queryset().delete()
        return Response({'message': 'Cart cleared'})


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Orders can only be created as COD or by the verified payment action.
    # Prevent generic PATCH/PUT from letting a customer edit payment/status fields.
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            qs = Order.objects.all().prefetch_related('items', 'timeline', 'shipment__milestones')
        else:
            qs = Order.objects.filter(user=user).prefetch_related('items', 'timeline', 'shipment__milestones')

        order_status = self.request.query_params.get('status')
        if order_status and order_status.lower() != 'all':
            if order_status.lower() == 'processing':
                qs = qs.filter(order_status__in=['Placed', 'Order Placed', 'Confirmed', 'Packed'])
            elif order_status.lower() == 'shipped':
                qs = qs.filter(order_status__in=['Picked Up', 'In Transit', 'Shipped', 'Out for Delivery'])
            else:
                qs = qs.filter(order_status__iexact=order_status)

        return qs

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def buy_again(self, request, pk=None):
        order = self.get_object()
        added_items = 0
        unavailable_items = []
        for item in order.items.select_related('product').all():
            product = item.product
            if not product or not product.in_stock or product.stock_quantity < 1:
                unavailable_items.append(item.product_name)
                continue

            cart_item, created = CartItem.objects.get_or_create(
                user=request.user,
                product=product,
                size=item.size,
                color=item.color,
                defaults={'quantity': item.quantity},
            )
            if not created:
                cart_item.quantity += item.quantity
                cart_item.save(update_fields=['quantity'])
            added_items += 1

        return Response({
            'added_items': added_items,
            'unavailable_items': unavailable_items,
            'message': 'Available items were added to your cart.' if added_items else 'No items from this order are currently available.',
        })

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        user = request.user
        cart_items = CartItem.objects.filter(user=user).select_related('product')
        if not cart_items.exists():
            return Response({'detail': 'Your cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        address_id = request.data.get('address_id')
        address_obj = Address.objects.filter(id=address_id, user=user).first() if address_id else None

        if address_obj:
            customer_name = address_obj.full_name
            phone = address_obj.phone
            delivery_address = f"{address_obj.address_line}, {address_obj.city} - {address_obj.postal_code}"
            address_type = address_obj.address_type
        else:
            customer_name = request.data.get('customer_name', user.full_name)
            phone = request.data.get('phone', user.phone or '+91 9876543210')
            delivery_address = request.data.get('delivery_address', '12-3-456, MG Road, Bengaluru - 560001')
            address_type = request.data.get('address_type', 'Home')

        payment_method = request.data.get('payment_method', 'UPI')
        if payment_method not in ['Cash on Delivery', 'COD']:
            return Response(
                {'detail': 'Online orders must be completed through verified Razorpay checkout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        coupon_code = request.data.get('coupon_code')

        # Compute totals
        item_total = sum(item.product.price * item.quantity for item in cart_items)
        discount_amount = Decimal('0.00')
        if coupon_code:
            coupon = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
            if coupon and item_total >= coupon.min_order_value:
                discount_amount = min(coupon.discount_amount, item_total)
        elif item_total > Decimal('2000.00'):
            discount_amount = Decimal('300.00')

        delivery_charges = Decimal('0.00')
        total_amount = max(Decimal('0.00'), item_total - discount_amount + delivery_charges)

        order = Order.objects.create(
            user=user,
            customer_name=customer_name,
            phone=phone,
            delivery_address=delivery_address,
            address_type=address_type,
            payment_method=payment_method,
            payment_status='Pending' if payment_method in ['Cash on Delivery', 'COD'] else 'Paid',
            order_status='Order Placed',
            item_total=item_total,
            discount_amount=discount_amount,
            delivery_charges=delivery_charges,
            total_amount=total_amount,
            estimated_delivery='31 Oct - 03 Nov'
        )

        # Create Order Items
        for ci in cart_items:
            img = ci.product.images.first()
            img_url = img.image_url if img else ''
            OrderItem.objects.create(
                order=order,
                product=ci.product,
                product_name=ci.product.name,
                price=ci.product.price,
                quantity=ci.quantity,
                size=ci.size,
                color=ci.color,
                image_url=img_url
            )

        # Initialize Tracking Record and 7 Milestones via Courier Provider
        courier_provider = get_courier_provider()
        courier_provider.create_shipment(order)

        # Clear cart
        cart_items.delete()

        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def create_razorpay_order(self, request):
        user = request.user
        cart_items = CartItem.objects.filter(user=user).select_related('product')
        if not cart_items.exists():
            return Response({'detail': 'Your cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        coupon_code = request.data.get('coupon_code')
        item_total = sum(item.product.price * item.quantity for item in cart_items)
        discount_amount = Decimal('0.00')
        if coupon_code:
            coupon = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
            if coupon and item_total >= coupon.min_order_value:
                discount_amount = min(coupon.discount_amount, item_total)
        elif item_total > Decimal('2000.00'):
            discount_amount = Decimal('300.00')

        delivery_charges = Decimal('0.00')
        total_amount = max(Decimal('1.00'), item_total - discount_amount + delivery_charges)
        amount_in_paise = int(total_amount * 100)

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            if settings.DEBUG:
                return Response({
                    'razorpay_order_id': f"order_sim_{int(timezone.now().timestamp())}",
                    'amount': amount_in_paise,
                    'currency': 'INR',
                    'key_id': '',
                    'total_amount': str(total_amount),
                    'simulated': True,
                })
            return Response(
                {'detail': 'Online payments are not configured. Please choose Cash on Delivery.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            razorpay_order = client.order.create({
                'amount': amount_in_paise,
                'currency': 'INR',
                'notes': {
                    'user_id': str(user.id),
                    'user_email': user.email,
                }
            })
            return Response({
                'razorpay_order_id': razorpay_order['id'],
                'amount': razorpay_order['amount'],
                'currency': razorpay_order['currency'],
                'key_id': settings.RAZORPAY_KEY_ID,
                'total_amount': str(total_amount)
            })
        except Exception as e:
            print(f"Razorpay order create error: {e}")
            if settings.DEBUG:
                return Response({
                    'razorpay_order_id': f"order_sim_{int(timezone.now().timestamp())}",
                    'amount': amount_in_paise,
                    'currency': 'INR',
                    'key_id': '',
                    'total_amount': str(total_amount),
                    'simulated': True,
                })
            return Response(
                {'detail': 'Razorpay could not create the payment order. Please retry or choose Cash on Delivery.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def verify_razorpay_payment(self, request):
        user = request.user
        razorpay_payment_id = request.data.get('razorpay_payment_id', '')
        razorpay_order_id = request.data.get('razorpay_order_id', '')
        razorpay_signature = request.data.get('razorpay_signature', '')

        is_paid = False
        client = None
        if str(razorpay_order_id).startswith('order_sim_'):
            # Simulated orders are development-only. Never turn an unverified
            # client callback into a paid production order.
            is_paid = settings.DEBUG
        elif not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
            return Response(
                {'detail': 'Razorpay did not return all payment verification fields. Please retry or choose Cash on Delivery.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
            return Response(
                {'detail': 'Online payment verification is not configured. Please choose Cash on Delivery.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        else:
            try:
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                client.utility.verify_payment_signature({
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature,
                })
                is_paid = True
            except Exception as e:
                print(f"[Razorpay Signature Verification Error]: {e}")

        if not is_paid:
            return Response({'detail': 'Payment could not be verified with Razorpay.'}, status=status.HTTP_400_BAD_REQUEST)

        payment_reference = razorpay_payment_id or f"sim:{razorpay_order_id}"
        existing_order = Order.objects.filter(user=user, payment_reference=payment_reference).first()
        if existing_order:
            return Response(self.get_serializer(existing_order).data, status=status.HTTP_200_OK)

        cart_items = list(CartItem.objects.filter(user=user).select_related('product'))
        if not cart_items:
            return Response(
                {'detail': 'Your cart is empty. The payment was not turned into an order; please contact support.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon_code = request.data.get('coupon_code')
        item_total = sum(item.product.price * item.quantity for item in cart_items)
        discount_amount = Decimal('0.00')
        if coupon_code:
            coupon = Coupon.objects.filter(code__iexact=coupon_code, is_active=True).first()
            if coupon and item_total >= coupon.min_order_value:
                discount_amount = min(coupon.discount_amount, item_total)
        elif item_total > Decimal('2000.00'):
            discount_amount = Decimal('300.00')

        expected_amount_paise = int(max(Decimal('1.00'), item_total - discount_amount) * 100)
        if str(razorpay_order_id).startswith('order_sim_'):
            if not settings.DEBUG:
                return Response({'detail': 'Simulated payments are disabled.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                gateway_order = client.order.fetch(razorpay_order_id)
                gateway_payment = client.payment.fetch(razorpay_payment_id)
                if (
                    str((gateway_order.get('notes') or {}).get('user_id')) != str(user.id)
                    or int(gateway_order.get('amount', -1)) != expected_amount_paise
                    or gateway_order.get('currency') != 'INR'
                    or gateway_payment.get('order_id') != razorpay_order_id
                    or gateway_payment.get('status') not in ['authorized', 'captured']
                    or int(gateway_payment.get('amount', -1)) != expected_amount_paise
                    or gateway_payment.get('currency') != 'INR'
                ):
                    return Response(
                        {'detail': 'The captured payment does not match this account and current cart total.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if gateway_payment.get('status') == 'authorized':
                    gateway_payment = client.payment.capture(razorpay_payment_id, {
                        'amount': expected_amount_paise,
                        'currency': 'INR',
                    })
                if gateway_payment.get('status') != 'captured':
                    return Response(
                        {'detail': 'Payment is authorized but not captured yet. Retry verification in a few seconds.'},
                        status=status.HTTP_409_CONFLICT,
                    )
            except Exception as e:
                print(f"[Razorpay Payment/Order Verification Error]: {e}")
                return Response(
                    {'detail': 'Razorpay confirmed the checkout but could not finish capture/verification. Retry verification; do not pay again.'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        # Build order
        address_id = request.data.get('address_id')
        address_obj = Address.objects.filter(id=address_id, user=user).first() if address_id else None

        if address_obj:
            customer_name = address_obj.full_name
            phone = address_obj.phone
            delivery_address = f"{address_obj.address_line}, {address_obj.city} - {address_obj.postal_code}"
            address_type = address_obj.address_type
        else:
            customer_name = request.data.get('customer_name', getattr(user, 'full_name', 'Valued Customer'))
            phone = request.data.get('phone', getattr(user, 'phone', None) or '+91 9876543210')
            delivery_address = request.data.get('delivery_address', '12-3-456, MG Road, Bengaluru - 560001')
            address_type = request.data.get('address_type', 'Home')

        delivery_charges = Decimal('0.00')
        total_amount = max(Decimal('1.00'), item_total - discount_amount + delivery_charges)

        order = Order.objects.create(
            user=user,
            customer_name=customer_name,
            phone=phone,
            delivery_address=delivery_address,
            address_type=address_type,
            payment_method='Razorpay',
            payment_status='Paid',
            order_status='Order Placed',
            payment_reference=payment_reference,
            item_total=item_total,
            discount_amount=discount_amount,
            delivery_charges=delivery_charges,
            total_amount=total_amount,
            estimated_delivery='31 Oct - 03 Nov'
        )

        for ci in cart_items:
            img = ci.product.images.first()
            img_url = img.image_url if img else ''
            OrderItem.objects.create(
                order=order,
                product=ci.product,
                product_name=ci.product.name,
                price=ci.product.price,
                quantity=ci.quantity,
                size=ci.size,
                color=ci.color,
                image_url=img_url
            )

        # Initialize Tracking Record and 7 Milestones via Courier Provider
        courier_provider = get_courier_provider()
        courier_provider.create_shipment(order)

        # Clear cart
        CartItem.objects.filter(id__in=[item.id for item in cart_items]).delete()

        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def tracking(self, request, pk=None):
        """
        Retrieve tracking info and 7-stage milestones.
        Customers can only view their own orders; staff/admins can view any order.
        """
        order = self.get_object()
        if not request.user.is_staff and order.user != request.user:
            return Response(
                {'detail': 'You do not have permission to view tracking for this order.'},
                status=status.HTTP_403_FORBIDDEN
            )

        provider = get_courier_provider()
        if not hasattr(order, 'shipment') or not order.shipment:
            provider.create_shipment(order)
            order.refresh_from_db()

        tracking_data = provider.get_tracking_info(order.shipment.tracking_number)
        return Response(tracking_data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def update_status(self, request, pk=None):
        """
        Admin status update endpoint. Synchronizes Order and ShipmentTracking milestones.
        """
        order = self.get_object()
        new_status = request.data.get('status')
        location = request.data.get('location', '')
        note = request.data.get('note', '')

        if not new_status:
            return Response({'detail': 'status is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Mapping legacy status names if passed
        status_alias_map = {
            'Placed': 'Order Placed',
            'Shipped': 'In Transit',
        }
        mapped_status = status_alias_map.get(new_status, new_status)

        provider = get_courier_provider()
        if not hasattr(order, 'shipment') or not order.shipment:
            provider.create_shipment(order)
            order.refresh_from_db()

        try:
            shipment = provider.update_status(
                order.shipment.tracking_number,
                mapped_status,
                location=location,
                note=note
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        order.refresh_from_db()
        return Response({
            'message': f'Status updated to {mapped_status}',
            'order': self.get_serializer(order).data,
            'tracking': provider.get_tracking_info(shipment.tracking_number)
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def simulate_tracking(self, request, pk=None):
        """
        DEMO TRACKING Simulation endpoint.
        Allows authorized admin to simulate status changes with custom locations and notes.
        """
        return self.update_status(request, pk=pk)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reset_demo_tracking(self, request, pk=None):
        """
        Reset tracking to 'Order Placed' for demo purposes.
        """
        order = self.get_object()
        provider = get_courier_provider()
        if not hasattr(order, 'shipment') or not order.shipment:
            provider.create_shipment(order)
            order.refresh_from_db()

        shipment = provider.update_status(
            order.shipment.tracking_number,
            'Order Placed',
            location='Bengaluru Fulfillment Center',
            note='Simulation reset to Order Placed.'
        )
        order.refresh_from_db()
        return Response({
            'message': 'Demo tracking reset to Order Placed',
            'order': self.get_serializer(order).data,
            'tracking': provider.get_tracking_info(shipment.tracking_number)
        })


class ReturnRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ReturnRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        if self.request.user.is_staff:
            return ReturnRequest.objects.all().select_related('order', 'order_item')
        return ReturnRequest.objects.filter(order__user=self.request.user).select_related('order', 'order_item')

    def create(self, request, *args, **kwargs):
        order_id = request.data.get('order_id')
        order_item_id = request.data.get('order_item_id')
        reason = request.data.get('reason', 'Size does not fit')
        pickup_type = request.data.get('pickup_type', 'Pickup')

        order = Order.objects.filter(id=order_id, user=request.user).first()
        if not order:
            return Response({'detail': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        if order.order_status != 'Delivered':
            return Response({'detail': 'Returns can only be requested after delivery.'}, status=status.HTTP_400_BAD_REQUEST)
        delivered_at = order.updated_at
        try:
            delivered_event = order.shipment.milestones.filter(
                status_step='Delivered', is_completed=True
            ).first()
            if delivered_event and delivered_event.timestamp:
                delivered_at = delivered_event.timestamp
        except ShipmentTracking.DoesNotExist:
            pass
        if delivered_at < timezone.now() - timedelta(days=7):
            return Response({'detail': 'The 7-day return window for this order has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        order_item = OrderItem.objects.filter(id=order_item_id, order=order).first()
        if not order_item:
            # Fallback to first item if not provided
            order_item = order.items.first()
            if not order_item:
                return Response({'detail': 'Order item not found'}, status=status.HTTP_404_NOT_FOUND)

        if order_item.return_requests.exclude(status='Rejected').exists():
            return Response({'detail': 'A return has already been requested for this item.'}, status=status.HTTP_409_CONFLICT)

        item_subtotal = order_item.price * order_item.quantity
        item_discount = (
            (order.discount_amount * item_subtotal / order.item_total).quantize(Decimal('0.01'))
            if order.item_total > 0 else Decimal('0.00')
        )
        refund_amount = max(Decimal('0.00'), item_subtotal - item_discount)

        return_obj = ReturnRequest.objects.create(
            order=order,
            order_item=order_item,
            reason=reason,
            pickup_type=pickup_type,
            status='Initiated',
            refund_amount=refund_amount
        )
        serializer = self.get_serializer(return_obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    @transaction.atomic
    def update_status(self, request, pk=None):
        return_request = self.get_object()
        new_status = request.data.get('status')
        allowed = ['Pickup Scheduled', 'Pickup Received', 'Refund Processed', 'Rejected']
        if new_status not in allowed:
            return Response({'detail': f"Choose one of: {', '.join(allowed)}."}, status=status.HTTP_400_BAD_REQUEST)
        if return_request.status in ['Refund Processed', 'Rejected']:
            return Response({'detail': 'This return request is already closed.'}, status=status.HTTP_409_CONFLICT)
        if new_status == 'Pickup Scheduled' and return_request.status != 'Initiated':
            return Response({'detail': 'Pickup can only be scheduled for a newly initiated return.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_status == 'Pickup Received' and not (
            return_request.status == 'Pickup Scheduled'
            or (return_request.status == 'Initiated' and return_request.pickup_type.lower().startswith('drop'))
        ):
            return Response({'detail': 'Confirm receipt only after a pickup is scheduled or a drop-off is received.'}, status=status.HTTP_400_BAD_REQUEST)

        order = return_request.order
        if new_status == 'Refund Processed' and order.payment_method == 'Razorpay':
            if return_request.status != 'Pickup Received':
                return Response({'detail': 'Confirm receipt of the returned item before issuing the refund.'}, status=status.HTTP_400_BAD_REQUEST)
            if not order.payment_reference:
                return Response({'detail': 'No captured Razorpay payment is linked to this order.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                client.payment.refund(order.payment_reference, {
                    'amount': int(return_request.refund_amount * 100),
                    'notes': {'return_request_id': str(return_request.id)},
                })
            except Exception as e:
                print(f"[Razorpay Refund Error]: {e}")
                return Response({'detail': 'Razorpay could not process the refund. The request remains open.'}, status=status.HTTP_502_BAD_GATEWAY)
        elif new_status == 'Refund Processed' and order.payment_method in ['Cash on Delivery', 'COD']:
            if return_request.status != 'Pickup Received':
                return Response({'detail': 'Confirm receipt of the returned item before confirming the refund.'}, status=status.HTTP_400_BAD_REQUEST)
            if request.data.get('manual_refund_confirmed') is not True:
                return Response(
                    {'detail': 'Transfer the COD refund manually, then confirm manual_refund_confirmed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return_request.status = new_status
        return_request.save(update_fields=['status'])
        if new_status == 'Refund Processed':
            refunded = sum(
                (r.refund_amount for r in order.returns.filter(status='Refund Processed')),
                Decimal('0.00'),
            )
            order.payment_status = 'Refunded' if refunded >= (order.item_total - order.discount_amount) else 'Partially Refunded'
            order.save(update_fields=['payment_status', 'updated_at'])
        return Response(self.get_serializer(return_request).data)
