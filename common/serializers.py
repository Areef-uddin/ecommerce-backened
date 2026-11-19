from rest_framework import serializers
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

class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    created_at_formatted = serializers.SerializerMethodField()
    can_mark_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ('id', 'title', 'message', 'category', 'icon', 'is_read', 'created_at', 'created_at_formatted', 'can_mark_read')

    def get_created_at_formatted(self, obj):
        return obj.created_at.strftime('%d %b, %I:%M %p')

    def get_can_mark_read(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.user_id == request.user.id)


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = '__all__'


class ContactTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactTicket
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class StoreSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSetting
        fields = '__all__'


class FooterLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterLink
        fields = ('id', 'label', 'url', 'is_external', 'display_order')


class FooterSectionSerializer(serializers.ModelSerializer):
    links = serializers.SerializerMethodField()

    class Meta:
        model = FooterSection
        fields = ('id', 'title', 'display_order', 'is_active', 'links')

    def get_links(self, obj):
        links = obj.links.all().order_by('display_order')
        return FooterLinkSerializer(links, many=True).data


class PolicyPageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyPage
        fields = ('id', 'slug', 'title', 'updated_at')


class PolicyPageDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyPage
        fields = ('id', 'slug', 'title', 'content', 'updated_at')


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ('id', 'email', 'subscribed_at', 'is_active')
        read_only_fields = ('id', 'subscribed_at', 'is_active')

