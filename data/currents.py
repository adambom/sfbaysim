"""
Current Provider
High-level current data provider using SFBOFS forecast window.
Simpler than weather provider - only one source (SFBOFS), fallback is zero current.
"""

from data.current_window import CurrentWindowManager


class CurrentProvider:
    """
    Provides current data from SFBOFS.

    Fallback strategy: Return zero current if data unavailable.
    This allows simulation to continue without currents.
    """

    def __init__(self, start_time):
        """
        Initialize current provider.

        Args:
            start_time: Initial simulation time
        """
        self.start_time = start_time

        # Initialize current window manager
        print("Initializing SFBOFS current window...")
        self.current_window = CurrentWindowManager(start_time)
        self.current_window.initialize()

    def get_current(self, sim_time, lat, lon):
        """
        Get current at specified time and location.

        Args:
            sim_time: Simulation datetime
            lat: Latitude
            lon: Longitude

        Returns:
            (u, v) tuple in m/s (east, north components)
            Returns (0.0, 0.0) if data not available
        """
        if self.current_window:
            return self.current_window.get_current(sim_time, lat, lon)
        else:
            return (0.0, 0.0)

    def get_current_batch(self, sim_time, lat_lon_pairs):
        """
        Get current at multiple points (vectorized).

        Args:
            sim_time: Simulation datetime
            lat_lon_pairs: List of (lat, lon) tuples

        Returns:
            List of (u, v) tuples in m/s
        """
        if self.current_window:
            return self.current_window.get_current_batch(sim_time, lat_lon_pairs)
        else:
            return [(0.0, 0.0)] * len(lat_lon_pairs)

    def update(self, sim_time):
        """
        Update forecast window as simulation time advances.

        Args:
            sim_time: Current simulation time
        """
        if self.current_window:
            self.current_window.update_window(sim_time)

    def get_load_progress(self):
        """
        Get loading progress for UI display.

        Returns:
            Dict with 'loaded', 'total', 'loading' keys
        """
        if self.current_window:
            return self.current_window.get_load_progress()
        else:
            return {'loaded': 0, 'total': 0, 'loading': False}

    def stop(self):
        """Stop background threads."""
        if self.current_window:
            self.current_window.stop()
