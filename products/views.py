from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q
from .models import Category, SubCategory, Product, ProductImage, ProductColor, ProductSize, SizeGuide, Wishlist
from .serializers import (
    CategorySerializer, SubCategorySerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    SizeGuideSerializer, WishlistSerializer
)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True).order_by('display_order', 'name')
    serializer_class = CategorySerializer

    def get_permissions(self):
        return [permissions.AllowAny()]

    def get_queryset(self):
        # Admin can view all categories including inactive
        if self.request.user and self.request.user.is_staff:
            return Category.objects.all().order_by('display_order', 'name')
        return Category.objects.filter(is_active=True).order_by('display_order', 'name')


class SubCategoryViewSet(viewsets.ModelViewSet):
    queryset = SubCategory.objects.all().order_by('display_order', 'name')
    serializer_class = SubCategorySerializer

    def get_permissions(self):
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        category_slug = self.request.query_params.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        return qs


class ProductViewSet(viewsets.ModelViewSet):
    lookup_field = 'id'

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer

    def get_queryset(self):
        qs = Product.objects.all().select_related('category', 'subcategory').prefetch_related('images', 'colors', 'sizes')
        
        # Admin can view out of stock, customers only active products
        if not (self.request.user and self.request.user.is_staff):
            qs = qs.filter(in_stock=True)

        # Filters
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(Q(category__slug=category) | Q(category__name__iexact=category))

        subcategory = self.request.query_params.get('subcategory')
        if subcategory:
            qs = qs.filter(Q(subcategory__slug=subcategory) | Q(subcategory__name__iexact=subcategory))

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        trending = self.request.query_params.get('trending')
        if trending == 'true':
            qs = qs.filter(is_trending=True)

        new_arrival = self.request.query_params.get('new_arrival')
        if new_arrival == 'true':
            qs = qs.filter(is_new_arrival=True)

        # Sorting
        sort = self.request.query_params.get('sort')
        if sort == 'price_low_high':
            qs = qs.order_by('price')
        elif sort == 'price_high_low':
            qs = qs.order_by('-price')
        elif sort == 'rating':
            qs = qs.order_by('-rating')
        elif sort == 'newest':
            qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by('-created_at')

        return qs


class SizeGuideViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SizeGuide.objects.all()
    serializer_class = SizeGuideSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        category_type = self.request.query_params.get('category', 'Women')
        return qs.filter(category_type__iexact=category_type)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'detail': 'product_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        product = Product.objects.filter(id=product_id).first()
        if not product:
            return Response({'detail': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        wishlist_item = Wishlist.objects.filter(user=request.user, product=product).first()
        if wishlist_item:
            wishlist_item.delete()
            return Response({'message': 'Removed from wishlist', 'is_wishlisted': False})
        else:
            Wishlist.objects.create(user=request.user, product=product)
            return Response({'message': 'Added to wishlist', 'is_wishlisted': True}, status=status.HTTP_201_CREATED)
