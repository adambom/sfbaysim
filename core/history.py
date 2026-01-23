"""
Simulation History - Time Rewind Feature
Captures and restores simulation state snapshots for time travel functionality.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import deque


@dataclass
class BoatSnapshot:
    """Single boat's state at a point in time."""
    lat: float
    lon: float
    heading: float
    boat_speed: float
    sog: float
    cog: float
    twa: float
    tws: float
    awa: float
    aws: float
    current_u: float
    current_v: float
    current_waypoint_index: int
    marks_rounded: int
    distance_nm: float
    elapsed_time: float
    breadcrumbs: List[Tuple[float, float]]
    is_ai_controlled: bool
    # Store identification for restoration
    name: str
    color: Tuple[int, int, int]
    target_speed_factor: float


@dataclass
class SimulationSnapshot:
    """Complete simulation state at a point in time."""
    sim_time: datetime
    accumulator: float
    breadcrumb_timer: float
    boats: List[BoatSnapshot]
    waypoints: List[Dict]


class SimulationHistory:
    """
    Ring buffer of snapshots with restore capabilities.
    Allows rewinding to any captured point in simulation history.
    """

    def __init__(self, max_snapshots: int = 360):
        """
        Initialize history buffer.

        Args:
            max_snapshots: Maximum number of snapshots to keep (default 360 = 3 hours at 30s intervals)
        """
        self.snapshots: deque = deque(maxlen=max_snapshots)
        self.current_index: int = -1  # -1 means "at present" (no rewind active)
        self._present_index: int = -1  # Index of most recent snapshot

    def capture(self, sim_time: datetime, accumulator: float, breadcrumb_timer: float,
                boats: list, waypoints: list) -> None:
        """
        Capture current simulation state as a snapshot.

        Args:
            sim_time: Current simulation datetime
            accumulator: Physics accumulator value
            breadcrumb_timer: Breadcrumb timer value
            boats: List of Boat instances
            waypoints: Shared waypoints list
        """
        # If we're viewing a past state and capture is called, truncate future history
        if self.current_index >= 0 and self.current_index < len(self.snapshots) - 1:
            # Keep only snapshots up to and including current position
            while len(self.snapshots) > self.current_index + 1:
                self.snapshots.pop()

        # Create boat snapshots
        boat_snapshots = []
        for boat in boats:
            snapshot = BoatSnapshot(
                lat=boat.lat,
                lon=boat.lon,
                heading=boat.heading,
                boat_speed=boat.boat_speed,
                sog=boat.sog,
                cog=boat.cog,
                twa=boat.twa,
                tws=boat.tws,
                awa=boat.awa,
                aws=boat.aws,
                current_u=boat.current_u,
                current_v=boat.current_v,
                current_waypoint_index=boat.current_waypoint_index,
                marks_rounded=boat.marks_rounded,
                distance_nm=boat.distance_nm,
                elapsed_time=boat.elapsed_time,
                breadcrumbs=list(boat.breadcrumbs),  # Copy the list
                is_ai_controlled=boat.is_ai_controlled,
                name=boat.name,
                color=boat.color,
                target_speed_factor=boat.target_speed_factor
            )
            boat_snapshots.append(snapshot)

        # Create simulation snapshot
        snapshot = SimulationSnapshot(
            sim_time=sim_time,
            accumulator=accumulator,
            breadcrumb_timer=breadcrumb_timer,
            boats=boat_snapshots,
            waypoints=[dict(wp) for wp in waypoints]  # Deep copy waypoints
        )

        self.snapshots.append(snapshot)
        self._present_index = len(self.snapshots) - 1
        self.current_index = -1  # Stay at present

    def restore(self, index: int, boats: list) -> Optional[Tuple[datetime, float, float, List[Dict]]]:
        """
        Restore simulation state from snapshot at given index.

        Args:
            index: Snapshot index to restore
            boats: List of Boat instances to restore state to

        Returns:
            Tuple of (sim_time, accumulator, breadcrumb_timer, waypoints) or None if invalid
        """
        if index < 0 or index >= len(self.snapshots):
            return None

        snapshot = self.snapshots[index]
        self.current_index = index

        # Restore boat states
        for i, boat_snap in enumerate(snapshot.boats):
            if i < len(boats):
                boat = boats[i]
                boat.lat = boat_snap.lat
                boat.lon = boat_snap.lon
                boat.heading = boat_snap.heading
                boat.boat_speed = boat_snap.boat_speed
                boat.sog = boat_snap.sog
                boat.cog = boat_snap.cog
                boat.twa = boat_snap.twa
                boat.tws = boat_snap.tws
                boat.awa = boat_snap.awa
                boat.aws = boat_snap.aws
                boat.current_u = boat_snap.current_u
                boat.current_v = boat_snap.current_v
                boat.current_waypoint_index = boat_snap.current_waypoint_index
                boat.marks_rounded = boat_snap.marks_rounded
                boat.distance_nm = boat_snap.distance_nm
                boat.elapsed_time = boat_snap.elapsed_time
                boat.breadcrumbs = list(boat_snap.breadcrumbs)

        return (snapshot.sim_time, snapshot.accumulator,
                snapshot.breadcrumb_timer, snapshot.waypoints)

    def step_backward(self, boats: list) -> Optional[Tuple[datetime, float, float, List[Dict]]]:
        """
        Step backward one snapshot.

        Args:
            boats: List of Boat instances to restore state to

        Returns:
            Tuple of (sim_time, accumulator, breadcrumb_timer, waypoints) or None if at oldest
        """
        if len(self.snapshots) == 0:
            return None

        if self.current_index == -1:
            # Currently at present, go to most recent snapshot
            target_index = len(self.snapshots) - 1
        else:
            # Go back one more
            target_index = self.current_index - 1

        if target_index < 0:
            return None  # Already at oldest

        return self.restore(target_index, boats)

    def step_forward(self, boats: list) -> Optional[Tuple[datetime, float, float, List[Dict]]]:
        """
        Step forward one snapshot.

        Args:
            boats: List of Boat instances to restore state to

        Returns:
            Tuple of (sim_time, accumulator, breadcrumb_timer, waypoints) or None if at present
        """
        if len(self.snapshots) == 0 or self.current_index == -1:
            return None  # Already at present or no history

        target_index = self.current_index + 1

        if target_index >= len(self.snapshots):
            # Reached present
            self.current_index = -1
            return None

        return self.restore(target_index, boats)

    def jump_to_oldest(self, boats: list) -> Optional[Tuple[datetime, float, float, List[Dict]]]:
        """
        Jump to oldest snapshot.

        Args:
            boats: List of Boat instances to restore state to

        Returns:
            Tuple of (sim_time, accumulator, breadcrumb_timer, waypoints) or None if no history
        """
        if len(self.snapshots) == 0:
            return None

        return self.restore(0, boats)

    def jump_to_present(self, boats: list) -> Optional[Tuple[datetime, float, float, List[Dict]]]:
        """
        Jump to most recent snapshot (present).

        Args:
            boats: List of Boat instances to restore state to

        Returns:
            Tuple of (sim_time, accumulator, breadcrumb_timer, waypoints) or None if no history
        """
        if len(self.snapshots) == 0:
            return None

        self.current_index = -1
        return self.restore(len(self.snapshots) - 1, boats)

    def jump_to_index(self, index: int, boats: list) -> Optional[Tuple[datetime, float, float, List[Dict]]]:
        """
        Jump to specific snapshot index (for slider scrubbing).

        Args:
            index: Target snapshot index
            boats: List of Boat instances to restore state to

        Returns:
            Tuple of (sim_time, accumulator, breadcrumb_timer, waypoints) or None if invalid
        """
        return self.restore(index, boats)

    def is_at_present(self) -> bool:
        """Check if currently viewing present (not rewound)."""
        return self.current_index == -1 or self.current_index == len(self.snapshots) - 1

    def get_time_offset_seconds(self) -> float:
        """
        Get time offset from present in seconds.

        Returns:
            Negative seconds if in past, 0 if at present
        """
        if self.current_index == -1 or len(self.snapshots) == 0:
            return 0.0

        current_snap = self.snapshots[self.current_index]
        present_snap = self.snapshots[-1]

        delta = current_snap.sim_time - present_snap.sim_time
        return delta.total_seconds()

    def get_time_range(self) -> Optional[Tuple[datetime, datetime]]:
        """
        Get time range of available history.

        Returns:
            Tuple of (oldest_time, newest_time) or None if no history
        """
        if len(self.snapshots) == 0:
            return None

        return (self.snapshots[0].sim_time, self.snapshots[-1].sim_time)

    def get_current_time(self) -> Optional[datetime]:
        """
        Get time of currently viewed snapshot.

        Returns:
            datetime of current snapshot, or None if at present/no history
        """
        if self.current_index == -1 or len(self.snapshots) == 0:
            return None

        return self.snapshots[self.current_index].sim_time

    def get_snapshot_count(self) -> int:
        """Get total number of snapshots."""
        return len(self.snapshots)

    def get_current_index(self) -> int:
        """
        Get current viewing index.

        Returns:
            Current index, or len(snapshots)-1 if at present
        """
        if self.current_index == -1:
            return len(self.snapshots) - 1 if len(self.snapshots) > 0 else 0
        return self.current_index

    def truncate_future(self) -> None:
        """
        Truncate history after current position.
        Called when resuming from a rewound state.
        """
        if self.current_index >= 0 and self.current_index < len(self.snapshots) - 1:
            # Keep only snapshots up to current position
            while len(self.snapshots) > self.current_index + 1:
                self.snapshots.pop()

        # Return to "present" mode
        self.current_index = -1
        self._present_index = len(self.snapshots) - 1

    def clear(self) -> None:
        """Clear all history."""
        self.snapshots.clear()
        self.current_index = -1
        self._present_index = -1
