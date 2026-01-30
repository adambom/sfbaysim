"""
Grid Weather and Current Providers
Generates grids of wind/current vectors for overlay visualization.
Uses caching to avoid recomputing every frame (60 FPS → once per second).
"""

import time
import math
from config import (
    VECTOR_GRID_SPACING_M,
    CURRENT_GRID_SPACING_M,
    VECTOR_CACHE_INTERVAL,
    MIN_WIND_SPEED_KTS,
    MIN_CURRENT_SPEED_KTS,
    MS_TO_KNOTS
)


class GridWeatherProvider:
    """
    Generates grid of wind vectors for overlay visualization.

    KEY OPTIMIZATION: Caches grid for VECTOR_CACHE_INTERVAL seconds.
    Without caching, would interpolate 170 points × 60 FPS = 10,200 queries/sec!
    With 1-second cache: only 170 queries/sec.
    """

    def __init__(self, weather_provider, geography):
        """
        Initialize grid weather provider.

        Args:
            weather_provider: WeatherProvider instance
            geography: GeographyProvider instance
        """
        self.weather = weather_provider
        self.geography = geography

        # Cache
        self.cache = None
        self.cache_time = None
        self.cache_sim_time = None

    def get_grid_data(self, sim_time, center_lat, center_lon, viewport_width_m, viewport_height_m,
                       angle_offset=0.0, speed_scale=1.0):
        """
        Generate grid of wind vectors in viewport.

        Args:
            sim_time: Simulation datetime
            center_lat: Viewport center latitude
            center_lon: Viewport center longitude
            viewport_width_m: Viewport width in meters
            viewport_height_m: Viewport height in meters
            angle_offset: Degrees to rotate wind direction (positive = clockwise)
            speed_scale: Multiplier for wind speed (1.0 = 100%)

        Returns:
            List of (lat, lon, direction, speed) tuples
        """
        # Check cache based on real time (not sim time)
        # This prevents regenerating grid every frame at 60 FPS
        current_time = time.time()
        if (self.cache is not None and
            self.cache_time is not None and
            (current_time - self.cache_time) < VECTOR_CACHE_INTERVAL):
            # Apply modifiers to cached data (raw data stays cached)
            if angle_offset != 0.0 or speed_scale != 1.0:
                return [
                    (lat, lon, (direction + angle_offset) % 360, speed * speed_scale)
                    for lat, lon, direction, speed in self.cache
                ]
            return self.cache

        # Generate grid points
        grid_points = []
        spacing_m = VECTOR_GRID_SPACING_M

        # Calculate grid bounds
        num_x = int(viewport_width_m / spacing_m) + 1
        num_y = int(viewport_height_m / spacing_m) + 1

        for i in range(num_y):
            # Offset from center in meters
            dy_m = (i - num_y / 2) * spacing_m

            # Convert to latitude offset
            lat = center_lat + dy_m / 111000

            for j in range(num_x):
                dx_m = (j - num_x / 2) * spacing_m

                # Convert to longitude offset (adjust for latitude)
                lon = center_lon + dx_m / (111000 * math.cos(math.radians(center_lat)))

                # Check if in bounds
                if self.geography.is_in_bounds(lat, lon):
                    grid_points.append((lat, lon))

        # Fetch wind for all points
        result = []
        for lat, lon in grid_points:
            wind = self.weather.get_wind(sim_time, lat, lon)
            if wind:
                direction, speed = wind

                # Filter out very weak winds
                if speed >= MIN_WIND_SPEED_KTS:
                    result.append((lat, lon, direction, speed))

        # Update cache
        self.cache = result
        self.cache_time = current_time
        self.cache_sim_time = sim_time

        # Debug: show cache refresh
        if not hasattr(self, '_cache_count'):
            self._cache_count = 0
        self._cache_count += 1
        if self._cache_count <= 3:
            print(f"  Wind grid refreshed: {len(result)} vectors")

        # Apply modifiers to freshly generated data
        if angle_offset != 0.0 or speed_scale != 1.0:
            return [
                (lat, lon, (direction + angle_offset) % 360, speed * speed_scale)
                for lat, lon, direction, speed in result
            ]
        return result


class GridCurrentProvider:
    """
    Generates grid of current vectors for overlay visualization.

    Similar to GridWeatherProvider but for currents.
    Uses denser grid (smaller spacing) since currents vary more spatially.
    """

    def __init__(self, current_provider, geography):
        """
        Initialize grid current provider.

        Args:
            current_provider: CurrentProvider instance
            geography: GeographyProvider instance
        """
        self.currents = current_provider
        self.geography = geography

        # Cache
        self.cache = None
        self.cache_time = None
        self.cache_sim_time = None

    def get_grid_data(self, sim_time, center_lat, center_lon, viewport_width_m, viewport_height_m):
        """
        Generate grid of current vectors in viewport.

        Args:
            sim_time: Simulation datetime
            center_lat: Viewport center latitude
            center_lon: Viewport center longitude
            viewport_width_m: Viewport width in meters
            viewport_height_m: Viewport height in meters

        Returns:
            List of (lat, lon, u, v, speed_kts, direction) tuples
        """
        # Check cache based on real time (not sim time)
        current_time = time.time()
        if (self.cache is not None and
            self.cache_time is not None and
            (current_time - self.cache_time) < VECTOR_CACHE_INTERVAL):
            return self.cache

        # Generate grid points (denser than wind)
        grid_points = []
        spacing_m = CURRENT_GRID_SPACING_M

        num_x = int(viewport_width_m / spacing_m) + 1
        num_y = int(viewport_height_m / spacing_m) + 1

        for i in range(num_y):
            dy_m = (i - num_y / 2) * spacing_m
            lat = center_lat + dy_m / 111000

            for j in range(num_x):
                dx_m = (j - num_x / 2) * spacing_m
                lon = center_lon + dx_m / (111000 * math.cos(math.radians(center_lat)))

                if self.geography.is_in_bounds(lat, lon):
                    grid_points.append((lat, lon))

        # Batch fetch currents (MUCH faster than individual queries)
        currents_uv = self.currents.get_current_batch(sim_time, grid_points)

        # Process results
        result = []
        for (lat, lon), (u, v) in zip(grid_points, currents_uv):
            # Calculate speed and direction
            speed_ms = math.sqrt(u*u + v*v)
            speed_kts = speed_ms * MS_TO_KNOTS

            # Filter out very weak currents
            if speed_kts >= MIN_CURRENT_SPEED_KTS:
                # Direction (current flows TO this direction, oceanographic convention)
                direction = math.degrees(math.atan2(u, v)) % 360

                result.append((lat, lon, u, v, speed_kts, direction))

        # Update cache
        self.cache = result
        self.cache_time = current_time
        self.cache_sim_time = sim_time

        return result
