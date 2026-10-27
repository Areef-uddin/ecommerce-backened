from rest_framework import serializers
from .models import CartItem, Coupon, Order, OrderItem, OrderTimeline, ReturnRequest
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


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    timeline = OrderTimelineSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'user', 'customer_name', 'phone', 'delivery_address',
            'address_type', 'payment_method', 'payment_status', 'order_status',
            'item_total', 'discount_amount', 'delivery_charges', 'total_amount',
            'delivery_partner_name', 'delivery_partner_phone', 'delivery_partner_rating',
            'delivery_partner_vehicle', 'estimated_delivery', 'created_at', 'updated_at',
            'items', 'timeline'
        )
        read_only_fields = ('id', 'order_number', 'user', 'created_at', 'updated_at')


class ReturnRequestSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='order_item.product_name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model = ReturnRequest
        fields = ('id', 'order', 'order_number', 'order_item', 'product_name', 'reason', 'pickup_type', 'status', 'refund_amount', 'created_at')
        read_only_fields = ('id', 'created_at')
