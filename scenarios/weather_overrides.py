"""
Weather Override Scenarios
Provides test scenarios with controllable wind patterns.
"""

import math
from datetime import datetime, timezone
from config import SCENARIOS


class WeatherScenario:
    """
    Base class for weather scenarios.
    Subclasses implement different wind patterns.
    """

    def get_wind(self, timestamp, lat, lon):
        """
        Get wind at specified time and location.

        Args:
            timestamp: Simulation datetime
            lat: Latitude
            lon: Longitude

        Returns:
            (direction, speed) tuple in degrees and knots
        """
        raise NotImplementedError("Subclasses must implement get_wind()")


class ConstantWindScenario(WeatherScenario):
    """
    Constant wind from a single direction at constant speed.
    """

    def __init__(self, direction, speed):
        """
        Initialize constant wind scenario.

        Args:
            direction: Wind direction in degrees (FROM)
            speed: Wind speed in knots
        """
        self.direction = direction
        self.speed = speed

    def get_wind(self, timestamp, lat, lon):
        """Return constant wind regardless of time/location."""
        return (self.direction, self.speed)


class VariableWindScenario(WeatherScenario):
    """
    Wind that oscillates in direction over time.
    Useful for testing tacking strategies.
    """

    def __init__(self, base_direction, base_speed, delta_degrees, period_seconds):
        """
        Initialize variable wind scenario.

        Args:
            base_direction: Base wind direction in degrees
            base_speed: Wind speed in knots
            delta_degrees: Oscillation amplitude (±degrees)
            period_seconds: Oscillation period in seconds
        """
        self.base_direction = base_direction
        self.base_speed = base_speed
        self.delta_degrees = delta_degrees
        self.period_seconds = period_seconds
        self.start_time = datetime.now(datetime.UTC).replace(tzinfo=None)

    def get_wind(self, timestamp, lat, lon):
        """
        Return wind with oscillating direction.

        Direction oscillates as: base ± delta * sin(2π * t / period)
        """
        # Calculate elapsed time
        elapsed_seconds = (timestamp - self.start_time).total_seconds()

        # Calculate phase (0 to 1)
        phase = (elapsed_seconds % self.period_seconds) / self.period_seconds

        # Sine wave oscillation
        delta = self.delta_degrees * math.sin(2 * math.pi * phase)

        # Apply to base direction
        direction = (self.base_direction + delta) % 360

        return (direction, self.base_speed)


class SpatialWindScenario(WeatherScenario):
    """
    Wind that varies by location.
    Simulates wind shadows near land and funneling effects.
    """

    def __init__(self, geography):
        """
        Initialize spatial wind scenario.

        Args:
            geography: GeographyProvider instance
        """
        self.geography = geography
        self.base_direction = 315  # Northwest
        self.base_speed = 15  # knots

    def get_wind(self, timestamp, lat, lon):
        """
        Return wind that varies by location.

        Wind is reduced near coastline (wind shadow effect).
        """
        # Check distance to land (simplified - could be optimized)
        # For now, just use a simple latitude-based gradient

        # Central bay has full wind
        center_lat, center_lon = self.geography.get_center()

        # Distance from center
        dlat = abs(lat - center_lat)
        dlon = abs(lon - center_lon)

        # Simple model: reduce wind near edges
        edge_factor = 1.0

        if dlat > self.geography.height_deg * 0.4:
            edge_factor *= 0.7  # 30% reduction near north/south edges

        if dlon > self.geography.width_deg * 0.4:
            edge_factor *= 0.7  # 30% reduction near east/west edges

        speed = self.base_speed * edge_factor

        return (self.base_direction, speed)


def create_scenario(name):
    """
    Factory function to create scenario by name.

    Args:
        name: Scenario name from config.SCENARIOS

    Returns:
        WeatherScenario instance, or None if invalid name
    """
    if name not in SCENARIOS:
        return None

    scenario_config = SCENARIOS[name]

    if scenario_config.get('type') == 'constant':
        return ConstantWindScenario(
            scenario_config['wind_direction'],
            scenario_config['wind_speed']
        )

    elif scenario_config.get('type') == 'variable':
        return VariableWindScenario(
            scenario_config['wind_direction'],
            scenario_config['wind_speed'],
            scenario_config['delta_degrees'],
            scenario_config['period_seconds']
        )

    elif scenario_config.get('type') == 'spatial':
        # Note: geography will be passed in later
        # For now, return None (will be created in weather.py if needed)
        return None

    else:
        # 'None' scenario or unknown type
        return None
