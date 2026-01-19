"""
Polar Table Loading and Interpolation
Handles boat performance data (wind angle + wind speed → boat speed).
Uses 2D cubic spline interpolation for smooth performance curves.
"""

import json
import numpy as np
from scipy.interpolate import RectBivariateSpline


class PolarTable:
    """
    Loads and interpolates polar performance data.

    Polar table maps (True Wind Speed, True Wind Angle) → Boat Speed.
    Uses cubic spline interpolation for smooth values between data points.
    """

    def __init__(self, polar_file_path):
        """
        Load polar table from JSON file.

        Args:
            polar_file_path: Path to JSON file with polar data

        JSON Format:
            {
                "boat_name": "...",
                "wind_speeds": [5, 10, 15, 20, 25, 30],  # knots
                "wind_angles": [0, 30, 45, 60, ...],     # degrees (0-180)
                "speeds": [[...], [...], ...]             # 2D array: wind_speed x wind_angle
            }
        """
        with open(polar_file_path, 'r') as f:
            data = json.load(f)

        self.boat_name = data.get('boat_name', 'Unknown')
        self.description = data.get('description', '')

        # Extract arrays
        self.wind_speeds = np.array(data['wind_speeds'], dtype=float)
        self.wind_angles = np.array(data['wind_angles'], dtype=float)
        self.speed_data = np.array(data['speeds'], dtype=float)

        # Validate dimensions
        if self.speed_data.shape != (len(self.wind_speeds), len(self.wind_angles)):
            raise ValueError(
                f"Polar data shape mismatch: expected {(len(self.wind_speeds), len(self.wind_angles))}, "
                f"got {self.speed_data.shape}"
            )

        # Store bounds for clamping
        self.min_tws = self.wind_speeds[0]
        self.max_tws = self.wind_speeds[-1]
        self.min_twa = self.wind_angles[0]
        self.max_twa = self.wind_angles[-1]

        # Build 2D cubic spline interpolator
        self._build_interpolator()

        print(f"Loaded polar table: {self.boat_name}")
        print(f"  Wind speed range: {self.min_tws}-{self.max_tws} kts")
        print(f"  Wind angle range: {self.min_twa}-{self.max_twa}°")

    def _build_interpolator(self):
        """
        Build 2D bilinear interpolator for boat speed lookup.
        Uses scipy's RectBivariateSpline with linear (k=1) interpolation.
        Bilinear is more appropriate for polars - avoids overshoot and gives
        predictable results (e.g., halfway between points = halfway value).
        """
        # RectBivariateSpline expects (x, y, z) where z[i, j] = f(x[i], y[j])
        # x = wind speeds (rows), y = wind angles (columns)
        self.interpolator = RectBivariateSpline(
            self.wind_speeds,
            self.wind_angles,
            self.speed_data,
            kx=1,  # Linear in x (wind speed) direction
            ky=1,  # Linear in y (wind angle) direction
            s=0    # No smoothing (interpolate exactly through points)
        )

    def get_speed(self, twa, tws):
        """
        Get boat speed for given True Wind Angle and True Wind Speed.

        Args:
            twa: True Wind Angle in degrees [-180, 180]
            tws: True Wind Speed in knots

        Returns:
            Boat speed through water in knots

        Note:
            - Handles port/starboard symmetry (negative TWA same as positive)
            - Clamps inputs to polar table bounds (no extrapolation)
            - Returns 0 for invalid inputs
        """
        # Handle port/starboard symmetry: use absolute value of TWA
        twa_abs = abs(twa)

        # Handle wraparound (e.g., TWA = 200° → 160° on opposite tack)
        if twa_abs > 180:
            twa_abs = 360 - twa_abs

        # Clamp to table bounds (don't extrapolate beyond data)
        twa_clamped = np.clip(twa_abs, self.min_twa, self.max_twa)
        tws_clamped = np.clip(tws, self.min_tws, self.max_tws)

        # Interpolate boat speed
        # RectBivariateSpline returns 2D array, extract scalar
        try:
            speed = self.interpolator(tws_clamped, twa_clamped)[0, 0]
            return max(0.0, float(speed))  # Ensure non-negative
        except Exception as e:
            print(f"Warning: Polar interpolation failed for TWA={twa}, TWS={tws}: {e}")
            return 0.0

    def get_optimal_upwind_angle(self, tws):
        """
        Find optimal upwind angle (best VMG toward wind) for given wind speed.

        Args:
            tws: True Wind Speed in knots

        Returns:
            Optimal TWA in degrees (typically 40-50°)
        """
        # Sample close-hauled angles (30-60 degrees)
        angles = np.linspace(30, 60, 31)
        best_vmg = -float('inf')
        best_angle = 45

        for angle in angles:
            boat_speed = self.get_speed(angle, tws)
            # VMG upwind = boat_speed * cos(TWA)
            vmg = boat_speed * np.cos(np.radians(angle))

            if vmg > best_vmg:
                best_vmg = vmg
                best_angle = angle

        return best_angle

    def get_optimal_downwind_angle(self, tws):
        """
        Find optimal downwind angle (best VMG away from wind) for given wind speed.

        Args:
            tws: True Wind Speed in knots

        Returns:
            Optimal TWA in degrees (typically 140-160°)
        """
        # Sample broad reach to dead downwind angles (120-180 degrees)
        angles = np.linspace(120, 180, 31)
        best_vmg = -float('inf')
        best_angle = 150

        for angle in angles:
            boat_speed = self.get_speed(angle, tws)
            # VMG downwind = boat_speed * cos(180 - TWA)
            # Equivalent to: -boat_speed * cos(TWA)
            vmg = -boat_speed * np.cos(np.radians(angle))

            if vmg > best_vmg:
                best_vmg = vmg
                best_angle = angle

        return best_angle

    def get_speed_range(self):
        """
        Get min/max boat speeds from polar table.

        Returns:
            (min_speed, max_speed) tuple in knots
        """
        return (float(np.min(self.speed_data)), float(np.max(self.speed_data)))

    def __repr__(self):
        return f"PolarTable(boat='{self.boat_name}', tws_range=[{self.min_tws}, {self.max_tws}] kts)"
