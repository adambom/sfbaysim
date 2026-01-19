"""
Shared State and Data Structures
Common data classes used by routing algorithms.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class GridCell:
    """
    Cell in spatial grid for A* pathfinding.

    Attributes:
        lat: Latitude of cell center
        lon: Longitude of cell center
        is_land: Whether cell is on land (collision)
        neighbors: List of adjacent GridCell instances
        grid_x: Grid x-coordinate (integer)
        grid_y: Grid y-coordinate (integer)
    """
    lat: float
    lon: float
    is_land: bool
    neighbors: List['GridCell']
    grid_x: int
    grid_y: int


@dataclass
class RouteSegment:
    """
    Segment of a planned route.

    Attributes:
        start_lat: Starting latitude
        start_lon: Starting longitude
        end_lat: Ending latitude
        end_lon: Ending longitude
        heading: Heading for this segment (degrees)
        estimated_time: Estimated time to complete segment (seconds)
        estimated_vmg: Estimated VMG for this segment (knots)
    """
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    heading: float
    estimated_time: float
    estimated_vmg: float


@dataclass
class IsochronePoint:
    """
    Point on an isochrone ring.

    Attributes:
        lat: Latitude
        lon: Longitude
        time: Time to reach this point (seconds from start)
        heading: Heading used to reach this point
        parent: Previous IsochronePoint (for backtracking optimal path)
    """
    lat: float
    lon: float
    time: float
    heading: float
    parent: Optional['IsochronePoint']
