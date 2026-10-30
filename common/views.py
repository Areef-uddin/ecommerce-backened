from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Sum, Count
from .models import Banner, Notification, FAQ, ContactTicket
from .serializers import BannerSerializer, NotificationSerializer, FAQSerializer, ContactTicketSerializer
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
