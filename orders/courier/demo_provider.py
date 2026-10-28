from datetime import timedelta
from django.utils import timezone
from .base import BaseCourierProvider
from ..models import (
    ShipmentTracking,
    TrackingMilestone,
    TRACKING_STAGES_CONFIG,
    Order,
    OrderTimeline,
)

class DemoCourierProvider(BaseCourierProvider):
    """
    Demo Logistics Provider simulating real courier milestones locally.
    Does not require external APIs, GPS or billing.
    """

    def get_supported_statuses(self):
        return [cfg['status'] for cfg in TRACKING_STAGES_CONFIG]

    def create_shipment(self, order: Order) -> ShipmentTracking:
        tracking_number = f"TEST-FASH-{1000 + order.id}"
        
        shipment, created = ShipmentTracking.objects.get_or_create(
            order=order,
            defaults={
                'tracking_number': tracking_number,
                'courier_name': order.courier_name or 'StyleHub Express',
                'is_demo_mode': False,
                'current_status': order.order_status if order.order_status in self.get_supported_statuses() else 'Order Placed',
                'current_location': order.current_location or 'Bengaluru Fulfillment Center',
                'estimated_delivery': order.estimated_delivery or '31 Oct - 03 Nov',
                'delivery_person_name': order.delivery_partner_name or 'Rahul Kumar',
                'delivery_person_phone': order.delivery_partner_phone or '+91 9876543210',
                'delivery_partner_rating': order.delivery_partner_rating or 4.8,
                'delivery_vehicle_number': order.delivery_partner_vehicle or 'KA-01-SH-4421',
            }
        )

        # Create or update 7 milestones
        now = timezone.now()
        statuses = self.get_supported_statuses()
        try:
            curr_idx = statuses.index(shipment.current_status)
        except ValueError:
            curr_idx = 0

        for cfg in TRACKING_STAGES_CONFIG:
            idx = cfg['order_index']
            is_done = idx <= curr_idx
            
            # Simulated realistic timestamp
            if is_done:
                ts = now - timedelta(hours=(curr_idx - idx) * 5)
            else:
                ts = None

            TrackingMilestone.objects.update_or_create(
                shipment=shipment,
                status_step=cfg['status'],
                defaults={
                    'title': cfg['title'],
                    'location': cfg['location'],
                    'description': cfg['description'],
                    'timestamp': ts,
                    'is_completed': is_done,
                    'order_index': idx,
                }
            )

        # Sync OrderTimeline for backward compatibility
        self._sync_order_timeline(order, curr_idx)

        return shipment

    def update_status(self, tracking_number: str, new_status: str, location: str = "", note: str = "") -> ShipmentTracking:
        shipment = ShipmentTracking.objects.filter(tracking_number=tracking_number).select_related('order').first()
        if not shipment:
            raise ValueError(f"Shipment with tracking number {tracking_number} not found.")

        statuses = self.get_supported_statuses()
        if new_status not in statuses:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of: {statuses}")

        target_idx = statuses.index(new_status)
        now = timezone.now()

        shipment.current_status = new_status
        if location:
            shipment.current_location = location
        else:
            # Default to location of target stage
            stage_cfg = TRACKING_STAGES_CONFIG[target_idx]
            shipment.current_location = stage_cfg['location']
        shipment.save()

        # Update milestones
        milestones = shipment.milestones.all().order_index_ordered() if hasattr(shipment.milestones.all(), 'order_index_ordered') else shipment.milestones.all().order_by('order_index')
        for m in milestones:
            if m.order_index <= target_idx:
                m.is_completed = True
                if not m.timestamp:
                    m.timestamp = now
                if m.order_index == target_idx:
                    m.timestamp = now
                    if location:
                        m.location = location
                    if note:
                        m.description = note
            else:
                m.is_completed = False
                m.timestamp = None
            m.save()

        # Update linked order
        order = shipment.order
        order.order_status = new_status
        order.save()

        # Sync OrderTimeline
        self._sync_order_timeline(order, target_idx)

        return shipment

    def get_tracking_info(self, tracking_number: str) -> dict:
        shipment = ShipmentTracking.objects.filter(tracking_number=tracking_number).select_related('order').prefetch_related('milestones').first()
        if not shipment:
            return None

        milestones_data = []
        for m in shipment.milestones.all().order_by('order_index'):
            milestones_data.append({
                'id': m.id,
                'status': m.status_step,
                'title': m.title,
                'location': m.location,
                'description': m.description,
                'timestamp': m.timestamp.isoformat() if m.timestamp else None,
                'date_formatted': m.timestamp.strftime("%d %b, %I:%M %p") if m.timestamp else "Expected",
                'is_completed': m.is_completed,
                'order_index': m.order_index,
            })

        return {
            'tracking_number': shipment.tracking_number,
            'order_id': shipment.order.id,
            'order_number': shipment.order.order_number,
            'courier_name': shipment.courier_name,
            'is_demo_mode': shipment.is_demo_mode,
            'current_status': shipment.current_status,
            'current_location': shipment.current_location,
            'estimated_delivery': shipment.estimated_delivery,
            'delivery_partner': {
                'name': shipment.delivery_person_name,
                'phone': shipment.delivery_person_phone,
                'rating': float(shipment.delivery_partner_rating),
                'vehicle': shipment.delivery_vehicle_number,
            },
            'delivery_address': shipment.order.delivery_address,
            'customer_name': shipment.order.customer_name,
            'created_at': shipment.created_at.isoformat(),
            'updated_at': shipment.updated_at.isoformat(),
            'milestones': milestones_data,
        }

    def _sync_order_timeline(self, order: Order, current_index: int):
        """Keep OrderTimeline in sync with the 7 stages so legacy views continue to work."""
        now = timezone.now()
        for cfg in TRACKING_STAGES_CONFIG:
            idx = cfg['order_index']
            is_done = idx <= current_index
            date_str = now.strftime("%d %b, %I:%M %p") if is_done else "Pending"

            OrderTimeline.objects.update_or_create(
                order=order,
                order_index=idx,
                defaults={
                    'status_step': cfg['status'],
                    'date_text': date_str,
                    'is_completed': is_done,
                }
            )
