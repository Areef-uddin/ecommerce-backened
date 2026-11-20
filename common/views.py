from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.core.cache import cache
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
from .serializers import (
    BannerSerializer,
    NotificationSerializer,
    FAQSerializer,
    ContactTicketSerializer,
    StoreSettingSerializer,
    FooterSectionSerializer,
    FooterLinkSerializer,
    PolicyPageListSerializer,
    PolicyPageDetailSerializer,
    NewsletterSubscriberSerializer,
)
from orders.models import Order
from products.models import Product
from accounts.models import User

class BannerViewSet(viewsets.ModelViewSet):
    queryset = Banner.objects.all().order_by('display_order')
    serializer_class = BannerSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        if self.request.user and self.request.user.is_staff:
            return Banner.objects.all().order_by('display_order')
        return Banner.objects.filter(is_active=True).order_by('display_order')

    def list(self, request, *args, **kwargs):
        if not (request.user and request.user.is_staff):
            cached = cache.get('active_banners_list')
            if cached is not None:
                return Response(cached)
            resp = super().list(request, *args, **kwargs)
            cache.set('active_banners_list', resp.data, 600)
            return resp
        return super().list(request, *args, **kwargs)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Notification.objects.filter(user=user) | Notification.objects.filter(user__isnull=True)
        
        category = self.request.query_params.get('category')
        if category and category.lower() != 'all':
            qs = qs.filter(category__iexact=category)

        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        # Global announcements do not have per-user read state, so only count
        # user-targeted notifications in the badge.
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notif = self.get_object()
        if notif.user_id != request.user.id:
            return Response(
                {'detail': 'Only personal notifications can be marked as read.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        notif.is_read = True
        notif.save()
        return Response({'status': 'marked as read'})


class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FAQ.objects.all().order_by('display_order')
    serializer_class = FAQSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(question__icontains=search) | qs.filter(answer__icontains=search)
        return qs


class ContactTicketViewSet(viewsets.ModelViewSet):
    queryset = ContactTicket.objects.all().order_by('-created_at')
    serializer_class = ContactTicketSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class StoreSettingViewSet(viewsets.ModelViewSet):
    queryset = StoreSetting.objects.all()
    serializer_class = StoreSettingSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def list(self, request, *args, **kwargs):
        settings_obj = StoreSetting.get_settings()
        serializer = self.get_serializer(settings_obj)
        return Response(serializer.data)


class FooterSectionViewSet(viewsets.ModelViewSet):
    queryset = FooterSection.objects.filter(is_active=True).prefetch_related('links')
    serializer_class = FooterSectionSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        if self.request.user and self.request.user.is_staff:
            return FooterSection.objects.all().prefetch_related('links')
        return FooterSection.objects.filter(is_active=True).prefetch_related('links')


class PolicyPageViewSet(viewsets.ModelViewSet):
    queryset = PolicyPage.objects.all()
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PolicyPageDetailSerializer
        return PolicyPageListSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]


class NewsletterSubscriberViewSet(viewsets.ModelViewSet):
    queryset = NewsletterSubscriber.objects.all().order_by('-subscribed_at')
    serializer_class = NewsletterSubscriberSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def create(self, request, *args, **kwargs):
        email = request.data.get('email', '').strip().lower()
        if not email or '@' not in email:
            return Response({'detail': 'Please provide a valid email address.'}, status=status.HTTP_400_BAD_REQUEST)

        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={'is_active': True}
        )
        if not created and not subscriber.is_active:
            subscriber.is_active = True
            subscriber.save()

        return Response({
            'success': True,
            'message': 'Thank you for subscribing to StyleHub Luxe updates & private sales!',
            'email': email
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def footer_data_view(request):
    """
    Returns complete aggregate footer payload in 1 call (cached for 10 minutes):
    - store_settings (phone, email, address, hours, socials, copyright)
    - sections (shop, customer care, company, legal, each with links)
    - policies (list of policy pages)
    - payment_methods & trust_badges
    """
    cached = cache.get('footer_aggregate_payload')
    if cached is not None:
        return Response(cached)

    store_obj = StoreSetting.get_settings()
    sections = FooterSection.objects.filter(is_active=True).prefetch_related('links').order_by('display_order')
    policies = PolicyPage.objects.all().order_by('title')

    payload = {
        'store_settings': StoreSettingSerializer(store_obj).data,
        'sections': FooterSectionSerializer(sections, many=True).data,
        'policies': PolicyPageListSerializer(policies, many=True).data,
        'payment_methods': [
            'Visa',
            'Mastercard',
            'UPI / GPay / PhonePe',
            'Razorpay',
            'Cash on Delivery',
        ],
        'trust_badges': [
            {'icon': 'shield', 'title': '100% Authentic Luxury', 'desc': 'Directly from verified houses'},
            {'icon': 'truck', 'title': 'Express Shipping', 'desc': 'Free insured shipping across India'},
            {'icon': 'refresh', 'title': '7-Day Easy Returns', 'desc': 'Hassle-free doorstep pickup'},
            {'icon': 'lock', 'title': 'Secure Payments', 'desc': '256-bit encrypted transactions'},
        ]
    }
    cache.set('footer_aggregate_payload', payload, 600)
    return Response(payload)



@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def admin_dashboard_stats(request):
    total_sales = Order.objects.filter(payment_status='Paid').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_orders = Order.objects.count()
    active_customers = User.objects.filter(is_staff=False).count()
    total_products = Product.objects.count()

    # Recent 5 orders
    recent_orders = Order.objects.order_by('-created_at')[:5]
    recent_orders_data = [
        {
            'id': o.id,
            'order_number': o.order_number,
            'customer': o.customer_name,
            'total_amount': str(o.total_amount),
            'status': o.order_status,
            'payment_method': o.payment_method,
            'created_at': o.created_at.strftime('%Y-%m-%d %H:%M')
        } for o in recent_orders
    ]

    # Order status breakdown
    status_counts = Order.objects.values('order_status').annotate(count=Count('id'))

    return Response({
        'total_sales': str(total_sales),
        'total_orders': total_orders,
        'active_customers': active_customers,
        'total_products': total_products,
        'recent_orders': recent_orders_data,
        'status_counts': list(status_counts)
    })
