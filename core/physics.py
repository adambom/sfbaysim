"""
Core Physics Functions for Sailing Simulation
Pure functions for vector math, wind/current calculations, and nautical utilities.
No state - all functions are side-effect free.
"""

import math
import numpy as np
from config import KNOTS_TO_MS, MS_TO_KNOTS, METERS_PER_DEGREE_LAT


# ==================== Vector Math ====================

def vector_from_angle_magnitude(angle_deg, magnitude):
    """
    Convert angle (degrees, 0=North clockwise) and magnitude to vector (x, y).

    Args:
        angle_deg: Angle in degrees (0=North, 90=East, 180=South, 270=West)
        magnitude: Magnitude of vector

    Returns:
        (x, y) tuple - x is east component, y is north component
    """
    angle_rad = math.radians(angle_deg)
    x = magnitude * math.sin(angle_rad)  # East component
    y = magnitude * math.cos(angle_rad)  # North component
    return (x, y)


def magnitude(vx, vy):
    """
    Calculate magnitude of vector.

    Args:
        vx: X component
        vy: Y component

    Returns:
        Magnitude (length) of vector
    """
    return math.sqrt(vx * vx + vy * vy)


def direction(vx, vy):
    """
    Calculate direction of vector in nautical degrees (0=North, clockwise).

    Args:
        vx: X (east) component
        vy: Y (north) component

    Returns:
        Direction in degrees [0, 360)
    """
    angle_rad = math.atan2(vx, vy)  # atan2(x, y) for nautical convention
    angle_deg = math.degrees(angle_rad)
    return normalize_angle(angle_deg)


def normalize_angle(angle):
    """
    Normalize angle to [0, 360) range.

    Args:
        angle: Angle in degrees

    Returns:
        Normalized angle in [0, 360)
    """
    return angle % 360


def angle_difference(angle1, angle2):
    """
    Calculate shortest angular distance from angle1 to angle2.
    Handles wraparound (e.g., 350° to 10° is +20°, not +340°).

    Args:
        angle1: First angle in degrees
        angle2: Second angle in degrees

    Returns:
        Difference in degrees, range [-180, 180]
        Positive = clockwise from angle1 to angle2
        Negative = counterclockwise from angle1 to angle2
    """
    diff = (angle2 - angle1 + 180) % 360 - 180
    return diff


# ==================== Wind Calculations ====================

def calculate_true_wind_angle(boat_heading, wind_direction):
    """
    Calculate True Wind Angle (TWA) - angle between boat heading and wind direction.

    Args:
        boat_heading: Boat heading in degrees (0=North, clockwise)
        wind_direction: Wind direction in degrees (direction wind is FROM)

    Returns:
        TWA in degrees, range [-180, 180]
        Positive = wind from starboard (right) side
        Negative = wind from port (left) side
    """
    return angle_difference(boat_heading, wind_direction)


def calculate_apparent_wind(boat_heading, boat_speed_kts, wind_direction, wind_speed_kts):
    """
    Calculate Apparent Wind (what the boat "feels") from true wind and boat motion.
    Apparent Wind = True Wind - Boat Velocity (vector subtraction)

    Args:
        boat_heading: Boat heading in degrees
        boat_speed_kts: Boat speed through water in knots
        wind_direction: True wind direction in degrees (FROM)
        wind_speed_kts: True wind speed in knots

    Returns:
        (AWA, AWS) tuple:
            AWA: Apparent Wind Angle in degrees [-180, 180]
            AWS: Apparent Wind Speed in knots
    """
    # Convert to m/s for calculation
    boat_speed_ms = boat_speed_kts * KNOTS_TO_MS
    wind_speed_ms = wind_speed_kts * KNOTS_TO_MS

    # Boat velocity vector (direction of motion)
    boat_vx, boat_vy = vector_from_angle_magnitude(boat_heading, boat_speed_ms)

    # Wind velocity vector (direction wind is coming FROM)
    wind_vx, wind_vy = vector_from_angle_magnitude(wind_direction, wind_speed_ms)

    # Apparent wind = True wind - Boat velocity (vector subtraction)
    apparent_vx = wind_vx - boat_vx
    apparent_vy = wind_vy - boat_vy

    # Calculate apparent wind magnitude and direction
    apparent_speed_ms = magnitude(apparent_vx, apparent_vy)
    apparent_speed_kts = apparent_speed_ms * MS_TO_KNOTS

    apparent_direction = direction(apparent_vx, apparent_vy)

    # Apparent wind angle relative to boat heading
    awa = angle_difference(boat_heading, apparent_direction)

    return (awa, apparent_speed_kts)


# ==================== Velocity and Position ====================

def calculate_velocity_over_ground(boat_heading, boat_speed_kts, current_u, current_v):
    """
    Calculate velocity over ground by combining boat velocity and current.

    Args:
        boat_heading: Boat heading in degrees
        boat_speed_kts: Boat speed through water in knots
        current_u: Current east component in m/s
        current_v: Current north component in m/s

    Returns:
        (SOG, COG) tuple:
            SOG: Speed Over Ground in knots
            COG: Course Over Ground in degrees
    """
    # Convert boat speed to m/s
    boat_speed_ms = boat_speed_kts * KNOTS_TO_MS

    # Boat velocity vector (through water)
    boat_vx, boat_vy = vector_from_angle_magnitude(boat_heading, boat_speed_ms)

    # Add current (in m/s)
    ground_vx = boat_vx + current_u
    ground_vy = boat_vy + current_v

    # Calculate speed and course over ground
    sog_ms = magnitude(ground_vx, ground_vy)
    sog_kts = sog_ms * MS_TO_KNOTS

    cog = direction(ground_vx, ground_vy)

    return (sog_kts, cog)


def calculate_vmg(sog, cog, target_bearing):
    """
    Calculate Velocity Made Good (VMG) toward a target bearing.
    VMG is the component of velocity in the direction of the target.

    Args:
        sog: Speed Over Ground in knots
        cog: Course Over Ground in degrees
        target_bearing: Target bearing in degrees

    Returns:
        VMG in knots (positive = making progress toward target)
    """
    # Angle between COG and target bearing
    angle_diff = angle_difference(cog, target_bearing)

    # VMG is the cosine component of SOG in target direction
    vmg = sog * math.cos(math.radians(angle_diff))

    return vmg


# ==================== Position Updates ====================

def update_position(lat, lon, velocity_x_ms, velocity_y_ms, dt):
    """
    Update lat/lon position based on velocity and time step.

    Args:
        lat: Current latitude in degrees
        lon: Current longitude in degrees
        velocity_x_ms: East velocity in m/s
        velocity_y_ms: North velocity in m/s
        dt: Time step in seconds

    Returns:
        (new_lat, new_lon) tuple
    """
    # Distance traveled in meters
    dx_m = velocity_x_ms * dt
    dy_m = velocity_y_ms * dt

    # Convert to degrees
    # 1 degree latitude ≈ 111 km everywhere
    # 1 degree longitude ≈ 111 km * cos(latitude)
    delta_lat = dy_m / METERS_PER_DEGREE_LAT
    delta_lon = dx_m / (METERS_PER_DEGREE_LAT * math.cos(math.radians(lat)))

    new_lat = lat + delta_lat
    new_lon = lon + delta_lon

    return (new_lat, new_lon)


# ==================== Distance and Bearing ====================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate great-circle distance between two points using Haversine formula.

    Args:
        lat1, lon1: First point in degrees
        lat2, lon2: Second point in degrees

    Returns:
        Distance in nautical miles
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)

    c = 2 * math.asin(math.sqrt(a))

    # Earth radius in meters
    earth_radius_m = 6371000

    distance_m = earth_radius_m * c

    # Convert to nautical miles (1 NM = 1852 meters)
    distance_nm = distance_m / 1852.0

    return distance_nm


def bearing_between(lat1, lon1, lat2, lon2):
    """
    Calculate initial bearing from point 1 to point 2.

    Args:
        lat1, lon1: Start point in degrees
        lat2, lon2: End point in degrees

    Returns:
        Bearing in degrees [0, 360)
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad

    # Calculate bearing
    y = math.sin(dlon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))

    bearing_rad = math.atan2(y, x)
    bearing_deg = math.degrees(bearing_rad)

    return normalize_angle(bearing_deg)


# ==================== Unit Conversions ====================

def knots_to_ms(knots):
    """Convert knots to meters per second."""
    return knots * KNOTS_TO_MS


def ms_to_knots(ms):
    """Convert meters per second to knots."""
    return ms * MS_TO_KNOTS


def meters_to_nautical_miles(meters):
    """Convert meters to nautical miles."""
    return meters / 1852.0


def nautical_miles_to_meters(nm):
    """Convert nautical miles to meters."""
    return nm * 1852.0
