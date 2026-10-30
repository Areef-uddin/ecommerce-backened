from django.db import models
from django.conf import settings
from products.models import Product
import random
import string

def generate_order_number():
    random_str = ''.join(random.choices(string.digits, k=8))
    return f"#SH{random_str}"

class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=20, default='M')
    color = models.CharField(max_length=50, default='Pink')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product', 'size', 'color')

    def __str__(self):
        return f"{self.user.email} - {self.product.name} ({self.quantity})"

    @property
    def total_price(self):
        return self.product.price * self.quantity


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.PositiveIntegerField(default=10)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=300.00)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=999.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class Order(models.Model):
    STATUS_CHOICES = (
        ('Order Placed', 'Order Placed'),
        ('Placed', 'Placed'),
        ('Confirmed', 'Confirmed'),
        ('Packed', 'Packed'),
        ('Picked Up', 'Picked Up'),
        ('In Transit', 'In Transit'),
        ('Shipped', 'Shipped'),
        ('Out for Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    )

    PAYMENT_CHOICES = (
        ('UPI', 'UPI'),
        ('Credit / Debit Card', 'Credit / Debit Card'),
        ('Net Banking', 'Net Banking'),
        ('Wallet', 'Wallet'),
        ('Cash on Delivery', 'Cash on Delivery'),
    )

    order_number = models.CharField(max_length=30, unique=True, default=generate_order_number)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    
    # Address details snapshotted at time of order
    customer_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    delivery_address = models.TextField()
    address_type = models.CharField(max_length=20, default='Home')

    # Payment
    payment_method = models.CharField(max_length=50, choices=PAYMENT_CHOICES, default='UPI')
    payment_status = models.CharField(max_length=20, default='Paid')
    payment_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)

    # Status
    order_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Placed')

    # Pricing
    item_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Tracking & Delivery partner
    delivery_partner_name = models.CharField(max_length=100, default='Rahul Kumar')
    delivery_partner_phone = models.CharField(max_length=20, default='+91 9876543210')
    delivery_partner_rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.8)
    delivery_partner_vehicle = models.CharField(max_length=30, default='TB1234')
    estimated_delivery = models.CharField(max_length=100, default='31 Oct - 03 Nov')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.user.email} ({self.order_status})"

    @property
    def tracking_number(self):
        try:
            if hasattr(self, 'shipment') and self.shipment:
                return self.shipment.tracking_number
        except Exception:
            pass
        return f"TEST-FASH-{1000 + self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=20, default='M')
    color = models.CharField(max_length=50, default='Pink')
    image_url = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.product_name} x {self.quantity}"


class OrderTimeline(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='timeline')
    status_step = models.CharField(max_length=50) # 'Order Placed', 'Packed', 'Shipped', 'Out for Delivery', 'Delivered'
    date_text = models.CharField(max_length=100, blank=True)
    is_completed = models.BooleanField(default=False)
    order_index = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order_index']

    def __str__(self):
        return f"{self.order.order_number} - {self.status_step}"


class ReturnRequest(models.Model):
    STATUS_CHOICES = (
        ('Initiated', 'Initiated'),
        ('Pickup Scheduled', 'Pickup Scheduled'),
        ('Pickup Received', 'Pickup Received'),
        ('Refund Processed', 'Refund Processed'),
        ('Rejected', 'Rejected'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='returns')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='return_requests')
    reason = models.CharField(max_length=200)
    pickup_type = models.CharField(max_length=20, default='Pickup')  # Pickup or Drop
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Initiated')
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return for {self.order.order_number} - {self.order_item.product_name}"


TRACKING_STAGES_CONFIG = [
    {
        'status': 'Order Placed',
        'title': 'Order Placed',
        'description': 'Your order has been received and verified.',
        'location': 'Bengaluru Fulfillment Center',
        'order_index': 0,
    },
    {
        'status': 'Confirmed',
        'title': 'Order Confirmed',
        'description': 'Payment verified and items allocated in warehouse.',
        'location': 'Bengaluru Fulfillment Center',
        'order_index': 1,
    },
    {
        'status': 'Packed',
        'title': 'Packed at Warehouse',
        'description': 'Item packaged, labeled, and quality-inspected.',
        'location': 'Warehouse Sort Facility, Whitefield',
        'order_index': 2,
    },
    {
        'status': 'Picked Up',
        'title': 'Picked Up by Courier',
        'description': 'Courier logistics partner picked up the package.',
        'location': 'Bengaluru Logistics Hub',
        'order_index': 3,
    },
    {
        'status': 'In Transit',
        'title': 'In Transit to Hub',
        'description': 'Package in transit towards recipient destination city.',
        'location': 'Regional Sorting Facility',
        'order_index': 4,
    },
    {
        'status': 'Out for Delivery',
        'title': 'Out for Delivery',
        'description': 'Delivery executive is out for delivery to your address.',
        'location': 'Local Delivery Hub',
        'order_index': 5,
    },
    {
        'status': 'Delivered',
        'title': 'Delivered Successfully',
        'description': 'Package delivered to recipient. Thank you for shopping with us!',
        'location': 'Customer Delivery Address',
        'order_index': 6,
    },
]


class ShipmentTracking(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipment')
    tracking_number = models.CharField(max_length=50, unique=True, db_index=True)
    courier_name = models.CharField(max_length=100, default='StyleHub Express (Demo Logistics)')
    is_demo_mode = models.BooleanField(default=True)
    current_status = models.CharField(max_length=50, default='Order Placed')
    current_location = models.CharField(max_length=200, default='Bengaluru Fulfillment Center')
    estimated_delivery = models.CharField(max_length=100, default='31 Oct - 03 Nov')

    delivery_person_name = models.CharField(max_length=100, default='Rahul Kumar (Demo Partner)')
    delivery_person_phone = models.CharField(max_length=20, default='+91 9876543210')
    delivery_partner_rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.8)
    delivery_vehicle_number = models.CharField(max_length=30, default='KA-01-EXP-2024')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tracking_number} -> {self.order.order_number} ({self.current_status})"


class TrackingMilestone(models.Model):
    shipment = models.ForeignKey(ShipmentTracking, on_delete=models.CASCADE, related_name='milestones')
    status_step = models.CharField(max_length=50)  # One of the 7 stages
    title = models.CharField(max_length=100)
    location = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)
    order_index = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order_index']

    def __str__(self):
        return f"{self.shipment.tracking_number} - Step {self.order_index}: {self.status_step} ({'Done' if self.is_completed else 'Pending'})"
