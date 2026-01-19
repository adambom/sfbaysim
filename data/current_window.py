"""
Current Window Manager
Manages a sliding window of SFBOFS current data with background loading.
KEY OPTIMIZATION: Shares Delaunay triangulation across all hours (saves ~30 seconds).
"""

import threading
import time
from datetime import timedelta
from data.sfbofs_hour import SFBOFSHourData
from config import (
    FORECAST_WINDOW_HOURS,
    FORECAST_PRELOAD_MARGIN,
    FORECAST_LOAD_THROTTLE,
    FORECAST_PRIORITY_HOURS,
    BACKGROUND_THREAD_DAEMON
)


class CurrentWindowManager:
    """
    Manages a sliding window of SFBOFS current forecast hours.

    KEY OPTIMIZATION: Builds triangulation once, shares across all hours.
    This saves ~5 seconds per hour × 6 hours = 30 seconds total!
    """

    def __init__(self, start_time):
        """
        Initialize current window manager.

        Args:
            start_time: Initial simulation time
        """
        self.start_time = start_time

        # Window: list of dicts with {hour, valid_time, data}
        self.window = []

        # Shared triangulation (built once, reused)
        self.shared_triangulation = None

        # Thread synchronization
        self.lock = threading.Lock()
        self.running = False
        self.loader_thread = None

        # Loading queue and progress
        self.hours_to_load = []
        self.load_progress = {'loaded': 0, 'total': FORECAST_WINDOW_HOURS}

        print(f"Current window manager initialized (window size: {FORECAST_WINDOW_HOURS} hours)")

    def initialize(self):
        """
        Initialize window and start background loading.
        """
        with self.lock:
            # Create window slots
            for i in range(FORECAST_WINDOW_HOURS):
                hour_time = self.start_time + timedelta(hours=i)
                self.window.append({
                    'hour': i,
                    'valid_time': hour_time,
                    'data': None
                })

            # Queue priority hours (0-1) for immediate loading
            for i in range(min(FORECAST_PRIORITY_HOURS, FORECAST_WINDOW_HOURS)):
                self.hours_to_load.append(i)

        # Start background loader thread
        self.running = True
        self.loader_thread = threading.Thread(
            target=self._background_loader,
            daemon=BACKGROUND_THREAD_DAEMON
        )
        self.loader_thread.start()

        print(f"Current loader thread started (priority: hours 0-{FORECAST_PRIORITY_HOURS-1})")

    def _background_loader(self):
        """
        Background thread that loads queued current forecast hours.
        First hour builds triangulation, subsequent hours reuse it.
        """
        print("Current loader thread running...")

        while self.running:
            # Check if there's work to do
            with self.lock:
                if self.hours_to_load:
                    hour_idx = self.hours_to_load.pop(0)
                    slot = dict(self.window[hour_idx])
                    shared_tri = self.shared_triangulation  # Copy reference
                else:
                    # Queue remaining hours if not all loaded
                    if self.load_progress['loaded'] < FORECAST_WINDOW_HOURS:
                        next_hour = self.load_progress['loaded']
                        if next_hour < FORECAST_WINDOW_HOURS and next_hour not in self.hours_to_load:
                            self.hours_to_load.append(next_hour)

                    slot = None
                    shared_tri = None

            if slot is None:
                time.sleep(0.5)
                continue

            # Load data (EXPENSIVE - release lock!)
            try:
                print(f"Loading current hour {slot['hour']}...")

                # Pass shared triangulation (None for first hour)
                data = SFBOFSHourData(slot['valid_time'], shared_tri)
                data.fetch_and_build()

                # If first hour, save triangulation for reuse
                if shared_tri is None and data.shared_tri is not None:
                    with self.lock:
                        self.shared_triangulation = data.shared_tri
                    print(f"✓ Triangulation built and saved for reuse")

                # Update window with loaded data - find slot by hour number
                with self.lock:
                    # Find the slot with matching hour number
                    for window_slot in self.window:
                        if window_slot['hour'] == slot['hour']:
                            window_slot['data'] = data
                            break

                    self.load_progress['loaded'] += 1

                print(f"✓ Current hour {slot['hour']} ready ({self.load_progress['loaded']}/{FORECAST_WINDOW_HOURS})")

            except Exception as e:
                print(f"❌ Failed to load current hour {slot['hour']}: {e}")

            # Throttle loading
            time.sleep(FORECAST_LOAD_THROTTLE)

        print("Current loader thread stopped")

    def get_current(self, sim_time, lat, lon):
        """
        Get interpolated current at sim_time and location.

        Uses temporal interpolation between two bracketing forecast hours.

        Args:
            sim_time: Simulation datetime
            lat: Latitude
            lon: Longitude

        Returns:
            (u, v) tuple in m/s (east, north components)
        """
        with self.lock:
            # Find bracketing hours
            hour_before = None
            hour_after = None

            for slot in self.window:
                if slot['data'] is None or not slot['data'].is_ready:
                    continue

                if slot['valid_time'] <= sim_time:
                    if hour_before is None or slot['valid_time'] > hour_before['valid_time']:
                        hour_before = slot

                if slot['valid_time'] > sim_time:
                    if hour_after is None or slot['valid_time'] < hour_after['valid_time']:
                        hour_after = slot

            # Need both hours for interpolation
            if hour_before is None or hour_after is None:
                return (0.0, 0.0)  # Return zero current if data not ready

            # Copy data references
            data_before = hour_before['data']
            data_after = hour_after['data']
            time_before = hour_before['valid_time']
            time_after = hour_after['valid_time']

        # Get current from both hours (outside lock)
        u_before, v_before = data_before.get_current_at_point(lat, lon)
        u_after, v_after = data_after.get_current_at_point(lat, lon)

        # Temporal interpolation
        total_seconds = (time_after - time_before).total_seconds()
        if total_seconds == 0:
            return (u_before, v_before)

        elapsed_seconds = (sim_time - time_before).total_seconds()
        fraction = elapsed_seconds / total_seconds

        # Linear interpolation on both components
        u = u_before + fraction * (u_after - u_before)
        v = v_before + fraction * (v_after - v_before)

        return (u, v)

    def get_current_batch(self, sim_time, lat_lon_pairs):
        """
        Get current at multiple points (vectorized).

        Args:
            sim_time: Simulation datetime
            lat_lon_pairs: List of (lat, lon) tuples

        Returns:
            List of (u, v) tuples in m/s
        """
        # Find bracketing hours (same as get_current)
        with self.lock:
            hour_before = None
            hour_after = None

            for slot in self.window:
                if slot['data'] is None or not slot['data'].is_ready:
                    continue

                if slot['valid_time'] <= sim_time:
                    if hour_before is None or slot['valid_time'] > hour_before['valid_time']:
                        hour_before = slot

                if slot['valid_time'] > sim_time:
                    if hour_after is None or slot['valid_time'] < hour_after['valid_time']:
                        hour_after = slot

            if hour_before is None or hour_after is None:
                return [(0.0, 0.0)] * len(lat_lon_pairs)

            data_before = hour_before['data']
            data_after = hour_after['data']
            time_before = hour_before['valid_time']
            time_after = hour_after['valid_time']

        # Batch interpolation (outside lock)
        currents_before = data_before.get_current_batch(lat_lon_pairs)
        currents_after = data_after.get_current_batch(lat_lon_pairs)

        # Temporal interpolation
        total_seconds = (time_after - time_before).total_seconds()
        if total_seconds == 0:
            return currents_before

        elapsed_seconds = (sim_time - time_before).total_seconds()
        fraction = elapsed_seconds / total_seconds

        # Interpolate all points
        result = []
        for (u_before, v_before), (u_after, v_after) in zip(currents_before, currents_after):
            u = u_before + fraction * (u_after - u_before)
            v = v_before + fraction * (v_after - v_before)
            result.append((u, v))

        return result

    def update_window(self, sim_time):
        """
        Slide window forward as simulation time advances.

        Args:
            sim_time: Current simulation time
        """
        with self.lock:
            if not self.window:
                return

            last_slot = self.window[-1]
            time_to_edge_hours = (last_slot['valid_time'] - sim_time).total_seconds() / 3600

            if time_to_edge_hours < FORECAST_PRELOAD_MARGIN:
                # Evict oldest hour
                evicted = self.window.pop(0)
                print(f"Evicting current hour {evicted['hour']} from window")

                # Add new hour at end
                new_hour = last_slot['hour'] + 1
                new_time = last_slot['valid_time'] + timedelta(hours=1)

                self.window.append({
                    'hour': new_hour,
                    'valid_time': new_time,
                    'data': None
                })

                # Queue for loading
                new_idx = len(self.window) - 1
                if new_idx not in self.hours_to_load:
                    self.hours_to_load.append(new_idx)

                print(f"Added current hour {new_hour} to window (queued for loading)")

    def get_load_progress(self):
        """Get loading progress for UI display."""
        with self.lock:
            return {
                'loaded': self.load_progress['loaded'],
                'total': self.load_progress['total'],
                'loading': self.load_progress['loaded'] < self.load_progress['total']
            }

    def stop(self):
        """Stop background loader thread."""
        self.running = False
        if self.loader_thread and self.loader_thread.is_alive():
            self.loader_thread.join(timeout=1.0)
