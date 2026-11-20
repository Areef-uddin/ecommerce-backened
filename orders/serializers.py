from rest_framework import serializers
from datetime import timedelta
from django.utils import timezone
from .models import CartItem, Coupon, Order, OrderItem, OrderTimeline, ReturnRequest, ReturnTimeline, ShipmentTracking, TrackingMilestone
from products.serializers import ProductListSerializer

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'product_id', 'quantity', 'size', 'color', 'total_price', 'created_at')
        read_only_fields = ('id', 'created_at')


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'price', 'quantity', 'size', 'color', 'image_url')


class OrderTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTimeline
        fields = ('id', 'status_step', 'date_text', 'is_completed', 'order_index')


class TrackingMilestoneSerializer(serializers.ModelSerializer):
    date_formatted = serializers.SerializerMethodField()

    class Meta:
        model = TrackingMilestone
        fields = ('id', 'status_step', 'title', 'location', 'description', 'timestamp', 'date_formatted', 'is_completed', 'order_index')

    def get_date_formatted(self, obj):
        if obj.timestamp:
            return obj.timestamp.strftime("%d %b, %I:%M %p")
        return "Expected"


class ShipmentTrackingSerializer(serializers.ModelSerializer):
    milestones = TrackingMilestoneSerializer(many=True, read_only=True)
    delivery_partner = serializers.SerializerMethodField()
    courier_name = serializers.SerializerMethodField()
    estimated_delivery = serializers.SerializerMethodField()
    is_demo_mode = serializers.SerializerMethodField()

    class Meta:
        model = ShipmentTracking
        fields = (
            'id', 'tracking_number', 'courier_name', 'is_demo_mode',
            'current_status', 'current_location', 'estimated_delivery',
            'delivery_partner', 'milestones', 'created_at', 'updated_at'
        )

    def get_courier_name(self, obj):
        name = obj.courier_name or 'StyleHub Express'
        return name.replace('(Demo Logistics)', '').replace('(Demo)', '').strip()

    def get_is_demo_mode(self, obj):
        return False

    def get_estimated_delivery(self, obj):
        if obj.estimated_delivery and obj.estimated_delivery != '31 Oct - 03 Nov':
            return obj.estimated_delivery
        from orders.models import compute_estimated_delivery
        order_dt = obj.order.created_at if hasattr(obj, 'order') and obj.order else None
        return compute_estimated_delivery(order_dt)

    def get_delivery_partner(self, obj):
        return {
            'name': (obj.delivery_person_name or 'Rahul Kumar').replace('(Demo Partner)', '').strip(),
            'phone': obj.delivery_person_phone or '+91 9876543210',
            'rating': float(obj.delivery_partner_rating or 4.8),
            'vehicle': obj.delivery_vehicle_number or 'KA-01-SH-4421',
        }


class ReturnTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnTimeline
        fields = ('id', 'status', 'note', 'created_at')


class ReturnRequestSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='order_item.product_name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer_name', read_only=True)
    payment_method = serializers.CharField(source='order.payment_method', read_only=True)
    timeline = ReturnTimelineSerializer(many=True, read_only=True)

    class Meta:
        model = ReturnRequest
        fields = ('id', 'order', 'order_number', 'customer_name', 'payment_method', 'order_item', 'product_name', 'reason', 'pickup_type', 'status', 'refund_amount', 'created_at', 'timeline')
        read_only_fields = ('id', 'created_at', 'status', 'refund_amount')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = OrderTimelineSerializer(many=True, read_only=True)
    returns = ReturnRequestSerializer(many=True, read_only=True)
    return_eligible = serializers.SerializerMethodField()
    return_window_ends_at = serializers.SerializerMethodField()

    def _return_deadline(self, obj):
        delivered_at = obj.updated_at
        try:
            delivered_milestone = obj.shipment.milestones.filter(
                status_step='Delivered', is_completed=True,
            ).first()
            if delivered_milestone and delivered_milestone.timestamp:
                delivered_at = delivered_milestone.timestamp
        except Exception:
            pass
        return delivered_at + timedelta(days=7)

    def get_return_eligible(self, obj):
        return obj.order_status == 'Delivered' and self._return_deadline(obj) >= timezone.now()

    def get_return_window_ends_at(self, obj):
        if obj.order_status != 'Delivered':
            return None
        return self._return_deadline(obj)
    tracking_number = serializers.ReadOnlyField()
    shipment = ShipmentTrackingSerializer(read_only=True)
    estimated_delivery = serializers.SerializerMethodField()

    def get_estimated_delivery(self, obj):
        if obj.estimated_delivery and obj.estimated_delivery != '31 Oct - 03 Nov':
            return obj.estimated_delivery
        from orders.models import compute_estimated_delivery
        return compute_estimated_delivery(obj.created_at)

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'tracking_number', 'user', 'customer_name', 'phone', 'delivery_address',
            'address_type', 'payment_method', 'payment_status', 'order_status',
            'item_total', 'discount_amount', 'delivery_charges', 'total_amount',
            'delivery_partner_name', 'delivery_partner_phone', 'delivery_partner_rating',
            'delivery_partner_vehicle', 'estimated_delivery', 'created_at', 'updated_at',
            'items', 'timeline', 'shipment', 'returns', 'return_eligible', 'return_window_ends_at'
        )
        read_only_fields = ('id', 'order_number', 'tracking_number', 'user', 'created_at', 'updated_at')
