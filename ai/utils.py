"""
AI Routing Utilities
Common functions shared across routing algorithms.
"""

import math
import numpy as np
from typing import Tuple, List
from core.physics import (
    bearing_between,
    angle_difference,
    calculate_vmg,
    calculate_velocity_over_ground,
    update_position,
    knots_to_ms,
    haversine_distance,
    calculate_true_wind_angle
)


def compute_vmg_for_heading(
    heading: float,
    boat_lat: float,
    boat_lon: float,
    target_lat: float,
    target_lon: float,
    wind_dir: float,
    wind_speed: float,
    polar,
    target_speed_factor: float = 1.0,
    current_u: float = 0.0,
    current_v: float = 0.0
) -> float:
    """
    Compute VMG toward target for a specific heading.

    This is the core function for VMG optimization.

    Args:
        heading: Candidate heading in degrees
        boat_lat, boat_lon: Boat position
        target_lat, target_lon: Target position
        wind_dir: Wind direction in degrees (FROM)
        wind_speed: Wind speed in knots
        polar: PolarTable instance
        target_speed_factor: Performance multiplier
        current_u, current_v: Current components in m/s

    Returns:
        VMG in knots (can be negative)
    """
    # Compute TWA for this heading
    twa = calculate_true_wind_angle(heading, wind_dir)

    # Skip in-irons zone
    if abs(twa) < 30:
        return -999.0  # Very negative VMG (invalid heading)

    # Get boat speed from polar
    boat_speed = polar.get_speed(twa, wind_speed) * target_speed_factor

    if boat_speed < 0.1:
        return -999.0  # No speed, invalid

    # Compute SOG and COG with current
    sog, cog = calculate_velocity_over_ground(heading, boat_speed, current_u, current_v)

    # Compute bearing to target
    target_bearing = bearing_between(boat_lat, boat_lon, target_lat, target_lon)

    # Calculate VMG
    vmg = calculate_vmg(sog, cog, target_bearing)

    return vmg


def sample_headings_around_current(
    context,
    center_heading: float,
    target_lat: float,
    target_lon: float,
    samples: int = 25,
    search_range: float = 20.0
) -> Tuple[float, float, List[Tuple[float, float]]]:
    """
    Sample headings around CURRENT heading (not target bearing).
    This enforces tack commitment - boat stays on current tack.

    Args:
        context: RoutingContext with boat and environment
        center_heading: Heading to center search on (typically boat.heading)
        target_lat, target_lon: Target position
        samples: Number of headings to sample
        search_range: Degrees to search on each side of center heading

    Returns:
        (best_heading, best_vmg, all_samples) tuple
    """
    boat = context.boat

    # Get wind at boat position
    wind = context.weather.get_wind(context.sim_time, boat.lat, boat.lon)
    if not wind:
        # No wind data, maintain current heading
        return center_heading, 0.0, []

    wind_dir, wind_speed = wind

    # Get current at boat position
    current_u, current_v = context.currents.get_current(context.sim_time, boat.lat, boat.lon)

    # Sample headings around current heading (NOT target bearing)
    headings = np.linspace(
        center_heading - search_range,
        center_heading + search_range,
        samples
    )

    best_heading = center_heading
    best_vmg = -float('inf')
    all_samples = []

    for h in headings:
        h = h % 360

        # Compute VMG for this heading
        vmg = compute_vmg_for_heading(
            h,
            boat.lat, boat.lon,
            target_lat, target_lon,
            wind_dir, wind_speed,
            context.polar,
            boat.target_speed_factor,
            current_u, current_v
        )

        all_samples.append((h, vmg))

        if vmg > best_vmg:
            best_vmg = vmg
            best_heading = h

    return best_heading, best_vmg, all_samples


def sample_headings_vmg(
    context,
    target_lat: float,
    target_lon: float,
    samples: int = 25,
    search_range: float = 90.0
) -> Tuple[float, float, List[Tuple[float, float]]]:
    """
    Sample headings around target bearing and return best VMG heading.

    Args:
        context: RoutingContext with boat and environment
        target_lat, target_lon: Target position
        samples: Number of headings to sample
        search_range: Degrees to search on each side of target bearing

    Returns:
        (best_heading, best_vmg, all_samples) tuple
        all_samples is list of (heading, vmg) for analysis
    """
    boat = context.boat

    # Get wind at boat position
    wind = context.weather.get_wind(context.sim_time, boat.lat, boat.lon)
    if not wind:
        # No wind data, default to heading toward target
        target_bearing = bearing_between(boat.lat, boat.lon, target_lat, target_lon)
        return target_bearing, 0.0, []

    wind_dir, wind_speed = wind

    # Get current at boat position
    current_u, current_v = context.currents.get_current(context.sim_time, boat.lat, boat.lon)

    # Compute target bearing
    target_bearing = bearing_between(boat.lat, boat.lon, target_lat, target_lon)

    # Sample headings around target bearing
    headings = np.linspace(
        target_bearing - search_range,
        target_bearing + search_range,
        samples
    )

    best_heading = target_bearing
    best_vmg = -float('inf')
    all_samples = []

    for h in headings:
        h = h % 360

        # Compute VMG for this heading
        vmg = compute_vmg_for_heading(
            h,
            boat.lat, boat.lon,
            target_lat, target_lon,
            wind_dir, wind_speed,
            context.polar,
            boat.target_speed_factor,
            current_u, current_v
        )

        all_samples.append((h, vmg))

        if vmg > best_vmg:
            best_vmg = vmg
            best_heading = h

    return best_heading, best_vmg, all_samples


def check_collision_on_heading(
    lat: float,
    lon: float,
    heading: float,
    distance_nm: float,
    geography,
    samples: int = 10
) -> bool:
    """
    Check if sailing on heading for distance will hit land.

    Samples points along the heading to detect collisions.

    Args:
        lat, lon: Starting position
        heading: Heading in degrees
        distance_nm: Distance to check in nautical miles
        geography: GeographyProvider instance
        samples: Number of points to sample along heading

    Returns:
        True if collision detected, False if clear
    """
    distance_m = distance_nm * 1852.0

    for i in range(1, samples + 1):
        frac = i / samples

        # Project position along heading
        heading_rad = math.radians(heading)
        dx_m = distance_m * frac * math.sin(heading_rad)
        dy_m = distance_m * frac * math.cos(heading_rad)

        # Convert to lat/lon offset
        dlat = dy_m / 111000
        dlon = dx_m / (111000 * math.cos(math.radians(lat)))

        test_lat = lat + dlat
        test_lon = lon + dlon

        # Check collision
        if geography.check_collision(test_lat, test_lon):
            return True  # Will hit land

    return False  # Clear path
