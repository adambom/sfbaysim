"""
HRRR Grid Data Loading
Downloads and parses NOAA HRRR (High-Resolution Rapid Refresh) weather data.
Uses bilinear interpolation on regular grid (instant - no triangulation needed).
"""

import os
import time
import numpy as np
import xarray as xr
import requests
from datetime import datetime, timedelta, timezone
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial import cKDTree
from config import (
    HRRR_S3_BASE_URL,
    HRRR_URL_TEMPLATE,
    CACHE_DIR,
    MS_TO_KNOTS,
    MAX_NOAA_RETRY_ATTEMPTS,
    NOAA_RETRY_DELAY,
    OFFLINE_MODE
)
from data.cache_manager import get_cache_manager


class HRRRGridData:
    """
    Loads and interpolates HRRR weather data for a specific forecast hour.

    HRRR Grid: 1059 x 1799 = 1,905,141 points (regular grid)
    Resolution: ~3km
    Coverage: Continental US
    Variables: U10, V10 (10-meter wind components in m/s)

    Uses bilinear interpolation via RegularGridInterpolator on the regular grid.
    MUCH faster than Delaunay triangulation (instant vs 20 seconds).
    """

    def __init__(self, target_datetime):
        """
        Initialize HRRR data loader for specific time.

        Args:
            target_datetime: Target datetime for forecast data
        """
        self.target_datetime = target_datetime
        self.is_ready = False
        self.grid_size = None
        self.valid_time = None

        # Store 2D grids and interpolators
        self.lats_2d = None
        self.lons_2d = None
        self.u_2d = None
        self.v_2d = None
        self.interpolator_u = None
        self.interpolator_v = None
        self.kdtree = None  # Fast spatial lookup

    def fetch_and_build(self):
        """
        Download GRIB2 file and parse wind data.
        Fast - only takes a few seconds to download and parse.
        Uses nearest neighbor on regular grid (no triangulation needed).
        """
        # Get cache manager
        cache_mgr = get_cache_manager()

        # Try multiple model runs (newest to oldest) until one works
        success = False
        cache_path = None

        # HRRR runs every hour! Try recent hourly runs
        # Start from most recent and go back up to 72 hours
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        for hours_back in range(72):
            try:
                # Calculate potential run time
                run_time = now - timedelta(hours=hours_back)
                run_time = run_time.replace(minute=0, second=0, microsecond=0)

                # Calculate forecast hour for this run
                forecast_hour = int((self.target_datetime - run_time).total_seconds() / 3600)

                # Skip if forecast hour is out of valid range (HRRR has 0-48h forecasts)
                if forecast_hour < 0 or forecast_hour > 48:
                    continue

                # Use cache manager to get cache path
                cache_path = cache_mgr.get_cache_path('hrrr', run_time, forecast_hour)

                # Check if cached
                if cache_path.exists():
                    print(f"Cache hit: HRRR {run_time.strftime('%Y%m%d %Hz')} f{forecast_hour:02d}")
                    cache_mgr.update_access_time(cache_path.name)
                    success = True
                    print(f"✓ Using cached HRRR: {run_time.strftime('%Y%m%d %Hz')} f{forecast_hour:02d}")
                    break

                # In offline mode, skip network attempts
                if OFFLINE_MODE:
                    continue

                # Download from network
                url = self._construct_url(run_time, forecast_hour)
                self._download_file(url, str(cache_path))

                # Register with cache manager
                cache_mgr.register_file('hrrr', run_time, forecast_hour, cache_path)

                success = True
                print(f"✓ Using HRRR run: {run_time.strftime('%Y%m%d %Hz')} f{forecast_hour:02d}")
                break

            except Exception as e:
                # Try next hour back
                continue

        if not success or cache_path is None:
            if OFFLINE_MODE:
                raise Exception("No cached HRRR data available (offline mode)")
            else:
                raise Exception("Could not find any available HRRR data")

        try:

            # 4. Parse GRIB2 file
            print(f"Parsing HRRR GRIB2 file...")
            ds = xr.open_dataset(
                cache_path,
                engine='cfgrib',
                backend_kwargs={
                    'filter_by_keys': {
                        'typeOfLevel': 'heightAboveGround',
                        'level': 10
                    }
                }
            )

            # 5. Extract wind components at 10m height
            u_wind = ds['u10'].values  # East component (m/s) - 2D array
            v_wind = ds['v10'].values  # North component (m/s) - 2D array
            lats = ds['latitude'].values  # 2D array
            lons = ds['longitude'].values  # 2D array

            # Debug: Check data ranges
            print(f"  HRRR data ranges:")
            print(f"    u10: min={np.min(u_wind):.2f}, max={np.max(u_wind):.2f}, mean={np.mean(u_wind):.2f} m/s")
            print(f"    v10: min={np.min(v_wind):.2f}, max={np.max(v_wind):.2f}, mean={np.mean(v_wind):.2f} m/s")
            print(f"    lat: min={np.min(lats):.2f}, max={np.max(lats):.2f}")
            print(f"    lon: min={np.min(lons):.2f}, max={np.max(lons):.2f}")

            # Store 2D grids
            self.grid_size = u_wind.shape
            self.lats_2d = lats
            self.lons_2d = lons
            self.u_2d = u_wind
            self.v_2d = v_wind

            # Extract valid time if available
            if 'valid_time' in ds.coords:
                valid_time_val = ds.coords['valid_time'].values
                # Handle both scalar and array cases
                if hasattr(valid_time_val, '__len__'):
                    self.valid_time = valid_time_val[0]
                else:
                    self.valid_time = valid_time_val
            else:
                self.valid_time = run_time + timedelta(hours=forecast_hour)

            ds.close()

            print(f"HRRR grid size: {self.grid_size[0]} x {self.grid_size[1]} = {u_wind.size:,} points")

            # 6. Build RegularGridInterpolator for bilinear interpolation
            # HRRR is on a regular grid in projection space, use grid indices as coordinates
            print(f"Building bilinear interpolators (RegularGridInterpolator)...")
            start_time = time.time()

            y_coords = np.arange(self.grid_size[0])
            x_coords = np.arange(self.grid_size[1])

            # Build interpolators with bilinear interpolation (method='linear')
            self.interpolator_u = RegularGridInterpolator(
                (y_coords, x_coords),
                u_wind,
                method='linear',  # Bilinear interpolation in 2D
                bounds_error=False,
                fill_value=0.0
            )

            self.interpolator_v = RegularGridInterpolator(
                (y_coords, x_coords),
                v_wind,
                method='linear',  # Bilinear interpolation in 2D
                bounds_error=False,
                fill_value=0.0
            )

            elapsed = time.time() - start_time
            print(f"✓ Bilinear interpolators built in {elapsed:.3f} seconds")

            # 7. Build KDTree for fast spatial lookups
            print(f"Building KDTree for fast spatial queries...")
            start_time = time.time()

            # Flatten lat/lon arrays and create point cloud
            grid_points = np.column_stack([self.lats_2d.flatten(), self.lons_2d.flatten()])
            self.kdtree = cKDTree(grid_points)

            elapsed = time.time() - start_time
            print(f"✓ KDTree built in {elapsed:.1f} seconds")

            self.is_ready = True

        except Exception as e:
            print(f"❌ Error loading HRRR data: {e}")
            self.is_ready = False
            raise


    def _construct_url(self, run_time, forecast_hour):
        """
        Construct URL for HRRR GRIB2 file on AWS S3.

        Args:
            run_time: Model run datetime
            forecast_hour: Forecast hour (0-48)

        Returns:
            URL string
        """
        date_str = run_time.strftime('%Y%m%d')
        cycle = run_time.hour

        url = HRRR_URL_TEMPLATE.format(
            base=HRRR_S3_BASE_URL,
            date=date_str,
            cycle=cycle,
            hour=forecast_hour
        )

        return url

    def _download_file(self, url, dest_path):
        """
        Download HRRR file from AWS S3.

        Args:
            url: Source URL
            dest_path: Destination file path

        Raises:
            Exception on permanent errors (404) or after retries exhausted
        """
        print(f"Downloading HRRR data from AWS S3...")
        print(f"  URL: {url}")

        for attempt in range(MAX_NOAA_RETRY_ATTEMPTS):
            try:
                response = requests.get(url, stream=True, timeout=60)
                response.raise_for_status()

                # Download with progress
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            # Print progress every 10MB
                            if downloaded % (10 * 1024 * 1024) < 8192:
                                mb = downloaded / (1024 * 1024)
                                print(f"  Downloaded {mb:.1f} MB...")

                print(f"✓ Download complete ({downloaded / (1024 * 1024):.1f} MB)")
                return

            except requests.exceptions.HTTPError as e:
                # Check if 404 - file doesn't exist, no point retrying
                if e.response.status_code == 404:
                    raise Exception(f"File not found (404): {url}")

                # For other HTTP errors, retry
                print(f"  Attempt {attempt + 1}/{MAX_NOAA_RETRY_ATTEMPTS} failed: HTTP {e.response.status_code}")
                if attempt < MAX_NOAA_RETRY_ATTEMPTS - 1:
                    print(f"  Retrying in {NOAA_RETRY_DELAY} seconds...")
                    time.sleep(NOAA_RETRY_DELAY)
                else:
                    raise

            except Exception as e:
                # For other errors (timeout, connection), retry
                print(f"  Attempt {attempt + 1}/{MAX_NOAA_RETRY_ATTEMPTS} failed: {e}")
                if attempt < MAX_NOAA_RETRY_ATTEMPTS - 1:
                    print(f"  Retrying in {NOAA_RETRY_DELAY} seconds...")
                    time.sleep(NOAA_RETRY_DELAY)
                else:
                    raise

    def _find_grid_cell(self, lat, lon_360):
        """
        Find the grid cell for a given lat/lon using KDTree.
        Returns fractional grid indices for bilinear interpolation.
        Fast O(log n) lookup instead of O(n).
        """
        # Use KDTree to find nearest grid point (FAST!)
        query_point = np.array([lat, lon_360])
        distance, flat_idx = self.kdtree.query(query_point)

        # Convert flat index to 2D indices
        y0, x0 = np.unravel_index(flat_idx, self.grid_size)

        # Clamp to valid range for cell corners
        y0 = max(0, min(y0, self.grid_size[0] - 2))
        x0 = max(0, min(x0, self.grid_size[1] - 2))

        # Get 4 corner points of grid cell
        lat00 = self.lats_2d[y0, x0]
        lon00 = self.lons_2d[y0, x0]
        lat11 = self.lats_2d[y0+1, x0+1]
        lon11 = self.lons_2d[y0+1, x0+1]

        # Calculate fractional position within cell [0, 1]
        if lon11 != lon00 and lat11 != lat00:
            fx = (lon_360 - lon00) / (lon11 - lon00)
            fy = (lat - lat00) / (lat11 - lat00)

            # Clamp to [0, 1]
            fx = max(0.0, min(1.0, fx))
            fy = max(0.0, min(1.0, fy))
        else:
            fx = 0.0
            fy = 0.0

        # Convert to continuous grid indices for interpolation
        y_idx = y0 + fy
        x_idx = x0 + fx

        return y_idx, x_idx

    def get_wind_at_point(self, lat, lon):
        """
        Get wind at specific point using bilinear interpolation on regular grid.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees (-180 to 180)

        Returns:
            (direction, speed_kts) tuple, or None if not ready
            Direction is meteorological (wind FROM this direction)
        """
        if not self.is_ready:
            return None

        try:
            # Convert negative longitude to 0-360° format (HRRR uses 0-360°)
            lon_360 = lon + 360 if lon < 0 else lon

            # Find fractional grid indices for bilinear interpolation
            y_idx, x_idx = self._find_grid_cell(lat, lon_360)

            # Use RegularGridInterpolator with fractional indices (bilinear interpolation)
            query_point = np.array([[y_idx, x_idx]])

            u = float(self.interpolator_u(query_point)[0])
            v = float(self.interpolator_v(query_point)[0])

            # Convert to speed and direction
            speed_ms = np.sqrt(u**2 + v**2)
            speed_kts = speed_ms * MS_TO_KNOTS

            # Calculate direction (meteorological: wind FROM this direction)
            # atan2(u, v) gives direction wind is TO, add 180 for FROM
            direction = (np.degrees(np.arctan2(u, v)) + 180) % 360

            # Debug output for first few calls
            if not hasattr(self, '_debug_count'):
                self._debug_count = 0
            if self._debug_count < 2:
                print(f"  DEBUG: HRRR at ({lat:.4f}, {lon:.4f}→{lon_360:.2f}): grid[{y_idx:.2f},{x_idx:.2f}] u={u:.2f}, v={v:.2f} → {direction:.0f}° @ {speed_kts:.1f} kts")
                self._debug_count += 1

            return (direction, speed_kts)

        except Exception as e:
            print(f"Warning: Wind interpolation failed at ({lat:.4f}, {lon:.4f}): {e}")
            return None

    def get_wind_batch(self, lat_lon_pairs):
        """
        Get wind at multiple points using bilinear interpolation on regular grid.

        Args:
            lat_lon_pairs: List of (lat, lon) tuples

        Returns:
            List of (direction, speed_kts) tuples
        """
        if not self.is_ready:
            return [(0.0, 0.0)] * len(lat_lon_pairs)

        try:
            results = []

            for lat, lon in lat_lon_pairs:
                # Convert longitude to 0-360° format
                lon_360 = lon + 360 if lon < 0 else lon

                # Find fractional grid indices
                y_idx, x_idx = self._find_grid_cell(lat, lon_360)

                # Query interpolator with fractional indices (bilinear)
                query_point = np.array([[y_idx, x_idx]])
                u = float(self.interpolator_u(query_point)[0])
                v = float(self.interpolator_v(query_point)[0])

                # Convert to speed and direction
                speed_ms = np.sqrt(u**2 + v**2)
                speed_kts = speed_ms * MS_TO_KNOTS
                direction = (np.degrees(np.arctan2(u, v)) + 180) % 360

                results.append((direction, speed_kts))

            return results

        except Exception as e:
            print(f"Warning: Batch wind interpolation failed: {e}")
            return [(0.0, 0.0)] * len(lat_lon_pairs)
