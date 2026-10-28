from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseCourierProvider(ABC):
    """
    Abstract interface for Courier Logistics Providers.
    Allows seamlessly plugging in real providers (BlueDart, Shiprocket, Delhivery)
    or the DemoCourierProvider for manual simulation.
    """

    @abstractmethod
    def create_shipment(self, order) -> Dict[str, Any]:
        """Generate a tracking record and assign a courier partner."""
        pass

    @abstractmethod
    def get_tracking_info(self, tracking_number: str) -> Dict[str, Any]:
        """Fetch current tracking status, location, and milestone history."""
        pass

    @abstractmethod
    def update_status(self, tracking_number: str, new_status: str, location: str = "", note: str = "") -> Dict[str, Any]:
        """Update the tracking status and append a milestone event."""
        pass

    @abstractmethod
    def get_supported_statuses(self) -> List[str]:
        """Return the list of standard statuses supported by this provider."""
        pass
