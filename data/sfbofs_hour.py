"""
SFBOFS Hour Data Loading
Loads NOAA SFBOFS (San Francisco Bay Operational Forecast System) current data.
Uses OpenDAP to access NetCDF files. Builds Delaunay triangulation for interpolation.
"""

import time
import numpy as np
import xarray as xr
from datetime import datetime, timedelta, timezone
from scipy.spatial import Delaunay
from scipy.interpolate import LinearNDInterpolator
from config import (
    SFBOFS_OPENDAP_BASE_URL,
    SFBOFS_URL_TEMPLATE,
    SFBOFS_MODEL_CYCLES,
    MAX_NOAA_RETRY_ATTEMPTS,
    NOAA_RETRY_DELAY
)


class SFBOFSHourData:
    """
    Loads and interpolates SFBOFS current data for a specific forecast hour.

    SFBOFS Grid: 102,264 elements (triangular unstructured mesh)
    Resolution: Variable (finer in channels, coarser in open water)
    Coverage: San Francisco Bay only
    Variables: u, v (velocity components in m/s)
    Vertical: 20 sigma layers (0=surface, 19=bottom)
    """

    def __init__(self, target_datetime, shared_triangulation=None):
        """
        Initialize SFBOFS data loader for specific time.

        Args:
            target_datetime: Target datetime for forecast data
            shared_triangulation: Optional pre-built Delaunay triangulation
                                 (HUGE optimization - reuse across hours!)
        """
        self.target_datetime = target_datetime
        self.shared_tri = shared_triangulation
        self.interpolator_u = None
        self.interpolator_v = None
        self.is_ready = False
        self.valid_time = None
        self.grid_points = None

    def fetch_and_build(self):
        """
        Load NetCDF file via OpenDAP and build interpolators.
        Takes 5-10 seconds due to triangulation (first time only).
        """
        # Try multiple model runs (newest to oldest) until one works
        success = False
        ds = None

        # Try current and previous 2 days
        for days_back in range(3):
            test_time = self.target_datetime - timedelta(days=days_back)

            # Try each model cycle for this day
            for cycle in reversed(SFBOFS_MODEL_CYCLES):  # Try newest first: 21, 15, 9, 3
                try:
                    cycle_time = test_time.replace(hour=cycle, minute=0, second=0, microsecond=0)

                    # Skip if cycle_time is in the future
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    if cycle_time > now:
                        continue

                    # Calculate forecast hour for this cycle
                    forecast_hour = round((self.target_datetime - cycle_time).total_seconds() / 3600)

                    # Skip if forecast hour is out of range
                    if forecast_hour < 0 or forecast_hour > 48:
                        continue

                    # Construct OpenDAP URL
                    url = self._construct_url(cycle_time, forecast_hour)

                    # Try to load via OpenDAP
                    print(f"Trying SFBOFS: {cycle_time.strftime('%Y%m%d %Hz')} f{forecast_hour:03d}...")

                    for attempt in range(MAX_NOAA_RETRY_ATTEMPTS):
                        try:
                            ds = xr.open_dataset(url)
                            success = True
                            print(f"✓ Using SFBOFS run: {cycle_time.strftime('%Y%m%d %Hz')} f{forecast_hour:03d}")
                            break
                        except FileNotFoundError as e:
                            # File doesn't exist (404-like), no point retrying
                            print(f"  File not found, skipping...")
                            break
                        except OSError as e:
                            # Check if it's a "file not found" error from OpenDAP
                            if "NetCDF: file not found" in str(e) or "No such file" in str(e):
                                print(f"  File not found, skipping...")
                                break
                            # Other OSError, retry
                            if attempt < MAX_NOAA_RETRY_ATTEMPTS - 1:
                                time.sleep(1)
                            else:
                                pass
                        except Exception as e:
                            # Other errors, retry
                            if attempt < MAX_NOAA_RETRY_ATTEMPTS - 1:
                                time.sleep(1)
                            else:
                                pass

                    if success:
                        break

                except Exception as e:
                    # Try next run
                    continue

            if success:
                break

        if not success or ds is None:
            raise Exception("Could not find any available SFBOFS data")

        try:

            # 4. Extract element centers (where u/v are defined)
            lon_centers = ds['lonc'].values  # (102264,) - USES 0-360° CONVENTION!
            lat_centers = ds['latc'].values

            print(f"SFBOFS grid: {len(lon_centers):,} elements")

            # 5. Extract u/v at surface layer (sigma index 0)
            # Data shape: (time, sigma, element)
            u_data = ds['u'].values  # (1, 20, 102264)
            v_data = ds['v'].values

            # Get surface layer (first sigma layer, index 0)
            u_surface = u_data[0, 0, :]  # (102264,)
            v_surface = v_data[0, 0, :]

            # 6. Parse valid time
            if 'Times' in ds.variables:
                time_bytes = ds['Times'].values[0]
                time_str = time_bytes.tobytes().decode('utf-8').strip()
                # Handle formats: "2025-12-21_09:00:00" or "2025-12-21T09:00:00.000000"
                time_str = time_str.split('.')[0].replace('T', ' ').replace('_', ' ')
                self.valid_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            else:
                self.valid_time = cycle_time + timedelta(hours=forecast_hour)

            ds.close()

            # 7. Build or reuse triangulation
            if self.shared_tri is None:
                # Build new triangulation (SLOW - 5-10 seconds)
                print(f"Building Delaunay triangulation for {len(lon_centers):,} points...")
                start_time = time.time()

                self.grid_points = np.column_stack([lon_centers, lat_centers])
                self.shared_tri = Delaunay(self.grid_points)

                elapsed = time.time() - start_time
                print(f"✓ Triangulation complete in {elapsed:.1f} seconds ({len(self.shared_tri.simplices):,} triangles)")
            else:
                print(f"✓ Reusing existing triangulation ({len(self.shared_tri.simplices):,} triangles)")

            # 8. Create interpolators using shared triangulation
            self.interpolator_u = LinearNDInterpolator(
                self.shared_tri,
                u_surface,
                fill_value=0.0  # Return 0 for points outside bay
            )

            self.interpolator_v = LinearNDInterpolator(
                self.shared_tri,
                v_surface,
                fill_value=0.0
            )

            self.is_ready = True

        except Exception as e:
            print(f"❌ Error loading SFBOFS data: {e}")
            self.is_ready = False
            raise

    def _construct_url(self, cycle_time, forecast_hour):
        """
        Construct OpenDAP URL for SFBOFS NetCDF file.

        Args:
            cycle_time: Model cycle datetime
            forecast_hour: Forecast hour (0-48)

        Returns:
            URL string
        """
        year = cycle_time.year
        month = cycle_time.month
        day = cycle_time.day
        cycle = cycle_time.hour
        date_str = cycle_time.strftime('%Y%m%d')

        url = SFBOFS_URL_TEMPLATE.format(
            base=SFBOFS_OPENDAP_BASE_URL,
            year=year,
            month=month,
            day=day,
            cycle=cycle,
            date=date_str,
            hour=forecast_hour
        )

        return url

    def get_current_at_point(self, lat, lon):
        """
        Get current at specific point using spatial interpolation.

        CRITICAL: SFBOFS uses 0-360° longitude convention!
        Must convert negative longitude before interpolation.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees (-180 to 180)

        Returns:
            (u, v) tuple in m/s (east, north components)
        """
        if not self.is_ready:
            return (0.0, 0.0)

        try:
            # Convert longitude to 0-360° format used by SFBOFS
            lon_360 = lon + 360 if lon < 0 else lon

            # Interpolate u and v components
            u = float(self.interpolator_u(lon_360, lat))
            v = float(self.interpolator_v(lon_360, lat))

            # Handle NaN (point outside SF Bay)
            if np.isnan(u):
                u = 0.0
            if np.isnan(v):
                v = 0.0

            return (u, v)

        except Exception as e:
            print(f"Warning: Current interpolation failed at ({lat:.4f}, {lon:.4f}): {e}")
            return (0.0, 0.0)

    def get_current_batch(self, lat_lon_pairs):
        """
        Get current at multiple points (vectorized - MUCH faster).

        Args:
            lat_lon_pairs: List of (lat, lon) tuples

        Returns:
            List of (u, v) tuples in m/s
        """
        if not self.is_ready:
            return [(0.0, 0.0)] * len(lat_lon_pairs)

        try:
            # Convert all longitudes to 0-360° format
            points_360 = []
            for lat, lon in lat_lon_pairs:
                lon_360 = lon + 360 if lon < 0 else lon
                points_360.append([lon_360, lat])

            points_360 = np.array(points_360)

            # Interpolate all points at once (FAST!)
            u_values = self.interpolator_u(points_360)
            v_values = self.interpolator_v(points_360)

            # Replace NaN with 0
            u_values = np.nan_to_num(u_values, nan=0.0)
            v_values = np.nan_to_num(v_values, nan=0.0)

            # Return as list of tuples
            return list(zip(u_values, v_values))

        except Exception as e:
            print(f"Warning: Batch current interpolation failed: {e}")
            return [(0.0, 0.0)] * len(lat_lon_pairs)
