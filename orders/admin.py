from django.contrib import admin
from .models import Order, OrderItem, OrderTimeline, Coupon, ReturnRequest, ShipmentTracking, TrackingMilestone

class TrackingMilestoneInline(admin.TabularInline):
    model = TrackingMilestone
    extra = 0

@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(admin.ModelAdmin):
    list_display = ('tracking_number', 'order', 'courier_name', 'current_status', 'is_demo_mode', 'current_location', 'updated_at')
    list_filter = ('current_status', 'is_demo_mode', 'courier_name')
    search_fields = ('tracking_number', 'order__order_number', 'order__customer_name')
    inlines = [TrackingMilestoneInline]

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class OrderTimelineInline(admin.TabularInline):
    model = OrderTimeline
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer_name', 'phone', 'total_amount', 'order_status', 'payment_status', 'created_at')
    list_filter = ('order_status', 'payment_status', 'payment_method')
    search_fields = ('order_number', 'customer_name', 'phone', 'user__email')
    inlines = [OrderItemInline, OrderTimelineInline]

admin.site.register(Coupon)
admin.site.register(ReturnRequest)
