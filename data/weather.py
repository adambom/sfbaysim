"""
Weather Provider
High-level weather data provider with HRRR GRIB data and scenario overrides.
"""

from data.forecast_window import ForecastWindowManager
from data.hrrr_grid import HRRRGridData
from config import (
    FALLBACK_WIND_DIRECTION,
    FALLBACK_WIND_SPEED
)


class WeatherProvider:
    """
    Provides weather data with fallback chain:
    1. Scenario override (if set)
    2. HRRR forecast window
    3. Default constant wind
    """

    def __init__(self, start_time, source='hrrr', scenario=None):
        """
        Initialize weather provider.

        Args:
            start_time: Initial simulation time
            source: Data source ('hrrr' only)
            scenario: Optional scenario name for override
        """
        self.start_time = start_time
        self.source = source
        self.scenario_name = scenario
        self.scenario_obj = None

        # Initialize HRRR forecast window
        print("Initializing HRRR forecast window...")
        self.forecast_window = ForecastWindowManager(start_time, HRRRGridData)
        self.forecast_window.initialize()

        # Initialize scenario if provided
        if scenario and scenario != 'None':
            print(f"Loading weather scenario: {scenario}")
            from scenarios.weather_overrides import create_scenario
            self.scenario_obj = create_scenario(scenario)

    def get_wind(self, sim_time, lat, lon):
        """
        Get wind at specified time and location.

        Fallback chain:
        1. Scenario override
        2. HRRR forecast window
        3. Default constant wind

        Args:
            sim_time: Simulation datetime
            lat: Latitude
            lon: Longitude

        Returns:
            (direction, speed) tuple in degrees and knots
        """
        # 1. Scenario override (highest priority)
        if self.scenario_obj:
            return self.scenario_obj.get_wind(sim_time, lat, lon)

        # 2. Try HRRR forecast window
        if self.forecast_window:
            wind = self.forecast_window.get_wind(sim_time, lat, lon)
            if wind is not None:
                return wind

        # 3. Default constant wind (if HRRR not ready yet)
        return (FALLBACK_WIND_DIRECTION, FALLBACK_WIND_SPEED)

    def update(self, sim_time):
        """
        Update forecast windows as simulation time advances.

        Args:
            sim_time: Current simulation time
        """
        if self.forecast_window:
            self.forecast_window.update_window(sim_time)

    def get_load_progress(self):
        """
        Get loading progress for UI display.

        Returns:
            Dict with 'loaded', 'total', 'loading' keys
        """
        if self.forecast_window:
            return self.forecast_window.get_load_progress()
        else:
            return {'loaded': 0, 'total': 0, 'loading': False}

    def stop(self):
        """Stop background threads."""
        if self.forecast_window:
            self.forecast_window.stop()
