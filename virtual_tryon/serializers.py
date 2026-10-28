from rest_framework import serializers
from .models import TryOnJob
from products.serializers import ProductListSerializer

class TryOnJobSerializer(serializers.ModelSerializer):
    product_details = ProductListSerializer(source='product', read_only=True)
    user_image_url = serializers.SerializerMethodField()
    result_display_url = serializers.SerializerMethodField()

    class Meta:
        model = TryOnJob
        fields = (
            'id', 'product', 'product_details', 'visualization_mode',
            'user_image', 'user_image_url', 'product_image_url',
            'status', 'result_image', 'result_image_url', 'result_display_url',
            'error_message', 'prompt_used', 'metadata', 'created_at', 'completed_at'
        )
        read_only_fields = ('id', 'status', 'result_image', 'result_image_url', 'created_at', 'completed_at')

    def get_user_image_url(self, obj):
        if obj.user_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.user_image.url)
            return obj.user_image.url
        return ""

    def get_result_display_url(self, obj):
        if obj.result_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.result_image.url)
            return obj.result_image.url
        return obj.result_image_url or ""

