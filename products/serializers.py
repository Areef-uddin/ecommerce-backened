import re
from rest_framework import serializers
from .models import Category, SubCategory, Product, ProductImage, ProductColor, ProductSize, SizeGuide, Wishlist

class SubCategorySerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = SubCategory
        fields = ('id', 'category', 'name', 'slug', 'image_url', 'item_count', 'display_order')

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        url = ret.get('image_url')
        if url and (url.startswith('/media/') or url.startswith('media/')):
            ret['image_url'] = f"http://127.0.0.1:8000/{url.lstrip('/')}"
        return ret

    def create(self, validated_data):
        import re, base64, os, time
        from django.conf import settings
        if not validated_data.get('slug'):
            name = validated_data.get('name', 'sub')
            validated_data['slug'] = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

        img = validated_data.get('image_url', '')
        if img and img.startswith('data:image'):
            try:
                header, b64_data = img.split(';base64,', 1)
                ext = '.png'
                if 'jpeg' in header or 'jpg' in header:
                    ext = '.jpg'
                sub_dir = os.path.join(settings.MEDIA_ROOT, 'subcategories')
                os.makedirs(sub_dir, exist_ok=True)
                filename = f"sub_{int(time.time())}{ext}"
                with open(os.path.join(sub_dir, filename), 'wb') as dest:
                    dest.write(base64.b64decode(b64_data))
                validated_data['image_url'] = f"{settings.MEDIA_URL}subcategories/{filename}"
            except Exception as e:
                print(f"Error saving subcategory image: {e}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        import base64, os, time
        from django.conf import settings
        img = validated_data.get('image_url', '')
        if img and img.startswith('data:image'):
            try:
                header, b64_data = img.split(';base64,', 1)
                ext = '.png'
                if 'jpeg' in header or 'jpg' in header:
                    ext = '.jpg'
                sub_dir = os.path.join(settings.MEDIA_ROOT, 'subcategories')
                os.makedirs(sub_dir, exist_ok=True)
                filename = f"sub_{instance.id}_{int(time.time())}{ext}"
                with open(os.path.join(sub_dir, filename), 'wb') as dest:
                    dest.write(base64.b64decode(b64_data))
                validated_data['image_url'] = f"{settings.MEDIA_URL}subcategories/{filename}"
            except Exception as e:
                print(f"Error updating subcategory image: {e}")
        return super().update(instance, validated_data)


class CategorySerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.CharField(required=False, allow_blank=True)
    subcategories = SubCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'image_url', 'icon', 'display_order', 'is_active', 'subcategories')

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        url = ret.get('image_url')
        if url and (url.startswith('/media/') or url.startswith('media/')):
            ret['image_url'] = f"http://127.0.0.1:8000/{url.lstrip('/')}"
        return ret

    def create(self, validated_data):
        import re, base64, os, time
        from django.conf import settings
        if not validated_data.get('slug'):
            name = validated_data.get('name', 'cat')
            validated_data['slug'] = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

        img = validated_data.get('image_url', '')
        if img and img.startswith('data:image'):
            try:
                header, b64_data = img.split(';base64,', 1)
                ext = '.png'
                if 'jpeg' in header or 'jpg' in header:
                    ext = '.jpg'
                cat_dir = os.path.join(settings.MEDIA_ROOT, 'categories')
                os.makedirs(cat_dir, exist_ok=True)
                filename = f"cat_{int(time.time())}{ext}"
                with open(os.path.join(cat_dir, filename), 'wb') as dest:
                    dest.write(base64.b64decode(b64_data))
                validated_data['image_url'] = f"{settings.MEDIA_URL}categories/{filename}"
            except Exception as e:
                print(f"Error saving category image: {e}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        import base64, os, time
        from django.conf import settings
        img = validated_data.get('image_url', '')
        if img and img.startswith('data:image'):
            try:
                header, b64_data = img.split(';base64,', 1)
                ext = '.png'
                if 'jpeg' in header or 'jpg' in header:
                    ext = '.jpg'
                cat_dir = os.path.join(settings.MEDIA_ROOT, 'categories')
                os.makedirs(cat_dir, exist_ok=True)
                filename = f"cat_{instance.id}_{int(time.time())}{ext}"
                with open(os.path.join(cat_dir, filename), 'wb') as dest:
                    dest.write(base64.b64decode(b64_data))
                validated_data['image_url'] = f"{settings.MEDIA_URL}categories/{filename}"
            except Exception as e:
                print(f"Error updating category image: {e}")
        return super().update(instance, validated_data)


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
        if not img or not img.image_url:
            return None
        url = img.image_url
        if url.startswith('/media/') or url.startswith('media/'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri('/' + url.lstrip('/'))
            return f"http://127.0.0.1:8000/{url.lstrip('/')}"
        return url

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
            raw_url = image_url.strip()
            if raw_url.startswith('data:image'):
                try:
                    import base64, os, time
                    from django.conf import settings
                    header, b64_data = raw_url.split(';base64,', 1)
                    ext = '.png'
                    if 'jpeg' in header or 'jpg' in header:
                        ext = '.jpg'
                    elif 'webp' in header:
                        ext = '.webp'
                    products_dir = os.path.join(settings.MEDIA_ROOT, 'products')
                    os.makedirs(products_dir, exist_ok=True)
                    filename = f'prod_{product.id}_{int(time.time())}{ext}'
                    filepath = os.path.join(products_dir, filename)
                    with open(filepath, 'wb') as dest:
                        dest.write(base64.b64decode(b64_data))
                    raw_url = f'{settings.MEDIA_URL}products/{filename}'
                except Exception as e:
                    print(f"Error saving product image: {e}")
            ProductImage.objects.create(product=product, image_url=raw_url, is_primary=True)
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

    def update(self, instance, validated_data):
        image_url = validated_data.pop('image_url', None)
        images = validated_data.pop('images', None)
        colors = validated_data.pop('colors', None)
        sizes = validated_data.pop('sizes', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if image_url and image_url.strip():
            raw_url = image_url.strip()
            if raw_url.startswith('data:image'):
                try:
                    import base64, os, time
                    from django.conf import settings
                    header, b64_data = raw_url.split(';base64,', 1)
                    ext = '.png'
                    if 'jpeg' in header or 'jpg' in header:
                        ext = '.jpg'
                    elif 'webp' in header:
                        ext = '.webp'
                    products_dir = os.path.join(settings.MEDIA_ROOT, 'products')
                    os.makedirs(products_dir, exist_ok=True)
                    filename = f'prod_{instance.id}_{int(time.time())}{ext}'
                    filepath = os.path.join(products_dir, filename)
                    with open(filepath, 'wb') as dest:
                        dest.write(base64.b64decode(b64_data))
                    raw_url = f'{settings.MEDIA_URL}products/{filename}'
                except Exception as e:
                    print(f"Error saving product image on update: {e}")
            primary_img = instance.images.filter(is_primary=True).first()
            if primary_img:
                primary_img.image_url = raw_url
                primary_img.save()
            else:
                ProductImage.objects.create(product=instance, image_url=raw_url, is_primary=True)

        return instance


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
