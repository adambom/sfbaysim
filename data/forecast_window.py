"""
Forecast Window Manager
Manages a sliding window of forecast data with background loading.
Progressively loads forecast hours in background thread to avoid blocking.
"""

import threading
import time
from datetime import timedelta
from config import (
    FORECAST_WINDOW_HOURS,
    FORECAST_PRELOAD_MARGIN,
    FORECAST_LOAD_THROTTLE,
    FORECAST_PRIORITY_HOURS,
    BACKGROUND_THREAD_DAEMON
)


class ForecastWindowManager:
    """
    Manages a sliding window of forecast hours with progressive background loading.

    Architecture:
    - Maintains window of N forecast hours (default 6)
    - Loads hours 0-1 first (priority)
    - Progressively loads hours 2-N in background
    - Slides window forward as simulation time advances
    - Thread-safe with locks around shared data
    """

    def __init__(self, start_time, data_class):
        """
        Initialize forecast window manager.

        Args:
            start_time: Initial simulation time
            data_class: Class to instantiate for each hour (e.g., HRRRGridData)
        """
        self.start_time = start_time
        self.data_class = data_class

        # Window: list of dicts with {hour, valid_time, data}
        self.window = []

        # Thread synchronization
        self.lock = threading.Lock()
        self.running = False
        self.loader_thread = None

        # Loading queue and progress
        self.hours_to_load = []
        self.load_progress = {'loaded': 0, 'total': FORECAST_WINDOW_HOURS}

        print(f"Forecast window manager initialized (window size: {FORECAST_WINDOW_HOURS} hours)")

    def initialize(self):
        """
        Initialize window and start background loading.
        Creates window slots and queues hours for loading.
        """
        with self.lock:
            # Create window slots
            for i in range(FORECAST_WINDOW_HOURS):
                hour_time = self.start_time + timedelta(hours=i)
                self.window.append({
                    'hour': i,
                    'valid_time': hour_time,
                    'data': None  # Not loaded yet
                })

            # Queue priority hours for immediate loading (hours 0-1)
            for i in range(min(FORECAST_PRIORITY_HOURS, FORECAST_WINDOW_HOURS)):
                self.hours_to_load.append(i)

        # Start background loader thread
        self.running = True
        self.loader_thread = threading.Thread(
            target=self._background_loader,
            daemon=BACKGROUND_THREAD_DAEMON
        )
        self.loader_thread.start()

        print(f"Background loader thread started (priority: hours 0-{FORECAST_PRIORITY_HOURS-1})")

    def _background_loader(self):
        """
        Background thread that loads queued forecast hours.
        Runs continuously, loading hours from the queue with throttling.
        """
        print("Forecast loader thread running...")

        while self.running:
            # Check if there's work to do
            with self.lock:
                if self.hours_to_load:
                    # Get next hour to load
                    hour_idx = self.hours_to_load.pop(0)
                    slot = dict(self.window[hour_idx])  # Copy slot data
                else:
                    # Queue remaining hours if not all loaded
                    if self.load_progress['loaded'] < FORECAST_WINDOW_HOURS:
                        next_hour = self.load_progress['loaded']
                        if next_hour < FORECAST_WINDOW_HOURS and next_hour not in self.hours_to_load:
                            self.hours_to_load.append(next_hour)

                    slot = None

            if slot is None:
                # No work, sleep briefly
                time.sleep(0.5)
                continue

            # Load data (EXPENSIVE - release lock first!)
            try:
                print(f"Loading forecast hour {slot['hour']}...")
                data = self.data_class(slot['valid_time'])
                data.fetch_and_build()

                # Update window with loaded data - find slot by hour number
                with self.lock:
                    # Find the slot with matching hour number
                    for window_slot in self.window:
                        if window_slot['hour'] == slot['hour']:
                            window_slot['data'] = data
                            break

                    self.load_progress['loaded'] += 1

                print(f"✓ Forecast hour {slot['hour']} ready ({self.load_progress['loaded']}/{FORECAST_WINDOW_HOURS})")

            except Exception as e:
                print(f"❌ Failed to load forecast hour {slot['hour']}: {e}")

            # Throttle loading (don't hammer servers)
            time.sleep(FORECAST_LOAD_THROTTLE)

        print("Forecast loader thread stopped")

    def get_wind(self, sim_time, lat, lon):
        """
        Get interpolated wind at sim_time and location.

        Uses temporal interpolation between two bracketing forecast hours.

        Args:
            sim_time: Simulation datetime
            lat: Latitude
            lon: Longitude

        Returns:
            (direction, speed) tuple, or None if data not ready
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

            # If we have both hours, we can interpolate
            if hour_before is not None and hour_after is not None:
                # Copy data references (release lock for interpolation)
                data_before = hour_before['data']
                data_after = hour_after['data']
                time_before = hour_before['valid_time']
                time_after = hour_after['valid_time']
                use_interpolation = True
            # If we only have one hour, use it directly
            elif hour_before is not None:
                data_single = hour_before['data']
                use_interpolation = False
            elif hour_after is not None:
                data_single = hour_after['data']
                use_interpolation = False
            else:
                # No data loaded yet
                return None

        # Interpolate between two hours
        if use_interpolation:
            # Get wind from both hours (outside lock)
            wind_before = data_before.get_wind_at_point(lat, lon)
            wind_after = data_after.get_wind_at_point(lat, lon)

            if wind_before is None or wind_after is None:
                return None

            # Temporal interpolation
            total_seconds = (time_after - time_before).total_seconds()
            if total_seconds == 0:
                return wind_before

            elapsed_seconds = (sim_time - time_before).total_seconds()
            fraction = elapsed_seconds / total_seconds

            # Interpolate speed (linear)
            speed = wind_before[1] + fraction * (wind_after[1] - wind_before[1])

            # Interpolate direction (handle wraparound)
            dir_before = wind_before[0]
            dir_after = wind_after[0]

            dir_diff = dir_after - dir_before
            # Handle 0°/360° wraparound
            if dir_diff > 180:
                dir_diff -= 360
            elif dir_diff < -180:
                dir_diff += 360

            direction = (dir_before + fraction * dir_diff) % 360

            return (direction, speed)
        else:
            # Use single available hour
            return data_single.get_wind_at_point(lat, lon)

    def update_window(self, sim_time):
        """
        Slide window forward as simulation time advances.

        When sim_time approaches the end of the window, evicts oldest hour
        and adds a new hour at the end.

        Args:
            sim_time: Current simulation time
        """
        with self.lock:
            if not self.window:
                return

            # Check time to last hour in window
            last_slot = self.window[-1]
            time_to_edge_hours = (last_slot['valid_time'] - sim_time).total_seconds() / 3600

            # If within preload margin, extend window
            if time_to_edge_hours < FORECAST_PRELOAD_MARGIN:
                # Evict oldest hour
                evicted = self.window.pop(0)
                print(f"Evicting forecast hour {evicted['hour']} from window")

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

                print(f"Added forecast hour {new_hour} to window (queued for loading)")

    def get_load_progress(self):
        """
        Get loading progress for UI display.

        Returns:
            Dict with 'loaded', 'total', 'loading' keys
        """
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
