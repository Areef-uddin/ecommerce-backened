from django.db import models
from django.conf import settings

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    image_url = models.URLField(max_length=500, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    image_url = models.URLField(max_length=500, blank=True)
    item_count = models.IntegerField(default=0)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Sub Categories'
        ordering = ['display_order', 'name']
        unique_together = ('category', 'slug')

    def __str__(self):
        return f"{self.category.name} -> {self.name}"


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    subcategory = models.ForeignKey(SubCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # selling price e.g. 1299
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # e.g. 2499
    discount_percent = models.IntegerField(default=0)  # e.g. 48%
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.5)  # e.g. 4.5
    review_count = models.PositiveIntegerField(default=120)  # e.g. 1200
    is_trending = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    in_stock = models.BooleanField(default=True)
    stock_quantity = models.PositiveIntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.original_price and self.original_price > self.price:
            self.discount_percent = round(((self.original_price - self.price) / self.original_price) * 100)
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=500)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_primary', 'id']

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductColor(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='colors')
    name = models.CharField(max_length=50)  # e.g. Pink, Peach, Black, Red
    hex_code = models.CharField(max_length=10)  # e.g. #F8BBD0

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class ProductSize(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sizes')
    size = models.CharField(max_length=20)  # XS, S, M, L, XL, XXL

    def __str__(self):
        return f"{self.product.name} - {self.size}"


class SizeGuide(models.Model):
    CATEGORY_CHOICES = (
        ('Women', 'Women'),
        ('Men', 'Men'),
        ('Kids', 'Kids'),
    )
    category_type = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='Women')
    size = models.CharField(max_length=10)  # XS, S, M, L, XL
    # Inches
    bust_in = models.CharField(max_length=20)
    waist_in = models.CharField(max_length=20)
    hip_in = models.CharField(max_length=20)
    # Centimeters
    bust_cm = models.CharField(max_length=20)
    waist_cm = models.CharField(max_length=20)
    hip_cm = models.CharField(max_length=20)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.category_type} - {self.size}"


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlists')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} -> {self.product.name}"
