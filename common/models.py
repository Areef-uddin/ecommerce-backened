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
