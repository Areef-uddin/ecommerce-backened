from django.db import models
from django.conf import settings
from products.models import Product

class TryOnJob(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    MODE_CHOICES = (
        ('clothing', 'Clothing Try-On'),
        ('footwear', 'Footwear Try-On'),
        ('accessories', 'Accessories & Bags'),
        ('furniture', 'Visualize in My Space'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tryon_jobs')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='tryon_jobs')
    visualization_mode = models.CharField(max_length=50, choices=MODE_CHOICES, default='clothing')
    user_image = models.ImageField(upload_to='tryon_inputs/')
    product_image_url = models.URLField(max_length=800, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_image = models.ImageField(upload_to='tryon_results/', blank=True, null=True)
    result_image_url = models.URLField(max_length=800, blank=True)
    error_message = models.TextField(blank=True)
    prompt_used = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"TryOn #{self.id} - {self.product.name} ({self.status})"

