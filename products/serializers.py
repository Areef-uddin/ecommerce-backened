import re
from rest_framework import serializers
from .models import Category, SubCategory, Product, ProductImage, ProductColor, ProductSize, SizeGuide, Wishlist

class SubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = ('id', 'category', 'name', 'slug', 'image_url', 'item_count', 'display_order')


class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'image_url', 'icon', 'display_order', 'is_active', 'subcategories')


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('id', 'image_url', 'is_primary')


class ProductColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductColor
        fields = ('id', 'name', 'hex_code')


class ProductSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSize
        fields = ('id', 'size')


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    is_wishlisted = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'category', 'category_name', 'subcategory', 'subcategory_name',
            'price', 'original_price', 'discount_percent', 'rating', 'review_count',
            'is_trending', 'is_new_arrival', 'in_stock', 'primary_image', 'is_wishlisted'
        )

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        return img.image_url if img else None

    def get_is_wishlisted(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Wishlist.objects.filter(user=request.user, product=obj).exists()
        return False


class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.name', read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    colors = ProductColorSerializer(many=True, read_only=True)
    sizes = ProductSizeSerializer(many=True, read_only=True)
    is_wishlisted = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'category', 'category_name', 'subcategory', 'subcategory_name',
            'description', 'price', 'original_price', 'discount_percent', 'rating', 'review_count',
            'is_trending', 'is_new_arrival', 'in_stock', 'stock_quantity', 'images', 'colors', 'sizes',
            'is_wishlisted', 'created_at'
        )

    def get_is_wishlisted(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Wishlist.objects.filter(user=request.user, product=obj).exists()
        return False


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.CharField(write_only=True, required=False, allow_blank=True)
    images = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    colors = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    sizes = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    primary_image = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'category', 'subcategory', 'description',
            'price', 'original_price', 'rating', 'is_trending', 'is_new_arrival',
            'in_stock', 'stock_quantity', 'image_url', 'images', 'colors', 'sizes', 'primary_image'
        )

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first() or obj.images.first()
        return img.image_url if img else None

    def create(self, validated_data):
        image_url = validated_data.pop('image_url', None)
        images = validated_data.pop('images', [])
        colors = validated_data.pop('colors', [])
        sizes = validated_data.pop('sizes', [])

        if not validated_data.get('slug'):
            name = validated_data.get('name', 'product')
            base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            validated_data['slug'] = slug

        product = Product.objects.create(**validated_data)

        # Handle primary image
        primary_set = False
        if image_url and image_url.strip():
            ProductImage.objects.create(product=product, image_url=image_url.strip(), is_primary=True)
            primary_set = True

        for img in images:
            if img and img.strip() and img.strip() != image_url:
                ProductImage.objects.create(product=product, image_url=img.strip(), is_primary=(not primary_set))
                primary_set = True

        # Fallback if no image was provided
        if not product.images.exists():
            ProductImage.objects.create(
                product=product,
                image_url='https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=800',
                is_primary=True
            )

        # Handle colors
        if colors:
            for col in colors:
                ProductColor.objects.create(product=product, name=col, hex_code='#111111')
        else:
            ProductColor.objects.create(product=product, name='Black', hex_code='#111111')
            ProductColor.objects.create(product=product, name='Pink', hex_code='#F8BBD0')

        # Handle sizes
        if sizes:
            for sz in sizes:
                ProductSize.objects.create(product=product, size=sz)
        else:
            for sz in ['XS', 'S', 'M', 'L', 'XL']:
                ProductSize.objects.create(product=product, size=sz)

        return product


class SizeGuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = SizeGuide
        fields = '__all__'


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ('id', 'product', 'product_id', 'created_at')
