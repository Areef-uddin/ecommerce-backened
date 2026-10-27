import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import User
from products.models import Category, SubCategory, Product, ProductImage, ProductColor, ProductSize, SizeGuide
from common.models import Banner, FAQ

def seed():
    print("[*] Seeding NeonDB PostgreSQL database...")

    # 1. Admin user
    admin, created = User.objects.get_or_create(
        email='admin@stylehub.com',
        defaults={
            'first_name': 'StyleHub',
            'last_name': 'Administrator',
            'phone': '+919999900000',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    admin.set_password('adminpassword')
    admin.save()
    print("[OK] Admin user ready: admin@stylehub.com / adminpassword")

    # 2. Test Customer
    user, _ = User.objects.get_or_create(
        email='customer@stylehub.com',
        defaults={
            'first_name': 'Priya',
            'last_name': 'Sharma',
            'phone': '+919876543210',
            'avatar': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400'
        }
    )
    user.set_password('password123')
    user.save()
    print("[OK] Test Customer ready: customer@stylehub.com / password123")

    # 3. Banners
    Banner.objects.all().delete()
    banners = [
        Banner(
            title="Summer Festive Extravaganza",
            subtitle="Flat 50% Off on Top Designer Ethnic Wear",
            badge="Limited Festive",
            discount_text="FLAT 50% OFF",
            image_url="https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=1200",
            category_slug="women",
            is_active=True,
            display_order=1
        ),
        Banner(
            title="Luxury Silk & Fusion Wear",
            subtitle="Curated collection crafted for celebrations",
            badge="New Launch",
            discount_text="UP TO 40% OFF",
            image_url="https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=1200",
            category_slug="women",
            is_active=True,
            display_order=2
        ),
        Banner(
            title="Minimalist Everyday Essentials",
            subtitle="Breathe easy in 100% organic cottons",
            badge="Best Sellers",
            discount_text="BUY 2 GET 1",
            image_url="https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200",
            category_slug="men",
            is_active=True,
            display_order=3
        ),
    ]
    Banner.objects.bulk_create(banners)
    print("[OK] Banners seeded")

    # 4. Categories & Subcategories
    categories_data = [
        {
            "name": "Women",
            "slug": "women",
            "image_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600",
            "subcategories": ["Dresses", "Tops & Tunics", "Kurtas", "Sarees", "Denim"]
        },
        {
            "name": "Men",
            "slug": "men",
            "image_url": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600",
            "subcategories": ["Shirts", "T-Shirts", "Jackets", "Trousers", "Ethnic Kurta"]
        },
        {
            "name": "Kids",
            "slug": "kids",
            "image_url": "https://images.unsplash.com/photo-1622290291468-a28f7a7dc6a8?w=600",
            "subcategories": ["Boys", "Girls", "Infants", "Accessories"]
        },
        {
            "name": "Footwear",
            "slug": "footwear",
            "image_url": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=600",
            "subcategories": ["Sneakers", "Heels", "Loafers", "Boots"]
        },
        {
            "name": "Accessories",
            "slug": "accessories",
            "image_url": "https://images.unsplash.com/photo-1524805444758-089113d48a6d?w=600",
            "subcategories": ["Handbags", "Jewellery", "Watches", "Sunglasses"]
        },
    ]

    for cat_data in categories_data:
        cat, _ = Category.objects.get_or_create(
            slug=cat_data["slug"],
            defaults={"name": cat_data["name"], "image_url": cat_data["image_url"]}
        )
        for sub_name in cat_data["subcategories"]:
            sub_slug = sub_name.lower().replace(" & ", "-").replace(" ", "-")
            SubCategory.objects.get_or_create(
                category=cat,
                slug=sub_slug,
                defaults={"name": sub_name}
            )
    print("[OK] Categories and Subcategories seeded")

    # 5. Products
    products_data = [
        {
            "name": "Pastel Pink Embroidered Anarkali Set",
            "slug": "pastel-pink-embroidered-anarkali-set",
            "cat_slug": "women",
            "price": 2499.00,
            "original_price": 4999.00,
            "rating": 4.8,
            "is_trending": True,
            "is_new_arrival": True,
            "description": "Exquisite georgette Anarkali suit set adorned with intricate hand-embroidered sequin zari work. Includes matching dupatta and churidar trousers.",
            "images": [
                "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?w=800",
                "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=800"
            ],
            "colors": [("Blush Pink", "#F8BBD0"), ("Ivory White", "#F5F5F5"), ("Sage Green", "#C8E6C9")],
            "sizes": ["XS", "S", "M", "L", "XL"]
        },
        {
            "name": "Tailored Italian Linen Blazer",
            "slug": "tailored-italian-linen-blazer",
            "cat_slug": "men",
            "price": 3899.00,
            "original_price": 6499.00,
            "rating": 4.9,
            "is_trending": True,
            "is_new_arrival": False,
            "description": "Crafted from 100% breathable Italian linen with structured shoulders and horn buttons. Perfect for sophisticated destination weddings and evening soirees.",
            "images": [
                "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800",
                "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=800"
            ],
            "colors": [("Navy Blue", "#1E3A8A"), ("Sand Beige", "#D4A373"), ("Charcoal", "#334155")],
            "sizes": ["38", "40", "42", "44"]
        },
        {
            "name": "Pure Mulberry Silk Banarasi Saree",
            "slug": "pure-mulberry-silk-banarasi-saree",
            "cat_slug": "women",
            "price": 5499.00,
            "original_price": 9999.00,
            "rating": 4.9,
            "is_trending": True,
            "is_new_arrival": True,
            "description": "Handwoven Banarasi silk masterpiece featuring gold kadwa floral motifs with an ornate pallu. Comes with unstitched matching blouse piece.",
            "images": [
                "https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=800",
                "https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?w=800"
            ],
            "colors": [("Royal Crimson", "#881337"), ("Emerald Gold", "#064E3B"), ("Royal Purple", "#581C87")],
            "sizes": ["Free Size"]
        },
        {
            "name": "Urban Minimalist Leather Crossbody",
            "slug": "urban-minimalist-leather-crossbody",
            "cat_slug": "accessories",
            "price": 1899.00,
            "original_price": 3299.00,
            "rating": 4.7,
            "is_trending": True,
            "is_new_arrival": False,
            "description": "Full-grain top calf leather handbag with antique gold hardware, dual magnetic closures, and adjustable shoulder strap.",
            "images": [
                "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=800",
                "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=800"
            ],
            "colors": [("Chestnut Tan", "#78350F"), ("Obsidian Black", "#0F172A")],
            "sizes": ["Regular"]
        },
        {
            "name": "Street Classic White Chunky Sneakers",
            "slug": "street-classic-white-chunky-sneakers",
            "cat_slug": "footwear",
            "price": 2199.00,
            "original_price": 3999.00,
            "rating": 4.6,
            "is_trending": True,
            "is_new_arrival": True,
            "description": "Aerodynamic lightweight foam sole with premium memory cushion insole and breathable perforated leather upper.",
            "images": [
                "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=800",
                "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=800"
            ],
            "colors": [("Pure White", "#FFFFFF"), ("White/Rose Gold", "#FDE047")],
            "sizes": ["UK 6", "UK 7", "UK 8", "UK 9", "UK 10"]
        },
        {
            "name": "Kids Festive Jacquard Kurta Pajama",
            "slug": "kids-festive-jacquard-kurta-pajama",
            "cat_slug": "kids",
            "price": 1299.00,
            "original_price": 2299.00,
            "rating": 4.8,
            "is_trending": False,
            "is_new_arrival": True,
            "description": "Gentle on sensitive skin with soft cotton lining, woven banarasi jacquard jacket, and comfortable elasticated churidar.",
            "images": [
                "https://images.unsplash.com/photo-1622290291468-a28f7a7dc6a8?w=800"
            ],
            "colors": [("Mustard Gold", "#CA8A04"), ("Sky Blue", "#0284C7")],
            "sizes": ["3-4Y", "5-6Y", "7-8Y", "9-10Y"]
        }
    ]

    for p_data in products_data:
        cat = Category.objects.get(slug=p_data["cat_slug"])
        prod, _ = Product.objects.get_or_create(
            slug=p_data["slug"],
            defaults={
                "name": p_data["name"],
                "category": cat,
                "price": p_data["price"],
                "original_price": p_data["original_price"],
                "rating": p_data["rating"],
                "is_trending": p_data["is_trending"],
                "is_new_arrival": p_data["is_new_arrival"],
                "description": p_data["description"],
                "stock_quantity": 50,
                "in_stock": True
            }
        )
        
        # Images
        ProductImage.objects.filter(product=prod).delete()
        for idx, img_url in enumerate(p_data["images"]):
            ProductImage.objects.create(
                product=prod,
                image_url=img_url,
                is_primary=(idx == 0)
            )
            
        # Colors
        ProductColor.objects.filter(product=prod).delete()
        for c_name, c_hex in p_data["colors"]:
            ProductColor.objects.create(
                product=prod,
                name=c_name,
                hex_code=c_hex
            )
            
        # Sizes
        ProductSize.objects.filter(product=prod).delete()
        for s_name in p_data["sizes"]:
            ProductSize.objects.create(
                product=prod,
                size=s_name
            )

    print("[OK] Products, images, colors, and sizes seeded")

    # 6. Size Guide
    SizeGuide.objects.all().delete()
    size_guides = [
        SizeGuide(category_type="Women", size="XS", bust_in="32", waist_in="26", hip_in="35", bust_cm="81", waist_cm="66", hip_cm="89"),
        SizeGuide(category_type="Women", size="S", bust_in="34", waist_in="28", hip_in="37", bust_cm="86", waist_cm="71", hip_cm="94"),
        SizeGuide(category_type="Women", size="M", bust_in="36", waist_in="30", hip_in="39", bust_cm="91", waist_cm="76", hip_cm="99"),
        SizeGuide(category_type="Women", size="L", bust_in="38", waist_in="32", hip_in="41", bust_cm="97", waist_cm="81", hip_cm="104"),
        SizeGuide(category_type="Women", size="XL", bust_in="40", waist_in="34", hip_in="43", bust_cm="102", waist_cm="86", hip_cm="109"),
        SizeGuide(category_type="Men", size="38", bust_in="38", waist_in="32", hip_in="39", bust_cm="96", waist_cm="81", hip_cm="99"),
        SizeGuide(category_type="Men", size="40", bust_in="40", waist_in="34", hip_in="41", bust_cm="102", waist_cm="86", hip_cm="104"),
        SizeGuide(category_type="Men", size="42", bust_in="42", waist_in="36", hip_in="43", bust_cm="107", waist_cm="91", hip_cm="109"),
    ]
    SizeGuide.objects.bulk_create(size_guides)
    print("[OK] Size Guide seeded")

    print("\nALL NEON POSTGRESQL DATA SEEDED SUCCESSFULLY!")

if __name__ == '__main__':
    seed()
