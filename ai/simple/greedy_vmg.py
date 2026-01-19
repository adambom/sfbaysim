"""
Greedy VMG Router - Layline-Based Strategy
Uses proper sailing geometry with laylines.

Strategy:
1. Calculate laylines (lines at optimal upwind angle on each tack)
2. If OUTSIDE laylines (can point at mark): point directly at mark
3. If INSIDE laylines (beating upwind):
   - Sail on one tack toward the layline
   - Tack when you reach the layline
   - Sail on opposite tack to mark

This models real upwind sailing strategy correctly.
"""

import numpy as np
import random
from ai.base_router import BaseRouter, RoutingContext
from ai.utils import compute_vmg_for_heading
from core.physics import (
    bearing_between,
    calculate_true_wind_angle,
    angle_difference,
    normalize_angle
)


class GreedyVMGRouter(BaseRouter):
    """
    Layline-based VMG optimizer.

    Uses sailing geometry to determine which tack to be on.
    """

    def __init__(self, config=None):
        """
        Initialize router.

        Config parameters:
            None currently - uses polar table for optimal angles
        """
        super().__init__(config)

    def compute_heading(self, context: RoutingContext) -> float:
        """
        Compute heading using layline geometry.

        Returns:
            Desired heading in degrees
        """
        boat = context.boat

        # Check if we have a target
        if not context.waypoints or boat.current_waypoint_index >= len(context.waypoints):
            return boat.heading

        mark = context.waypoints[boat.current_waypoint_index]
        target_lat, target_lon = mark['lat'], mark['lon']

        # Get environmental data
        wind = context.weather.get_wind(context.sim_time, boat.lat, boat.lon)
        if not wind:
            return bearing_between(boat.lat, boat.lon, target_lat, target_lon)

        wind_dir, wind_speed = wind

        # Get optimal upwind angle from polar table
        optimal_twa = context.polar.get_optimal_upwind_angle(wind_speed)

        # Calculate bearing to mark
        target_bearing = bearing_between(boat.lat, boat.lon, target_lat, target_lon)

        # Calculate angle from wind to target
        wind_to_target = angle_difference(wind_dir, target_bearing)

        # Calculate layline headings (optimal upwind angles on each tack)
        port_layline_heading = (wind_dir - optimal_twa) % 360  # Port tack
        stbd_layline_heading = (wind_dir + optimal_twa) % 360  # Starboard tack

        # Check if we can point directly at the mark (outside laylines)
        # This means target is not directly upwind
        if abs(wind_to_target) > optimal_twa:
            # OUTSIDE LAYLINES - can point at mark directly
            # Just head toward it with optimal VMG
            current_u, current_v = context.currents.get_current(context.sim_time, boat.lat, boat.lon)

            # Try pointing directly at mark
            direct_twa = calculate_true_wind_angle(target_bearing, wind_dir)

            if abs(direct_twa) > 30:  # Not in irons
                return target_bearing
            else:
                # Too close to wind, use best reach angle
                if wind_to_target > 0:
                    return stbd_layline_heading
                else:
                    return port_layline_heading

        # INSIDE LAYLINES - must beat upwind
        # Determine which tack to be on based on which side we're approaching from

        # Tack commitment - once on a tack, stay on it for minimum time
        last_chosen_tack = self.state.get('chosen_tack', None)
        last_tack_change_time = self.state.get('last_tack_change_time', 0.0)
        time_on_current_tack = boat.elapsed_time - last_tack_change_time

        MINIMUM_TACK_TIME = 30.0  # Stay on tack for at least 30 seconds

        # If we recently chose a tack, commit to it
        if last_chosen_tack and time_on_current_tack < MINIMUM_TACK_TIME:
            chosen_tack = last_chosen_tack
            if chosen_tack == 'port':
                target_heading = port_layline_heading
            else:
                target_heading = stbd_layline_heading
        else:
            # Time to re-evaluate which tack
            # Generate random threshold ONCE per tack (when we first start re-evaluating)
            # This should persist until we actually change tacks
            if 'tack_threshold_degrees' not in self.state:
                # First time or after reset, generate new threshold
                self.state['tack_threshold_degrees'] = random.uniform(15.0, 45.0)
                print(f"  {boat.name} AI: new tack threshold = {self.state['tack_threshold_degrees']:.0f}°")

            CENTERLINE_THRESHOLD = self.state['tack_threshold_degrees']

            if wind_to_target < -CENTERLINE_THRESHOLD:
                # Mark clearly left of wind, use port tack
                target_heading = port_layline_heading
                chosen_tack = 'port'
            elif wind_to_target > CENTERLINE_THRESHOLD:
                # Mark clearly right of wind, use starboard tack
                target_heading = stbd_layline_heading
                chosen_tack = 'stbd'
            else:
                # Mark near centerline, stick with current tack
                if last_chosen_tack:
                    chosen_tack = last_chosen_tack
                else:
                    # No previous choice, pick based on current TWA
                    chosen_tack = 'port' if boat.twa < 0 else 'stbd'

                if chosen_tack == 'port':
                    target_heading = port_layline_heading
                else:
                    target_heading = stbd_layline_heading

            # If we changed tacks, record the time and generate NEW threshold for next tack
            if chosen_tack != last_chosen_tack:
                self.state['last_tack_change_time'] = boat.elapsed_time
                # Generate new threshold for the NEXT tack evaluation
                self.state['tack_threshold_degrees'] = random.uniform(15.0, 45.0)
                print(f"  {boat.name} AI: changing to {chosen_tack.upper()} tack (wind→mark={wind_to_target:.0f}°, used threshold={CENTERLINE_THRESHOLD:.0f}°, next={self.state['tack_threshold_degrees']:.0f}°)")

        # Store state
        self.state['chosen_tack'] = chosen_tack

        return target_heading

    def should_tack(self, context: RoutingContext) -> bool:
        """
        Never tack via this method - tacking happens through compute_heading().

        The boat "tacks" by turning from one heading to another via adjust_heading(),
        not through explicit tack() calls.
        """
        return False

    def should_gybe(self, context: RoutingContext) -> bool:
        """
        Never gybe via this method - gybing happens through compute_heading().

        The boat "gybes" by turning from one heading to another via adjust_heading().
        """
        return False

    def get_name(self) -> str:
        """Return router name."""
        return "LaylineVMG"
