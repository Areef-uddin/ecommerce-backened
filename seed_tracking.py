import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import User
from orders.models import Order, OrderItem, ShipmentTracking
from orders.courier import get_courier_provider
from products.models import Product

def seed_tracking_data():
    print("[*] Initializing Dummy Courier Tracking System data...")
    provider = get_courier_provider()

    # 1. Ensure test customer exists
    customer, _ = User.objects.get_or_create(
        email='customer@stylehub.com',
        defaults={
            'first_name': 'Priya',
            'last_name': 'Sharma',
            'phone': '+919876543210',
            'avatar': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400'
        }
    )
    customer.set_password('password123')
    customer.save()

    # 2. Find or create a test product
    product = Product.objects.first()

    # 3. Process existing orders first
    existing_orders = Order.objects.all()
    print(f"[*] Found {existing_orders.count()} existing orders in database.")
    for ord in existing_orders:
        shipment = provider.create_shipment(ord)
        print(f"  [+] Order #{ord.order_number} linked to tracking {shipment.tracking_number} (status: {shipment.current_status})")

    # 4. Ensure customer@stylehub.com has at least 2 distinct realistic orders for demoing
    customer_orders = Order.objects.filter(user=customer)
    if customer_orders.count() < 2:
        print("[*] Creating dedicated demo order for customer@stylehub.com...")
        test_order_1 = Order.objects.create(
            user=customer,
            customer_name='Priya Sharma',
            phone='+91 9876543210',
            delivery_address='Flat 402, Green Glen Layout, Bellandur, Bengaluru - 560103',
            address_type='Home',
            payment_method='UPI',
            payment_status='Paid',
            order_status='In Transit', # Requirement 12: Not marked Delivered!
            item_total=2499.00,
            discount_amount=300.00,
            delivery_charges=0.00,
            total_amount=2199.00,
            delivery_partner_name='Vikram Singh (Demo Agent)',
            delivery_partner_phone='+91 9811223344',
            delivery_partner_rating=4.9,
            delivery_partner_vehicle='KA-03-TR-8821',
            estimated_delivery='Tomorrow, by 7 PM'
        )

        if product:
            OrderItem.objects.create(
                order=test_order_1,
                product=product,
                product_name=product.name,
                price=product.price,
                quantity=1,
                size='M',
                color='Pink',
                image_url=product.images.first().image_url if product.images.exists() else ''
            )

        shipment1 = provider.create_shipment(test_order_1)
        # Advance to In Transit for demo demonstration
        provider.update_status(
            shipment1.tracking_number,
            'In Transit',
            location='Bengaluru Central Logistics Sorting Hub',
            note='Parcel has departed regional sorting facility and is en-route to local delivery hub.'
        )
        print(f"  [+] Created demo Order #{test_order_1.order_number} -> Tracking: {shipment1.tracking_number} (Status: In Transit)")

        # Create second order in 'Confirmed' state
        test_order_2 = Order.objects.create(
            user=customer,
            customer_name='Priya Sharma',
            phone='+91 9876543210',
            delivery_address='Office Unit 7, Tech Park, Outer Ring Road, Bengaluru - 560103',
            address_type='Office',
            payment_method='Credit / Debit Card',
            payment_status='Paid',
            order_status='Confirmed',
            item_total=1899.00,
            discount_amount=0.00,
            delivery_charges=0.00,
            total_amount=1899.00,
            delivery_partner_name='Rahul Kumar (Demo Partner)',
            delivery_partner_phone='+91 9876543210',
            delivery_partner_rating=4.8,
            delivery_partner_vehicle='KA-01-EXP-2024',
            estimated_delivery='3-4 Business Days'
        )

        if product:
            OrderItem.objects.create(
                order=test_order_2,
                product=product,
                product_name=product.name,
                price=product.price,
                quantity=1,
                size='S',
                color='Black',
                image_url=product.images.first().image_url if product.images.exists() else ''
            )

        shipment2 = provider.create_shipment(test_order_2)
        provider.update_status(
            shipment2.tracking_number,
            'Confirmed',
            location='Bengaluru Fulfillment Center',
            note='Order payment verified and items queued for warehouse packing.'
        )
        print(f"  [+] Created demo Order #{test_order_2.order_number} -> Tracking: {shipment2.tracking_number} (Status: Confirmed)")

    print("[SUCCESS] Dummy Courier Tracking System initialized with test tracking records!")

if __name__ == '__main__':
    seed_tracking_data()
