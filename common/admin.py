from django.contrib import admin
from .models import (
    Banner,
    Notification,
    FAQ,
    ContactTicket,
    StoreSetting,
    FooterSection,
    FooterLink,
    PolicyPage,
    NewsletterSubscriber,
)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'badge', 'category_slug', 'is_active', 'display_order')
    list_editable = ('is_active', 'display_order')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'is_read', 'created_at')
    list_filter = ('category', 'is_read')
    search_fields = ('title', 'message')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'display_order')
    list_filter = ('category',)
    search_fields = ('question', 'answer')


@admin.register(ContactTicket)
class ContactTicketAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')


@admin.register(StoreSetting)
class StoreSettingAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'support_phone', 'support_email', 'working_hours')


class FooterLinkInline(admin.TabularInline):
    model = FooterLink
    extra = 2
    fields = ('label', 'url', 'is_external', 'display_order')


@admin.register(FooterSection)
class FooterSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')
    inlines = [FooterLinkInline]


@admin.register(PolicyPage)
class PolicyPageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'updated_at')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'content')


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'subscribed_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('email',)

