from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CartViewSet, OrderViewSet, ReturnRequestViewSet

router = DefaultRouter()
router.register('cart', CartViewSet, basename='cart')
router.register('orders', OrderViewSet, basename='order')
router.register('returns', ReturnRequestViewSet, basename='return')

urlpatterns = [
    path('', include(router.urls)),
]
