"""
Boat State Management
Central class that manages boat position, velocity, and sailing state.
Integrates physics and polar table to simulate boat behavior.
"""

import math
from core.physics import (
    calculate_true_wind_angle,
    calculate_apparent_wind,
    calculate_velocity_over_ground,
    calculate_vmg,
    update_position,
    bearing_between,
    haversine_distance,
    normalize_angle,
    vector_from_angle_magnitude,
    knots_to_ms
)
from config import IN_IRONS_ANGLE, IN_IRONS_SPEED_KTS, TACK_ANGLE_OFFSET, GYBE_ANGLE_OFFSET


class Boat:
    """
    Represents a sailing boat with position, velocity, and performance characteristics.
    """

    def __init__(self, polar_table, lat, lon, heading, target_speed_factor=1.0, name="Boat", color=(255, 0, 0)):
        """
        Initialize boat at given position and heading.

        Args:
            polar_table: PolarTable instance for boat performance
            lat: Initial latitude in degrees
            lon: Initial longitude in degrees
            heading: Initial heading in degrees (0=North, clockwise)
            target_speed_factor: Performance multiplier (0.0-1.0) for non-ideal conditions
            name: Boat name for display
            color: RGB tuple for boat color
        """
        # Polar performance data
        self.polar = polar_table
        self.target_speed_factor = target_speed_factor  # Performance multiplier

        # Identification
        self.name = name
        self.color = color

        # AI routing
        self.ai_router = None  # BaseRouter instance
        self.is_ai_controlled = False  # Whether AI controls this boat

        # Position
        self.lat = lat
        self.lon = lon
        self.heading = normalize_angle(heading)

        # Velocities
        self.boat_speed = 0.0  # Boat speed through water (knots)
        self.sog = 0.0  # Speed Over Ground (knots)
        self.cog = 0.0  # Course Over Ground (degrees)

        # Wind state
        self.twa = 0.0  # True Wind Angle (degrees, -180 to 180)
        self.tws = 0.0  # True Wind Speed (knots)
        self.awa = 0.0  # Apparent Wind Angle (degrees)
        self.aws = 0.0  # Apparent Wind Speed (knots)

        # Current state
        self.current_u = 0.0  # East component (m/s)
        self.current_v = 0.0  # North component (m/s)

        # Navigation
        self.waypoints = []  # List of {'lat': ..., 'lon': ..., 'name': ...}
        self.breadcrumbs = []  # List of (lat, lon) tuples for track
        self.last_breadcrumb_time = 0.0  # Time since last breadcrumb

        # Statistics
        self.distance_nm = 0.0  # Total distance traveled (nautical miles)
        self.elapsed_time = 0.0  # Elapsed simulation time in seconds

        # Racing - current waypoint index in shared course
        self.current_waypoint_index = 0  # Which mark boat is heading toward
        self.marks_rounded = 0  # How many marks have been rounded

        print(f"Boat initialized at ({lat:.4f}, {lon:.4f}), heading {heading:.0f}°")

    def update(self, dt, wind_direction, wind_speed, current_u, current_v):
        """
        Main physics update - called every fixed time step (1 second).

        Args:
            dt: Time step in seconds (should be 1.0)
            wind_direction: Wind direction in degrees (FROM)
            wind_speed: Wind speed in knots
            current_u: Current east component in m/s
            current_v: Current north component in m/s
        """
        # 1. Calculate True Wind Angle
        self.twa = calculate_true_wind_angle(self.heading, wind_direction)
        self.tws = wind_speed

        # 2. Check if in irons (too close to wind)
        if abs(self.twa) < IN_IRONS_ANGLE:
            # Boat nearly stops when pointing too close to wind
            self.boat_speed = IN_IRONS_SPEED_KTS
        else:
            # 3. Lookup boat speed from polar table and apply target speed factor
            polar_speed = self.polar.get_speed(self.twa, self.tws)
            self.boat_speed = polar_speed * self.target_speed_factor

        # 4. Calculate apparent wind (what boat "feels")
        self.awa, self.aws = calculate_apparent_wind(
            self.heading,
            self.boat_speed,
            wind_direction,
            wind_speed
        )

        # 5. Store current
        self.current_u = current_u
        self.current_v = current_v

        # 6. Calculate velocity over ground (boat + current)
        self.sog, self.cog = calculate_velocity_over_ground(
            self.heading,
            self.boat_speed,
            current_u,
            current_v
        )

        # 7. Update position (integrate velocity over time step)
        # Convert boat speed to m/s and get velocity vector
        boat_speed_ms = knots_to_ms(self.boat_speed)
        boat_vx, boat_vy = vector_from_angle_magnitude(self.heading, boat_speed_ms)

        # Add current (already in m/s)
        total_vx = boat_vx + current_u
        total_vy = boat_vy + current_v

        # Update position
        self.lat, self.lon = update_position(self.lat, self.lon, total_vx, total_vy, dt)

        # 8. Update distance traveled and elapsed time
        distance_this_step = self.sog * (dt / 3600.0)  # Convert hours to seconds
        self.distance_nm += distance_this_step
        self.elapsed_time += dt

    def add_breadcrumb(self):
        """Add current position to breadcrumb trail."""
        self.breadcrumbs.append((self.lat, self.lon))

    def adjust_heading(self, delta_degrees):
        """
        Adjust boat heading by given amount.

        Args:
            delta_degrees: Change in heading (positive = turn right/starboard)
        """
        self.heading = normalize_angle(self.heading + delta_degrees)

    def tack(self):
        """
        Tack through the wind (turn bow through wind to opposite tack).
        Maintains current TWA magnitude but switches from port to starboard or vice versa.

        Example: If sailing at TWA -50° (port tack), tacking puts you at TWA +50° (starboard tack)
        """
        # Calculate current wind direction
        # TWA is the relative angle: heading + TWA = wind direction
        wind_dir = normalize_angle(self.heading + self.twa)

        # Get absolute TWA (maintain this angle magnitude on opposite tack)
        twa_abs = abs(self.twa)

        # Flip to opposite tack with same TWA magnitude
        # Port tack (TWA < 0) → Starboard tack (TWA > 0): new_heading = wind_dir - twa_abs
        # Starboard tack (TWA > 0) → Port tack (TWA < 0): new_heading = wind_dir + twa_abs
        if self.twa < 0:  # Currently on port tack (wind from left)
            # Tack to starboard tack (wind from right)
            new_heading = normalize_angle(wind_dir - twa_abs)
        else:  # Currently on starboard tack (wind from right)
            # Tack to port tack (wind from left)
            new_heading = normalize_angle(wind_dir + twa_abs)

        old_twa = self.twa
        self.heading = new_heading
        print(f"Tacked: TWA {old_twa:.0f}° → heading {new_heading:.0f}°")

    def gybe(self):
        """
        Gybe (or jibe) - turn stern through the wind to opposite tack.
        Maintains current TWA magnitude but switches tacks (used when sailing downwind).
        """
        # Calculate current wind direction
        wind_dir = normalize_angle(self.heading + self.twa)

        # Get absolute TWA (maintain this angle on opposite tack)
        twa_abs = abs(self.twa)

        # Determine new heading on opposite tack
        # Switch from port to starboard or vice versa, maintaining TWA magnitude
        if self.twa > 0:  # Wind from starboard
            # Gybe to port tack
            new_heading = normalize_angle(wind_dir - twa_abs)
        else:  # Wind from port
            # Gybe to starboard tack
            new_heading = normalize_angle(wind_dir + twa_abs)

        old_twa = self.twa
        self.heading = new_heading
        print(f"Gybed: TWA {old_twa:.0f}° → heading {new_heading:.0f}°")

    def add_waypoint(self, lat, lon, name=""):
        """
        Add a navigation waypoint.

        Args:
            lat: Waypoint latitude
            lon: Waypoint longitude
            name: Optional name for waypoint
        """
        if not name:
            name = f"Mark {len(self.waypoints) + 1}"

        self.waypoints.append({
            'lat': lat,
            'lon': lon,
            'name': name
        })
        print(f"Waypoint added: {name} at ({lat:.4f}, {lon:.4f})")

    def clear_waypoints(self):
        """Remove all waypoints."""
        self.waypoints.clear()
        print("All waypoints cleared")

    def adjust_target_speed_factor(self, delta):
        """
        Adjust target speed factor.

        Args:
            delta: Change in factor (e.g., 0.05 for +5%)
        """
        self.target_speed_factor = max(0.1, min(1.0, self.target_speed_factor + delta))
        print(f"Target speed factor: {self.target_speed_factor*100:.0f}%")

    def get_distance_to_waypoint(self, waypoint_index):
        """
        Get distance to specific waypoint.

        Args:
            waypoint_index: Index of waypoint in waypoints list

        Returns:
            Distance in nautical miles, or None if invalid index
        """
        if waypoint_index < 0 or waypoint_index >= len(self.waypoints):
            return None

        wp = self.waypoints[waypoint_index]
        return haversine_distance(self.lat, self.lon, wp['lat'], wp['lon'])

    def get_bearing_to_waypoint(self, waypoint_index):
        """
        Get bearing to specific waypoint.

        Args:
            waypoint_index: Index of waypoint in waypoints list

        Returns:
            Bearing in degrees, or None if invalid index
        """
        if waypoint_index < 0 or waypoint_index >= len(self.waypoints):
            return None

        wp = self.waypoints[waypoint_index]
        return bearing_between(self.lat, self.lon, wp['lat'], wp['lon'])

    def get_vmg_to_waypoint(self, waypoint_index):
        """
        Get Velocity Made Good toward specific waypoint.

        Args:
            waypoint_index: Index of waypoint in waypoints list

        Returns:
            VMG in knots, or 0.0 if invalid index
        """
        if waypoint_index < 0 or waypoint_index >= len(self.waypoints):
            return 0.0

        target_bearing = self.get_bearing_to_waypoint(waypoint_index)
        if target_bearing is None:
            return 0.0

        return calculate_vmg(self.sog, self.cog, target_bearing)

    def get_vmg_upwind(self):
        """
        Get VMG upwind (toward the wind direction).
        Positive = making progress toward wind.

        Returns:
            VMG in knots
        """
        # Calculate true wind direction from TWA and heading
        wind_direction = normalize_angle(self.heading + self.twa)
        return calculate_vmg(self.sog, self.cog, wind_direction)

    def check_mark_rounding(self, waypoints, rounding_distance_nm=0.02):
        """
        Check if boat has rounded the current target mark.

        Args:
            waypoints: Shared waypoints list
            rounding_distance_nm: Distance to mark considered "rounded" (default ~40m)

        Returns:
            True if mark was rounded (and index advanced), False otherwise
        """
        if not waypoints or self.current_waypoint_index >= len(waypoints):
            return False

        # Get current target mark
        mark = waypoints[self.current_waypoint_index]
        distance = haversine_distance(self.lat, self.lon, mark['lat'], mark['lon'])

        # Check if within rounding distance
        if distance <= rounding_distance_nm:
            print(f"{self.name} rounded {mark['name']} ({self.marks_rounded + 1}/{len(waypoints)})")
            self.marks_rounded += 1
            self.current_waypoint_index += 1

            # Check if finished course
            if self.current_waypoint_index >= len(waypoints):
                print(f"*** {self.name} FINISHED! Time: {self.elapsed_time:.0f}s, Distance: {self.distance_nm:.2f}nm ***")
                return True

            return True

        return False

    def get_vmg_to_current_mark(self, waypoints):
        """
        Get VMG to current target mark in course.

        Args:
            waypoints: Shared waypoints list

        Returns:
            VMG in knots, or 0.0 if no current mark
        """
        if not waypoints or self.current_waypoint_index >= len(waypoints):
            return 0.0

        mark = waypoints[self.current_waypoint_index]
        target_bearing = bearing_between(self.lat, self.lon, mark['lat'], mark['lon'])
        return calculate_vmg(self.sog, self.cog, target_bearing)

    def get_distance_to_current_mark(self, waypoints):
        """
        Get distance to current target mark.

        Args:
            waypoints: Shared waypoints list

        Returns:
            Distance in nm, or None if no current mark
        """
        if not waypoints or self.current_waypoint_index >= len(waypoints):
            return None

        mark = waypoints[self.current_waypoint_index]
        return haversine_distance(self.lat, self.lon, mark['lat'], mark['lon'])

    def is_on_port_tack(self):
        """
        Check if boat is on port tack (wind from left/port side).

        Returns:
            True if on port tack, False if on starboard tack
        """
        return self.twa < 0

    def is_on_starboard_tack(self):
        """
        Check if boat is on starboard tack (wind from right/starboard side).

        Returns:
            True if on starboard tack, False if on port tack
        """
        return self.twa > 0

    def get_state_dict(self):
        """
        Get complete boat state as dictionary (for replay/logging).

        Returns:
            Dictionary with all boat state
        """
        return {
            'position': {'lat': self.lat, 'lon': self.lon},
            'heading': self.heading,
            'velocities': {
                'boat_speed': self.boat_speed,
                'sog': self.sog,
                'cog': self.cog
            },
            'wind': {
                'twa': self.twa,
                'tws': self.tws,
                'awa': self.awa,
                'aws': self.aws
            },
            'current': {
                'u': self.current_u,
                'v': self.current_v
            },
            'stats': {
                'distance_nm': self.distance_nm
            }
        }

    def set_ai_router(self, router):
        """
        Set AI router for this boat.

        Args:
            router: BaseRouter instance or None to disable AI
        """
        self.ai_router = router
        self.is_ai_controlled = (router is not None)

        if router:
            print(f"{self.name} AI enabled: {router.get_name()}")
        else:
            print(f"{self.name} AI disabled")

    def toggle_ai_control(self):
        """Toggle AI control on/off."""
        self.is_ai_controlled = not self.is_ai_controlled
        status = "enabled" if self.is_ai_controlled else "disabled"
        print(f"{self.name} AI control {status}")

    def __repr__(self):
        return (f"Boat(pos=({self.lat:.4f}, {self.lon:.4f}), "
                f"heading={self.heading:.0f}°, speed={self.boat_speed:.1f} kts)")
