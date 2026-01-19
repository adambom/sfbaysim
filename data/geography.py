"""
Geography Provider
Loads GeoJSON coastline data, provides collision detection and viewport queries.
Uses R-tree spatial indexing for efficient collision detection.
"""

import geopandas as gpd
from shapely.geometry import Point, box
from config import GEOJSON_PATH, COLLISION_BUFFER
import math


class GeographyProvider:
    """
    Manages geographic data (coastline) for the simulator.
    Provides collision detection and viewport culling using spatial indexing.
    """

    def __init__(self, geojson_path=GEOJSON_PATH):
        """
        Load GeoJSON coastline and build spatial index.

        Args:
            geojson_path: Path to GeoJSON file with coastline features
        """
        print(f"Loading geography from {geojson_path}...")

        # Load GeoJSON with geopandas
        self.gdf = gpd.read_file(geojson_path)

        # Build R-tree spatial index for fast queries
        self.sindex = self.gdf.sindex

        # Calculate bounds
        bounds = self.gdf.total_bounds  # [minx, miny, maxx, maxy]
        self.min_lon = bounds[0]
        self.min_lat = bounds[1]
        self.max_lon = bounds[2]
        self.max_lat = bounds[3]

        # Calculate center
        self.center_lat = (self.min_lat + self.max_lat) / 2
        self.center_lon = (self.min_lon + self.max_lon) / 2

        # Calculate dimensions in degrees
        self.width_deg = self.max_lon - self.min_lon
        self.height_deg = self.max_lat - self.min_lat

        print(f"✓ Loaded {len(self.gdf)} coastline features")
        print(f"  Bounds: ({self.min_lat:.4f}, {self.min_lon:.4f}) to ({self.max_lat:.4f}, {self.max_lon:.4f})")
        print(f"  Center: ({self.center_lat:.4f}, {self.center_lon:.4f})")

    def check_collision(self, lat, lon, buffer_deg=COLLISION_BUFFER):
        """
        Check if a point collides with land (coastline or island).

        Uses R-tree spatial index for efficient queries:
        1. Quick bounding box query to find nearby features
        2. Exact geometry intersection test

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            buffer_deg: Buffer around point in degrees (~10 meters default)

        Returns:
            True if collision (on land), False if in water
        """
        # Create point with buffer
        # Note: shapely uses (lon, lat) order (x, y)
        point = Point(lon, lat).buffer(buffer_deg)

        # R-tree query: get indices of features whose bounding boxes intersect
        possible_matches_index = list(self.sindex.intersection(point.bounds))

        if not possible_matches_index:
            return False  # No nearby features, definitely in water

        # Get actual features
        possible_matches = self.gdf.iloc[possible_matches_index]

        # Exact intersection test
        for idx, feature in possible_matches.iterrows():
            if feature.geometry.intersects(point):
                return True  # Collision!

        return False  # Clear water

    def get_visible_features(self, center_lat, center_lon, width_m, height_m):
        """
        Get coastline features visible in a viewport (for rendering).

        Uses R-tree spatial index to query only features in viewport,
        avoiding rendering thousands of off-screen features.

        Args:
            center_lat: Viewport center latitude
            center_lon: Viewport center longitude
            width_m: Viewport width in meters
            height_m: Viewport height in meters

        Returns:
            GeoDataFrame subset with only visible features
        """
        # Convert meters to degrees (approximate)
        # 1 degree latitude ≈ 111 km everywhere
        # 1 degree longitude ≈ 111 km * cos(latitude)
        width_deg = width_m / (111000 * math.cos(math.radians(center_lat)))
        height_deg = height_m / 111000

        # Calculate viewport bounding box
        min_lon = center_lon - width_deg / 2
        max_lon = center_lon + width_deg / 2
        min_lat = center_lat - height_deg / 2
        max_lat = center_lat + height_deg / 2

        # Create bounding box
        viewport_box = box(min_lon, min_lat, max_lon, max_lat)

        # R-tree query: get indices of features that intersect viewport
        indices = list(self.sindex.intersection(viewport_box.bounds))

        if not indices:
            # Return empty GeoDataFrame if nothing visible
            return self.gdf.iloc[0:0]

        # Return subset of features
        return self.gdf.iloc[indices]

    def get_center(self):
        """
        Get geographic center of the region.

        Returns:
            (lat, lon) tuple
        """
        return (self.center_lat, self.center_lon)

    def get_bounds(self):
        """
        Get bounding box of the region.

        Returns:
            (min_lat, min_lon, max_lat, max_lon) tuple
        """
        return (self.min_lat, self.min_lon, self.max_lat, self.max_lon)

    def get_dimensions_deg(self):
        """
        Get dimensions of the region in degrees.

        Returns:
            (width_deg, height_deg) tuple
        """
        return (self.width_deg, self.height_deg)

    def is_in_bounds(self, lat, lon):
        """
        Check if a point is within the geographic bounds.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees

        Returns:
            True if within bounds, False otherwise
        """
        return (self.min_lat <= lat <= self.max_lat and
                self.min_lon <= lon <= self.max_lon)
