from django.conf import settings
from .base import BaseCourierProvider
from .demo_provider import DemoCourierProvider

def get_courier_provider() -> BaseCourierProvider:
    """
    Factory function to retrieve active courier provider.
    Defaults to DemoCourierProvider.
    In the future, provider can be swapped via settings.COURIER_PROVIDER (e.g., 'bluedart', 'shiprocket').
    """
    provider_name = getattr(settings, 'COURIER_PROVIDER', 'demo').lower()

    if provider_name == 'demo':
        return DemoCourierProvider()
    
    # Future real providers can be plugged in here:
    # elif provider_name == 'bluedart':
    #     return BlueDartCourierProvider()
    # elif provider_name == 'shiprocket':
    #     return ShiprocketCourierProvider()
    
    return DemoCourierProvider()
