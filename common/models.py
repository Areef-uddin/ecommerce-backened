from django.db import models
from django.conf import settings

class Banner(models.Model):
    title = models.CharField(max_length=150) # e.g. "New Season New Styles"
    subtitle = models.CharField(max_length=200, blank=True)
    badge = models.CharField(max_length=50, default='New Season')
    discount_text = models.CharField(max_length=50, default='UP TO 50% OFF')
    image_url = models.URLField(max_length=500)
    category_slug = models.CharField(max_length=100, default='women')
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.title


class Notification(models.Model):
    CATEGORY_CHOICES = (
        ('all', 'All'),
        ('orders', 'Orders'),
        ('offers', 'Offers'),
        ('updates', 'Updates'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=150)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='orders')
    icon = models.CharField(max_length=50, default='shopping-bag')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.category})"


class FAQ(models.Model):
    category = models.CharField(max_length=100) # e.g. 'Track My Order', 'Returns & Refunds', 'Payment Issues', etc.
    question = models.CharField(max_length=250)
    answer = models.TextField()
    icon = models.CharField(max_length=50, default='help-circle')
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"[{self.category}] {self.question}"


class ContactTicket(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"


class StoreSetting(models.Model):
    store_name = models.CharField(max_length=150, default='StyleHub')
    tagline = models.CharField(max_length=250, default='Discover Luxury Fashion & Curated Collections')
    description = models.TextField(default='StyleHub is your premier destination for luxury fashion, ethnic designer wear, and premium lifestyle accessories.')
    support_phone = models.CharField(max_length=50, default='+91 98765 43210')
    support_email = models.EmailField(default='concierge@stylehub.com')
    flagship_address = models.TextField(default='100 Feet Rd, Indiranagar, Bengaluru, Karnataka 560038')
    working_hours = models.CharField(max_length=100, default='Mon - Sat: 09:00 AM - 08:00 PM')
    whatsapp_number = models.CharField(max_length=50, default='+919876543210')
    instagram_url = models.URLField(max_length=300, default='https://instagram.com/stylehub', blank=True)
    facebook_url = models.URLField(max_length=300, default='https://facebook.com/stylehub', blank=True)
    twitter_url = models.URLField(max_length=300, default='https://twitter.com/stylehub', blank=True)
    youtube_url = models.URLField(max_length=300, default='https://youtube.com/stylehub', blank=True)
    copyright_text = models.CharField(max_length=250, default='© 2026 StyleHub Inc. All rights reserved.')

    class Meta:
        verbose_name = 'Store Setting'
        verbose_name_plural = 'Store Settings'

    def __str__(self):
        return self.store_name

    @classmethod
    def get_settings(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj


class FooterSection(models.Model):
    title = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.title


class FooterLink(models.Model):
    section = models.ForeignKey(FooterSection, on_delete=models.CASCADE, related_name='links')
    label = models.CharField(max_length=100)
    url = models.CharField(max_length=255)
    is_external = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"{self.section.title} -> {self.label}"


class PolicyPage(models.Model):
    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.email

