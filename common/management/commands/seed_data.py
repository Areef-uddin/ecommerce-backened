import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, Address
from products.models import (
    Category, SubCategory, Product, ProductImage,
    ProductColor, ProductSize, SizeGuide, Wishlist
)
from orders.models import CartItem, Coupon, Order, OrderItem, OrderTimeline, ReturnRequest
from common.models import (
    Banner,
    Notification,
    FAQ,
    StoreSetting,
    FooterSection,
    FooterLink,
    PolicyPage,
    NewsletterSubscriber,
)

class Command(BaseCommand):
    help = 'Populate database with rich fashion e-commerce data matching StyleHub screens'

    def handle(self, *args, **options):
        self.stdout.write('Seeding StyleHub database...')

        # 1. Superuser / Admin User
        admin_user = User.objects.filter(email='admin@stylehub.com').first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                email='admin@stylehub.com',
                password='adminpassword',
                first_name='Admin',
                last_name='StyleHub'
            )
            self.stdout.write(self.style.SUCCESS('Admin created: admin@stylehub.com / adminpassword'))
        else:
            admin_user.set_password('adminpassword')
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()

        # 2. Customer User
        customer = User.objects.filter(email='areef@example.com').first() or User.objects.filter(phone='+919876543210').first()
        if not customer:
            customer = User.objects.create_user(
                email='areef@example.com',
                phone='+919876543210',
                password='password123',
                first_name='Areefuddin',
                last_name='',
                avatar='https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400'
            )
            self.stdout.write(self.style.SUCCESS('Customer created: areef@example.com / password123'))
        else:
            customer.set_password('password123')
            customer.first_name = 'Areefuddin'
            customer.save()

        # 3. Addresses
        Address.objects.filter(user=customer).delete()
        addr_home = Address.objects.create(
            user=customer,
            full_name='Areefuddin',
            phone='+91 9876543210',
            address_line='12-3-456, MG Road',
            city='Bengaluru',
            state='Karnataka',
            postal_code='560001',
            address_type='Home',
            is_default=True
        )
        addr_office = Address.objects.create(
            user=customer,
            full_name='Areefuddin',
            phone='+91 9876543210',
            address_line='45, Koramangala',
            city='Bengaluru',
            state='Karnataka',
            postal_code='560034',
            address_type='Office',
            is_default=False
        )
        self.stdout.write('Addresses created.')

        # 4. Categories & Subcategories
        categories_data = [
            {
                'name': 'Women',
                'slug': 'women',
                'image_url': 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=300',
                'icon': 'female',
                'order': 1,
                'subs': [
                    ('Dresses', 'dresses', 'https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=400', 200),
                    ('Tops', 'tops', 'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=400', 150),
                    ('Bottoms', 'bottoms', 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=400', 120),
                    ('Ethnic Wear', 'ethnic-wear', 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=400', 160),
                    ('Active Wear', 'active-wear', 'https://images.unsplash.com/photo-1518611012118-696072aa579a?w=400', 90),
                    ('Co-ord Sets', 'co-ord-sets', 'https://images.unsplash.com/photo-1509631179647-0177331693ae?w=400', 110),
                ]
            },
            {
                'name': 'Men',
                'slug': 'men',
                'image_url': 'https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=300',
                'icon': 'male',
                'order': 2,
                'subs': [
                    ('T-Shirts', 't-shirts', 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=400', 180),
                    ('Shirts', 'shirts', 'https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=400', 140),
                    ('Jeans', 'men-jeans', 'https://images.unsplash.com/photo-1542272604-780c96856592?w=400', 95),
                ]
            },
            {
                'name': 'Kids',
                'slug': 'kids',
                'image_url': 'https://images.unsplash.com/photo-1503919545889-aef636e10ad4?w=300',
                'icon': 'child',
                'order': 3,
                'subs': [
                    ('Girls Clothing', 'girls', 'https://images.unsplash.com/photo-1622290291468-a28f7a7dc6a8?w=400', 120),
                    ('Boys Clothing', 'boys', 'https://images.unsplash.com/photo-1519457431-44ccd64a579b?w=400', 110),
                ]
            },
            {
                'name': 'Shoes',
                'slug': 'shoes',
                'image_url': 'https://images.unsplash.com/photo-1549298916-b41d501d3772?w=300',
                'icon': 'shoe',
                'order': 4,
                'subs': [
                    ('Sneakers', 'sneakers', 'https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=400', 80),
                    ('Heels', 'heels', 'https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=400', 60),
                ]
            },
            {
                'name': 'Bags',
                'slug': 'bags',
                'image_url': 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=300',
                'icon': 'briefcase',
                'order': 5,
                'subs': [
                    ('Handbags', 'handbags', 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=400', 90),
                    ('Totes', 'totes', 'https://images.unsplash.com/photo-1544816155-12df9643f363?w=400', 45),
                ]
            },
            {
                'name': 'Accessories',
                'slug': 'accessories',
                'image_url': 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=300',
                'icon': 'watch',
                'order': 6,
                'subs': [
                    ('Watches', 'watches', 'https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=400', 70),
                    ('Jewellery', 'jewellery', 'https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400', 130),
                ]
            },
        ]

        for cat_info in categories_data:
            cat, _ = Category.objects.update_or_create(
                slug=cat_info['slug'],
                defaults={
                    'name': cat_info['name'],
                    'image_url': cat_info['image_url'],
                    'icon': cat_info['icon'],
                    'display_order': cat_info['order'],
                    'is_active': True,
                }
            )
            for sub_name, sub_slug, sub_img, item_count in cat_info['subs']:
                SubCategory.objects.update_or_create(
                    category=cat,
                    slug=sub_slug,
                    defaults={
                        'name': sub_name,
                        'image_url': sub_img,
                        'item_count': item_count,
                    }
                )

        women_cat = Category.objects.get(slug='women')
        dresses_sub = SubCategory.objects.get(category=women_cat, slug='dresses')
        shoes_cat = Category.objects.get(slug='shoes')
        sneakers_sub = SubCategory.objects.get(category=shoes_cat, slug='sneakers')
        bags_cat = Category.objects.get(slug='bags')
        handbags_sub = SubCategory.objects.get(category=bags_cat, slug='handbags')
        acc_cat = Category.objects.get(slug='accessories')
        watches_sub = SubCategory.objects.get(category=acc_cat, slug='watches')

        # 5. Products Matching StyleHub Screens
        products_data = [
            {
                'name': 'Floral Maxi Dress',
                'slug': 'floral-maxi-dress',
                'category': women_cat,
                'subcategory': dresses_sub,
                'price': 1299.00,
                'original_price': 2499.00,
                'rating': 4.5,
                'review_count': 1200,
                'is_trending': True,
                'is_new_arrival': True,
                'description': 'Elevate your wardrobe with this enchanting floral maxi dress. Crafted from breathable, lightweight georgette fabric with a flattering A-line silhouette, V-neckline, and subtle waist tie-up. Perfect for beach vacations, weekend brunches, or evening outings.',
                'images': [
                    ('https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=800', True),
                    ('https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800', False),
                    ('https://images.unsplash.com/photo-1496747611176-843222e1e57c?w=800', False),
                ],
                'colors': [('Pink', '#F8BBD0'), ('Peach', '#FFCCBC'), ('White', '#FFFFFF'), ('Black', '#212121')],
                'sizes': ['XS', 'S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Bodycon Dress',
                'slug': 'bodycon-dress',
                'category': women_cat,
                'subcategory': dresses_sub,
                'price': 999.00,
                'original_price': 1999.00,
                'rating': 4.3,
                'review_count': 980,
                'is_trending': True,
                'is_new_arrival': False,
                'description': 'Sleek and figure-sculpting black bodycon dress made with premium ribbed stretch knit. Features a square neckline and midi cut that transitions effortlessly from day to night.',
                'images': [
                    ('https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=800', True),
                    ('https://images.unsplash.com/photo-1509631179647-0177331693ae?w=800', False),
                ],
                'colors': [('Black', '#111111'), ('Wine Red', '#880E4F'), ('Navy Blue', '#1A237E')],
                'sizes': ['XS', 'S', 'M', 'L'],
            },
            {
                'name': 'Red Evening Dress',
                'slug': 'red-evening-dress',
                'category': women_cat,
                'subcategory': dresses_sub,
                'price': 1499.00,
                'original_price': 2999.00,
                'rating': 4.6,
                'review_count': 850,
                'is_trending': True,
                'is_new_arrival': True,
                'description': 'Make a striking entrance with this glamorous crimson red evening dress. Designed with a fitted bodice, side slit, and flowing drape that turns heads at any cocktail party or gala.',
                'images': [
                    ('https://images.unsplash.com/photo-1568252542512-9fe8fe9c87bb?w=800', True),
                ],
                'colors': [('Crimson Red', '#D32F2F'), ('Rose Gold', '#B76E79')],
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'White Classic Sneakers',
                'slug': 'white-classic-sneakers',
                'category': shoes_cat,
                'subcategory': sneakers_sub,
                'price': 1999.00,
                'original_price': 3499.00,
                'rating': 4.7,
                'review_count': 1520,
                'is_trending': True,
                'is_new_arrival': False,
                'description': 'Timeless everyday white sneakers crafted with premium vegan leather and cushioned memory foam insole. High-grip rubber cupsole ensures all-day comfort and stability.',
                'images': [
                    ('https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=800', True),
                    ('https://images.unsplash.com/photo-1549298916-b41d501d3772?w=800', False),
                ],
                'colors': [('All White', '#FFFFFF'), ('White/Green', '#E8F5E9')],
                'sizes': ['6', '7', '8', '9', '10'],
            },
            {
                'name': 'Black Luxury Handbag',
                'slug': 'black-luxury-handbag',
                'category': bags_cat,
                'subcategory': handbags_sub,
                'price': 2299.00,
                'original_price': 3999.00,
                'rating': 4.4,
                'review_count': 620,
                'is_trending': True,
                'is_new_arrival': False,
                'description': 'Structured tote handbag crafted in textured faux leather with gold-tone hardware. Includes twin grab handles, detachable shoulder strap, and multiple zipper compartments.',
                'images': [
                    ('https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=800', True),
                ],
                'colors': [('Jet Black', '#1A1A1A'), ('Tan Brown', '#8D6E63')],
                'sizes': ['One Size'],
            },
            {
                'name': 'Rose Gold Minimalist Watch',
                'slug': 'rose-gold-minimalist-watch',
                'category': acc_cat,
                'subcategory': watches_sub,
                'price': 1999.00,
                'original_price': 3999.00,
                'rating': 4.6,
                'review_count': 410,
                'is_trending': False,
                'is_new_arrival': True,
                'description': 'Sophisticated rose gold wristwatch featuring an ultra-slim stainless steel mesh strap, scratch-resistant mineral glass, and Japanese quartz movement.',
                'images': [
                    ('https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=800', True),
                ],
                'colors': [('Rose Gold', '#B76E79'), ('Silver', '#C0C0C0')],
                'sizes': ['Standard'],
            },
        ]

        for p_info in products_data:
            prod, created = Product.objects.update_or_create(
                slug=p_info['slug'],
                defaults={
                    'name': p_info['name'],
                    'category': p_info['category'],
                    'subcategory': p_info['subcategory'],
                    'price': p_info['price'],
                    'original_price': p_info['original_price'],
                    'rating': p_info['rating'],
                    'review_count': p_info['review_count'],
                    'is_trending': p_info['is_trending'],
                    'is_new_arrival': p_info['is_new_arrival'],
                    'description': p_info['description'],
                    'in_stock': True,
                    'stock_quantity': 45,
                }
            )

            ProductImage.objects.filter(product=prod).delete()
            for img_url, is_prim in p_info['images']:
                ProductImage.objects.create(product=prod, image_url=img_url, is_primary=is_prim)

            ProductColor.objects.filter(product=prod).delete()
            for c_name, c_hex in p_info['colors']:
                ProductColor.objects.create(product=prod, name=c_name, hex_code=c_hex)

            ProductSize.objects.filter(product=prod).delete()
            for sz in p_info['sizes']:
                ProductSize.objects.create(product=prod, size=sz)

        self.stdout.write('Products seeded successfully.')

        # 6. Size Guide Data matching Screen 9
        SizeGuide.objects.all().delete()
        size_data = [
            ('Women', 'XS', '32', '24', '34', '81', '61', '86'),
            ('Women', 'S', '34', '26', '36', '86', '66', '91'),
            ('Women', 'M', '36', '28', '38', '91', '71', '96'),
            ('Women', 'L', '38', '30', '40', '96', '76', '101'),
            ('Women', 'XL', '40', '32', '42', '101', '81', '106'),
            ('Men', 'S', '38', '30', '38', '96', '76', '96'),
            ('Men', 'M', '40', '32', '40', '101', '81', '101'),
            ('Men', 'L', '42', '34', '42', '106', '86', '106'),
            ('Men', 'XL', '44', '36', '44', '111', '91', '111'),
        ]
        for c_type, sz, b_in, w_in, h_in, b_cm, w_cm, h_cm in size_data:
            SizeGuide.objects.create(
                category_type=c_type,
                size=sz,
                bust_in=b_in,
                waist_in=w_in,
                hip_in=h_in,
                bust_cm=b_cm,
                waist_cm=w_cm,
                hip_cm=h_cm,
            )
        self.stdout.write('Size guide seeded.')

        # 7. Carousel Banners matching Screen 5
        Banner.objects.all().delete()
        Banner.objects.create(
            title='New Season New Styles',
            subtitle='Discover latest trends curated for you',
            badge='New Season',
            discount_text='UP TO 50% OFF',
            image_url='https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=800',
            category_slug='women',
            display_order=1
        )
        Banner.objects.create(
            title='Festive Glamour',
            subtitle='Elevate your festive look with chic ethnic wear',
            badge='Trending',
            discount_text='FLAT 40% OFF',
            image_url='https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=800',
            category_slug='women',
            display_order=2
        )

        # 8. Coupons
        Coupon.objects.update_or_create(
            code='STYLE300',
            defaults={
                'discount_percent': 10,
                'discount_amount': 300.00,
                'min_order_value': 999.00,
                'is_active': True,
            }
        )

        # 9. Wishlist items for Customer (Screen 18)
        Wishlist.objects.filter(user=customer).delete()
        for p_slug in ['red-evening-dress', 'black-luxury-handbag', 'rose-gold-minimalist-watch', 'white-classic-sneakers']:
            p = Product.objects.filter(slug=p_slug).first()
            if p:
                Wishlist.objects.create(user=customer, product=p)

        # 10. Notifications (Screen 21)
        Notification.objects.filter(user=customer).delete()
        notifs = [
            ('Order Shipped', 'Your order #SH12345678 has been shipped.', 'orders', 'shopping-bag'),
            ('Special Offer', 'Get 40% OFF on all dresses! Use code STYLE300.', 'offers', 'tag'),
            ('Order Delivered', 'Your order has been delivered successfully.', 'orders', 'check-circle'),
            ('New Arrivals', 'Check out latest winter collection now in store.', 'updates', 'sparkles'),
            ('Price Drop Alert', 'Items in your wishlist are now on sale!', 'offers', 'bell'),
        ]
        for title, msg, cat, icon in notifs:
            Notification.objects.create(user=customer, title=title, message=msg, category=cat, icon=icon)

        # 11. FAQs (Screen 20)
        FAQ.objects.all().delete()
        faqs = [
            ('Track My Order', 'How can I track my active order?', 'Navigate to the Orders tab in your profile or click Track Order on any active order to view live timeline status and delivery partner details.', 'truck', 1),
            ('Returns & Refunds', 'What is your return policy?', 'You can initiate a return within 7 days of delivery. Once verified, our delivery partner will pick up the item and your refund will be processed in 3-5 days.', 'rotate-ccw', 2),
            ('Payment Issues', 'Which payment methods are supported?', 'We support UPI (GPay, PhonePe, Paytm), Credit & Debit cards (Visa, Mastercard, RuPay), Net Banking, and Cash on Delivery.', 'credit-card', 3),
            ('Product Information', 'How do I choose the right size?', 'Click the Size Guide button on any product detail page to compare body measurements in both inches and centimeters with illustrations.', 'info', 4),
            ('Account & Profile', 'How do I change my delivery address?', 'Go to Profile -> My Addresses where you can add new addresses or set your default home/office address.', 'user', 5),
            ('Shipping & Delivery', 'How long does delivery take?', 'Standard delivery takes 2 to 4 business days. You will receive live status updates via SMS and in-app notifications.', 'package', 6),
        ]
        for cat, q, a, icon, order in faqs:
            FAQ.objects.create(category=cat, question=q, answer=a, icon=icon, display_order=order)

        # 12. Sample Past Orders for Customer (Screens 13, 14, 15, 16)
        Order.objects.filter(user=customer).delete()
        floral_dress = Product.objects.get(slug='floral-maxi-dress')
        white_sneakers = Product.objects.get(slug='white-classic-sneakers')
        black_bag = Product.objects.get(slug='black-luxury-handbag')

        # Active Shipped Order
        order1 = Order.objects.create(
            order_number='#SH12345678',
            user=customer,
            customer_name='Areefuddin',
            phone='+91 9876543210',
            delivery_address='12-3-456, MG Road, Bengaluru - 560001',
            address_type='Home',
            payment_method='UPI',
            payment_status='Paid',
            order_status='Shipped',
            item_total=3298.00,
            discount_amount=300.00,
            delivery_charges=0.00,
            total_amount=2998.00,
            delivery_partner_name='Rahul Kumar',
            delivery_partner_phone='+91 9876543210',
            delivery_partner_rating=4.8,
            delivery_partner_vehicle='TB1234',
            estimated_delivery='31 Oct - 03 Nov'
        )
        OrderItem.objects.create(
            order=order1,
            product=floral_dress,
            product_name='Floral Maxi Dress',
            price=1299.00,
            quantity=1,
            size='M',
            color='Pink',
            image_url=floral_dress.images.first().image_url
        )
        OrderItem.objects.create(
            order=order1,
            product=white_sneakers,
            product_name='White Sneakers',
            price=1999.00,
            quantity=1,
            size='7',
            color='White',
            image_url=white_sneakers.images.first().image_url
        )
        # Timeline
        tl_steps = [
            ('Order Placed', '28 Oct, 10:24 AM', True, 0),
            ('Packed', '29 Oct, 11:00 AM', True, 1),
            ('Shipped', '30 Oct, 08:20 AM', True, 2),
            ('Out for Delivery', 'Expected today by 7 PM', False, 3),
            ('Delivered', 'Expected 31 Oct', False, 4),
        ]
        for s_step, d_txt, is_c, idx in tl_steps:
            OrderTimeline.objects.create(
                order=order1,
                status_step=s_step,
                date_text=d_txt,
                is_completed=is_c,
                order_index=idx
            )

        # Delivered Order
        order2 = Order.objects.create(
            order_number='#SH87654321',
            user=customer,
            customer_name='Areefuddin',
            phone='+91 9876543210',
            delivery_address='12-3-456, MG Road, Bengaluru - 560001',
            address_type='Home',
            payment_method='Credit / Debit Card',
            payment_status='Paid',
            order_status='Delivered',
            item_total=2299.00,
            discount_amount=0.00,
            delivery_charges=0.00,
            total_amount=2299.00,
            estimated_delivery='Delivered on 2 Nov 2026'
        )
        OrderItem.objects.create(
            order=order2,
            product=black_bag,
            product_name='Black Handbag',
            price=2299.00,
            quantity=1,
            size='One Size',
            color='Black',
            image_url=black_bag.images.first().image_url
        )

        # Seeded demo accounts start with an empty bag. Real cart entries are
        # created only through the customer's Add to Cart action.
        CartItem.objects.filter(user=customer).delete()

        # 10. Store Settings & Footer Seeding
        setting, _ = StoreSetting.objects.get_or_create(id=1)
        setting.store_name = 'StyleHub Luxe'
        setting.tagline = 'Curated Luxury Fashion & Timeless Designer Collections'
        setting.description = 'StyleHub Luxe is India\'s premier destination for luxury fashion, ethnic designer couture, haute streetwear, and verified authentic lifestyle accessories.'
        setting.support_phone = '+91 80 4567 8900'
        setting.support_email = 'concierge@stylehub.com'
        setting.flagship_address = '100 Feet Rd, Indiranagar, Bengaluru, Karnataka 560038'
        setting.working_hours = 'Mon - Sat: 09:00 AM - 08:00 PM'
        setting.whatsapp_number = '+919876543210'
        setting.instagram_url = 'https://instagram.com/stylehub'
        setting.facebook_url = 'https://facebook.com/stylehub'
        setting.twitter_url = 'https://twitter.com/stylehub'
        setting.youtube_url = 'https://youtube.com/stylehub'
        setting.copyright_text = '© 2026 StyleHub Luxe Technologies Pvt Ltd. All rights reserved.'
        setting.save()

        # 11. Footer Sections & Links
        footer_sections_data = [
            {
                'title': 'Shop',
                'display_order': 1,
                'links': [
                    ("Women's Collection", '/products?category=women', False),
                    ("Men's Collection", '/products?category=men', False),
                    ('Kids Fashion', '/products?category=kids', False),
                    ('Luxury & Couture', '/products?category=luxury', False),
                    ('Footwear & Bags', '/products?category=footwear', False),
                    ('New Arrivals', '/products?tag=new', False),
                ]
            },
            {
                'title': 'Customer Care',
                'display_order': 2,
                'links': [
                    ('Track My Order', '/my-orders', False),
                    ('Returns & Exchanges', '/return-refund', False),
                    ('Shipping & Delivery', '/policies/shipping-policy', False),
                    ('Help & FAQs', '/help-support', False),
                    ('Refer & Earn VIP', '/referral-history', False),
                ]
            },
            {
                'title': 'StyleHub Company',
                'display_order': 3,
                'links': [
                    ('About StyleHub', '/policies/about-us', False),
                    ('VIP Lounge & Privilege', '/profile', False),
                    ('Flagship Boutique', '/policies/store-locator', False),
                    ('Careers', '/policies/careers', False),
                    ('Contact Concierge', '/help-support', False),
                ]
            },
            {
                'title': 'Policies & Legal',
                'display_order': 4,
                'links': [
                    ('Privacy Policy', '/policies/privacy-policy', False),
                    ('Terms of Service', '/policies/terms-conditions', False),
                    ('Return & Refund Policy', '/policies/refund-policy', False),
                    ('Authenticity & Security', '/policies/security', False),
                ]
            },
        ]

        for s_data in footer_sections_data:
            section, _ = FooterSection.objects.get_or_create(
                title=s_data['title'],
                defaults={'display_order': s_data['display_order'], 'is_active': True}
            )
            section.display_order = s_data['display_order']
            section.save()
            for idx, (label, url, is_ext) in enumerate(s_data['links']):
                FooterLink.objects.update_or_create(
                    section=section,
                    label=label,
                    defaults={'url': url, 'is_external': is_ext, 'display_order': idx}
                )

        # 12. Policy Pages Content
        policy_pages_data = [
            {
                'slug': 'about-us',
                'title': 'About StyleHub Luxe',
                'content': '''# About StyleHub Luxe

Founded with a passion for couture craftsmanship and modern elegance, StyleHub Luxe brings high-fashion sensibilities and curated designer collections directly to your doorstep.

## Our Philosophy
We curate authentic fashion from established designer labels and visionary independent ateliers worldwide. Every garment is inspected for fabric authenticity, stitch precision, and timeless appeal.

## Flagship Experience
Visit our flagship styling salon in Indiranagar, Bengaluru for personal styling sessions, bespoke fittings, and complimentary champagne tastings.

- **Address:** 100 Feet Rd, Indiranagar, Bengaluru, Karnataka 560038
- **Concierge:** concierge@stylehub.com | +91 80 4567 8900
'''
            },
            {
                'slug': 'privacy-policy',
                'title': 'Privacy Policy',
                'content': '''# StyleHub Luxe Privacy Policy

Last updated: November 2026

Your privacy and security are paramount. This policy outlines how StyleHub Luxe collects, stores, and protects your personal data.

### 1. Data Collection
We collect personal information necessary to fulfill your orders, including name, shipping address, contact number, and email. Payment details are processed through PCI-DSS certified gateway Razorpay and are never stored on our servers.

### 2. Virtual Try-On Photos
Images uploaded for AI Virtual Try-On are processed securely in memory and discarded after composite generation. We do not sell or train external models on customer portrait photos.

### 3. Contact Us
For any privacy inquiries or data deletion requests, email our Data Privacy Officer at concierge@stylehub.com.
'''
            },
            {
                'slug': 'terms-conditions',
                'title': 'Terms & Conditions',
                'content': '''# Terms of Service

Welcome to StyleHub Luxe. By browsing, creating an account, or placing an order on our platform, you agree to these Terms of Service.

### Orders and Authenticity
All products sold on StyleHub Luxe are 100% authentic, brand-new, and sourced directly from verified fashion houses. We reserve the right to cancel orders with unexpected pricing or inventory discrepancies.

### Pricing and Taxes
All prices are displayed in Indian Rupees (INR) inclusive of all applicable Goods and Services Taxes (GST).
'''
            },
            {
                'slug': 'refund-policy',
                'title': 'Return & Refund Policy',
                'content': '''# Return & Refund Policy

We want you to love everything you receive from StyleHub Luxe. If something isn't right, we offer an effortless return process.

### 7-Day Window
You may initiate a return within 7 calendar days of delivery for unworn items in their original packaging with tags attached.

### Doorstep Pickup & Fast Refund
Our courier partner will pick up the package from your doorstep. Once received and verified, refunds are credited back to your original payment method or StyleHub Wallet within 48 to 72 business hours.
'''
            },
            {
                'slug': 'shipping-policy',
                'title': 'Shipping & Delivery Policy',
                'content': '''# Shipping & Delivery Policy

### Complimentary Express Shipping
StyleHub Luxe provides complimentary insured express shipping across India on all orders.

### Delivery Timelines
- **Metro Cities (Bengaluru, Mumbai, Delhi, Hyderabad):** 2 to 3 business days.
- **Rest of India:** 3 to 5 business days.

Live tracking updates are provided via SMS, WhatsApp, and in the 'My Orders' section of the application.
'''
            },
        ]

        for p_data in policy_pages_data:
            PolicyPage.objects.update_or_create(
                slug=p_data['slug'],
                defaults={'title': p_data['title'], 'content': p_data['content']}
            )

        self.stdout.write(self.style.SUCCESS('StyleHub Database seeded with 100% dynamic fashion data & footer APIs!'))
