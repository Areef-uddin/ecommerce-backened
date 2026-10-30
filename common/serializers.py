from rest_framework import serializers
from .models import Banner, Notification, FAQ, ContactTicket

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
