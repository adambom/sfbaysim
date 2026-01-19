"""
Base Router - Abstract Interface for AI Routing Algorithms
Defines the contract that all routing algorithms must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class RoutingContext:
    """
    Context passed to routing algorithms containing all available information.

    Attributes:
        boat: Current boat instance
        sim_time: Current simulation datetime
        waypoints: Shared course waypoints (list of dicts)
        weather: WeatherProvider instance
        currents: CurrentProvider instance
        geography: GeographyProvider instance
        polar: PolarTable instance
    """
    boat: Any  # Boat instance
    sim_time: Any  # datetime
    waypoints: list  # List of waypoint dicts
    weather: Any  # WeatherProvider
    currents: Any  # CurrentProvider
    geography: Any  # GeographyProvider
    polar: Any  # PolarTable


class BaseRouter(ABC):
    """
    Abstract base class for all routing algorithms.

    Subclasses must implement:
    - compute_heading(): Decide which heading to steer
    - should_tack(): Decide when to tack through wind
    - should_gybe(): Decide when to gybe downwind
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize router with configuration.

        Args:
            config: Algorithm-specific configuration dict
        """
        self.config = config if config is not None else {}
        self.state = {}  # Algorithm-specific state between calls

    @abstractmethod
    def compute_heading(self, context: RoutingContext) -> float:
        """
        Compute desired heading for next time step.

        Called every physics update (1 Hz) to determine heading.

        Args:
            context: RoutingContext with boat state and environment

        Returns:
            Desired heading in degrees (0-360)
        """
        pass

    @abstractmethod
    def should_tack(self, context: RoutingContext) -> bool:
        """
        Decide if boat should tack through the wind.

        Called before compute_heading() to check for tacking.

        Args:
            context: RoutingContext

        Returns:
            True if should tack, False otherwise
        """
        pass

    @abstractmethod
    def should_gybe(self, context: RoutingContext) -> bool:
        """
        Decide if boat should gybe downwind.

        Called before compute_heading() to check for gybing.

        Args:
            context: RoutingContext

        Returns:
            True if should gybe, False otherwise
        """
        pass

    def reset_state(self):
        """
        Reset any internal state.

        Called when course changes or router is reassigned.
        """
        self.state = {}

    def get_name(self) -> str:
        """
        Return human-readable router name.

        Returns:
            Router name string
        """
        return self.__class__.__name__
