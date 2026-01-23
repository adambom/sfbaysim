"""
Controls Handler
Processes keyboard and mouse input for simulator control.
"""

import pygame
import math
from config import SPEED_MULTIPLIERS, DEFAULT_SPEED_INDEX


class ControlHandler:
    """
    Handles user input and maintains control state.
    """

    def __init__(self, boats, map_view, polar):
        """
        Initialize control handler.

        Args:
            boats: List of Boat instances
            map_view: MapView instance
            polar: Polar table for creating new boats
        """
        self.boats = boats  # List of all boats
        self.active_boat_index = 0  # Index of currently controlled boat
        self.map_view = map_view
        self.polar = polar  # Store polar for adding new boats

        # Simulation state
        self.paused = True  # Start paused
        self.sim_speed_index = DEFAULT_SPEED_INDEX
        self.speed_multipliers = SPEED_MULTIPLIERS

        # UI state
        self.show_wind_overlay = False
        self.show_current_overlay = False
        self.show_help = False
        self.show_course_lines = False  # Heading and COG projection lines
        self.show_mark_lines = False  # Dashed lines to target marks

        # Forecast preview mode (for looking ahead in time while paused)
        self.forecast_preview_mode = False
        self.preview_time_offset_minutes = 0  # Minutes ahead of current sim time

        # Time rewind mode
        self.rewind_mode = False
        self.history = None  # Will be set by main.py
        self.pending_time_restore = None  # Pending restore data for main.py

        # Shared waypoints for all boats
        self.waypoints = []

        # Mouse drag state
        self.dragging = False
        self.last_mouse_pos = None

    @property
    def active_boat(self):
        """Get the currently active boat."""
        if self.boats:
            return self.boats[self.active_boat_index]
        return None

    def handle_event(self, event):
        """
        Process pygame event.

        Args:
            event: Pygame event object

        Returns:
            'quit' if user wants to quit, None otherwise
        """
        if event.type == pygame.KEYDOWN:
            # ===== HEADING CONTROL =====
            if event.key == pygame.K_LEFT:
                if self.active_boat:
                    self.active_boat.adjust_heading(-5)

            elif event.key == pygame.K_RIGHT:
                if self.active_boat:
                    self.active_boat.adjust_heading(5)

            elif event.key == pygame.K_a:
                if self.active_boat:
                    self.active_boat.adjust_heading(-1)  # Fine control

            elif event.key == pygame.K_d:
                if self.active_boat:
                    self.active_boat.adjust_heading(1)  # Fine control

            # ===== MANEUVERS =====
            elif event.key == pygame.K_t:
                if self.active_boat:
                    self.active_boat.tack()

            elif event.key == pygame.K_g:
                if self.active_boat:
                    self.active_boat.gybe()

            # ===== SIMULATION CONTROL =====
            elif event.key == pygame.K_SPACE:
                if self.rewind_mode and not self.paused:
                    # Resuming from rewind mode - truncate future history
                    if self.history:
                        self.history.truncate_future()
                    self.rewind_mode = False
                    print("Resumed from rewind - future history truncated")
                elif self.rewind_mode and self.paused:
                    # Resume simulation from rewound state
                    if self.history:
                        self.history.truncate_future()
                    self.rewind_mode = False
                    self.paused = False
                    print("Resumed from rewind - future history truncated")
                else:
                    self.paused = not self.paused
                    status = "PAUSED" if self.paused else "RESUMED"
                    print(f"Simulation {status}")

            elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                # Speed up
                if self.sim_speed_index < len(self.speed_multipliers) - 1:
                    self.sim_speed_index += 1
                    print(f"Simulation speed: {self.get_sim_speed():.1f}x")

            elif event.key == pygame.K_MINUS:
                # Slow down
                if self.sim_speed_index > 0:
                    self.sim_speed_index -= 1
                    print(f"Simulation speed: {self.get_sim_speed():.1f}x")

            # ===== VIEW CONTROL =====
            elif event.key == pygame.K_c:
                if self.active_boat:
                    self.map_view.center_on_boat(self.active_boat)
                    print(f"Centered on {self.active_boat.name}")

            elif event.key == pygame.K_LEFTBRACKET:
                # [ key - step backward in rewind mode, or zoom out otherwise
                if self.rewind_mode and self.paused and self.history:
                    result = self.history.step_backward(self.boats)
                    if result:
                        sim_time, accumulator, breadcrumb_timer, waypoints = result
                        self.pending_time_restore = {
                            'sim_time': sim_time,
                            'accumulator': accumulator,
                            'breadcrumb_timer': breadcrumb_timer,
                            'waypoints': waypoints
                        }
                        offset = self.history.get_time_offset_seconds()
                        print(f"Rewound to {sim_time.strftime('%H:%M:%S')} ({offset:.0f}s)")
                    else:
                        print("At oldest snapshot")
                else:
                    self.map_view.zoom_out()
                    print(f"Zoom: {self.map_view.zoom:.2f}x")

            elif event.key == pygame.K_RIGHTBRACKET:
                # ] key - step forward in rewind mode, or zoom in otherwise
                if self.rewind_mode and self.paused and self.history:
                    result = self.history.step_forward(self.boats)
                    if result:
                        sim_time, accumulator, breadcrumb_timer, waypoints = result
                        self.pending_time_restore = {
                            'sim_time': sim_time,
                            'accumulator': accumulator,
                            'breadcrumb_timer': breadcrumb_timer,
                            'waypoints': waypoints
                        }
                        offset = self.history.get_time_offset_seconds()
                        print(f"Stepped to {sim_time.strftime('%H:%M:%S')} ({offset:.0f}s)")
                    else:
                        print("At present")
                else:
                    self.map_view.zoom_in()
                    print(f"Zoom: {self.map_view.zoom:.2f}x")

            # ===== OVERLAY TOGGLES =====
            elif event.key == pygame.K_w:
                self.show_wind_overlay = not self.show_wind_overlay
                status = "ON" if self.show_wind_overlay else "OFF"
                print(f"Wind overlay {status}")

            elif event.key == pygame.K_u:
                self.show_current_overlay = not self.show_current_overlay
                status = "ON" if self.show_current_overlay else "OFF"
                print(f"Current overlay {status}")

            elif event.key == pygame.K_h:
                self.show_help = not self.show_help

            elif event.key == pygame.K_l:
                self.show_course_lines = not self.show_course_lines
                status = "ON" if self.show_course_lines else "OFF"
                print(f"Course lines {status}")

            elif event.key == pygame.K_k:
                self.show_mark_lines = not self.show_mark_lines
                status = "ON" if self.show_mark_lines else "OFF"
                print(f"Mark target lines {status}")

            # ===== TIME REWIND MODE =====
            elif event.key == pygame.K_BACKQUOTE:
                # ` (backtick) - toggle rewind mode (only when paused)
                if self.paused:
                    self.rewind_mode = not self.rewind_mode
                    if self.rewind_mode:
                        # Exit forecast preview mode (mutually exclusive)
                        self.forecast_preview_mode = False
                        self.preview_time_offset_minutes = 0
                        print("Rewind mode ON - Use [ ] to step, Home/End to jump")
                    else:
                        print("Rewind mode OFF")
                else:
                    print("Rewind mode only available when paused (press SPACE first)")

            elif event.key == pygame.K_HOME:
                # Home - jump to oldest history (only in rewind mode)
                if self.rewind_mode and self.paused and self.history:
                    result = self.history.jump_to_oldest(self.boats)
                    if result:
                        sim_time, accumulator, breadcrumb_timer, waypoints = result
                        self.pending_time_restore = {
                            'sim_time': sim_time,
                            'accumulator': accumulator,
                            'breadcrumb_timer': breadcrumb_timer,
                            'waypoints': waypoints
                        }
                        offset = self.history.get_time_offset_seconds()
                        print(f"Jumped to oldest: {sim_time.strftime('%H:%M:%S')} ({offset:.0f}s)")

            elif event.key == pygame.K_END:
                # End - jump to present (only in rewind mode)
                if self.rewind_mode and self.paused and self.history:
                    result = self.history.jump_to_present(self.boats)
                    if result:
                        sim_time, accumulator, breadcrumb_timer, waypoints = result
                        self.pending_time_restore = {
                            'sim_time': sim_time,
                            'accumulator': accumulator,
                            'breadcrumb_timer': breadcrumb_timer,
                            'waypoints': waypoints
                        }
                        print(f"Jumped to present: {sim_time.strftime('%H:%M:%S')}")

            # ===== FORECAST PREVIEW MODE =====
            elif event.key == pygame.K_f:
                # Toggle forecast preview mode (only when paused)
                if self.paused:
                    self.forecast_preview_mode = not self.forecast_preview_mode
                    if self.forecast_preview_mode:
                        # Exit rewind mode (mutually exclusive)
                        self.rewind_mode = False
                        self.preview_time_offset_minutes = 0
                        print("Forecast preview mode ON - Use , / . to scrub time")
                    else:
                        self.preview_time_offset_minutes = 0
                        print("Forecast preview mode OFF - Restored to current time")
                else:
                    print("Forecast preview only available when paused (press SPACE first)")

            elif event.key == pygame.K_COMMA:
                # Scrub time backward (only in preview mode)
                if self.forecast_preview_mode and self.paused:
                    self.preview_time_offset_minutes = max(-60, self.preview_time_offset_minutes - 10)
                    print(f"Preview time: {self.preview_time_offset_minutes:+d} minutes")

            elif event.key == pygame.K_PERIOD:
                # Scrub time forward (only in preview mode)
                if self.forecast_preview_mode and self.paused:
                    self.preview_time_offset_minutes = min(360, self.preview_time_offset_minutes + 10)
                    print(f"Preview time: {self.preview_time_offset_minutes:+d} minutes")

            # ===== BOAT SWITCHING =====
            elif event.key == pygame.K_TAB:
                # Cycle through boats
                if len(self.boats) > 1:
                    self.active_boat_index = (self.active_boat_index + 1) % len(self.boats)
                    print(f"Switched to {self.active_boat.name}")

            elif event.key == pygame.K_n:
                # Add new boat at current active boat position (or center if no boats)
                self._add_new_boat()

            elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                # Remove active boat (if more than one boat exists)
                if len(self.boats) > 1:
                    removed = self.boats.pop(self.active_boat_index)
                    print(f"Removed {removed.name}")
                    # Adjust active index if needed
                    if self.active_boat_index >= len(self.boats):
                        self.active_boat_index = len(self.boats) - 1
                    print(f"Active boat: {self.active_boat.name}")

            # ===== WAYPOINT MANAGEMENT =====
            elif event.key == pygame.K_m:
                # Check if shift is held for clear all
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_SHIFT:
                    # Shift+M: Clear all marks
                    self.waypoints.clear()
                    print("All waypoints cleared")
                else:
                    # M: Drop mark at current boat position
                    if self.active_boat:
                        name = f"Mark {len(self.waypoints) + 1}"
                        self.waypoints.append({
                            'lat': self.active_boat.lat,
                            'lon': self.active_boat.lon,
                            'name': name
                        })
                        print(f"Waypoint added: {name} at ({self.active_boat.lat:.4f}, {self.active_boat.lon:.4f})")

            elif event.key == pygame.K_r:
                # Reset all boats to start of course
                for boat in self.boats:
                    boat.current_waypoint_index = 0
                    boat.marks_rounded = 0
                print("All boats reset to start of course")

            # ===== AI CONTROL =====
            elif event.key == pygame.K_i:
                # Toggle AI control for active boat
                if self.active_boat:
                    if self.active_boat.is_ai_controlled:
                        self.active_boat.toggle_ai_control()
                    else:
                        # Enable AI with default router
                        from ai.router_factory import create_router
                        try:
                            router = create_router('vmg')  # Default to Greedy VMG
                            self.active_boat.set_ai_router(router)
                        except Exception as e:
                            print(f"Failed to enable AI: {e}")

            elif event.key == pygame.K_o:
                # Cycle through AI routers
                if self.active_boat and self.active_boat.ai_router:
                    self._cycle_ai_router()

            # ===== TARGET SPEED FACTOR =====
            elif event.key == pygame.K_UP:
                # Increase target speed factor by 5%
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_SHIFT:
                    if self.active_boat:
                        self.active_boat.adjust_target_speed_factor(0.05)

            elif event.key == pygame.K_DOWN:
                # Decrease target speed factor by 5%
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_SHIFT:
                    if self.active_boat:
                        self.active_boat.adjust_target_speed_factor(-0.05)

            # ===== QUIT =====
            elif event.key == pygame.K_ESCAPE:
                return 'quit'

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_CTRL or mods & pygame.KMOD_META:
                    # Ctrl/Cmd + Click: drop waypoint at mouse position
                    lat, lon = self.map_view.screen_to_latlon(event.pos[0], event.pos[1])
                    name = f"Mark {len(self.waypoints) + 1}"
                    self.waypoints.append({
                        'lat': lat,
                        'lon': lon,
                        'name': name
                    })
                    print(f"Waypoint added: {name} at ({lat:.4f}, {lon:.4f})")
                else:
                    # Check if clicking on a boat to switch active
                    clicked_boat_idx = self._check_boat_click(event.pos)
                    if clicked_boat_idx is not None:
                        self.active_boat_index = clicked_boat_idx
                        print(f"Switched to {self.active_boat.name}")
                    else:
                        # Start drag for panning
                        self.dragging = True
                        self.last_mouse_pos = event.pos

            elif event.button == 3:  # Right click - drop waypoint
                lat, lon = self.map_view.screen_to_latlon(event.pos[0], event.pos[1])
                name = f"Mark {len(self.waypoints) + 1}"
                self.waypoints.append({
                    'lat': lat,
                    'lon': lon,
                    'name': name
                })
                print(f"Waypoint added: {name} at ({lat:.4f}, {lon:.4f})")

            elif event.button == 4:  # Mouse wheel up - zoom in
                self.map_view.zoom_in()

            elif event.button == 5:  # Mouse wheel down - zoom out
                self.map_view.zoom_out()

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:  # Left button released
                self.dragging = False
                self.last_mouse_pos = None

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging and self.last_mouse_pos:
                # Pan map
                dx = event.pos[0] - self.last_mouse_pos[0]
                dy = event.pos[1] - self.last_mouse_pos[1]
                self.map_view.pan(dx, dy)
                self.last_mouse_pos = event.pos

        return None

    def get_sim_speed(self):
        """
        Get current simulation speed multiplier.

        Returns:
            Speed multiplier (0.0 to 10.0)
        """
        return self.speed_multipliers[self.sim_speed_index]

    def _check_boat_click(self, mouse_pos):
        """
        Check if mouse click is on any boat.

        Args:
            mouse_pos: (x, y) mouse position

        Returns:
            Boat index if clicked, None otherwise
        """
        click_radius = 20  # Pixels

        for idx, boat in enumerate(self.boats):
            screen_x, screen_y = self.map_view.latlon_to_screen(boat.lat, boat.lon)
            distance = math.sqrt((mouse_pos[0] - screen_x)**2 + (mouse_pos[1] - screen_y)**2)

            if distance <= click_radius:
                return idx

        return None

    def _add_new_boat(self):
        """Add a new boat to the simulation."""
        # Get position for new boat
        if self.active_boat:
            # Place near active boat (offset by 0.001 degrees ~ 100m)
            lat = self.active_boat.lat + 0.001
            lon = self.active_boat.lon + 0.001
            heading = self.active_boat.heading
            target_speed = self.active_boat.target_speed_factor
        else:
            # Place at center if no boats (shouldn't happen)
            print("Cannot add boat: no active boat")
            return

        # Choose color (cycle through predefined colors)
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 100, 255),  # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 128, 0),  # Orange
            (128, 0, 255),  # Purple
        ]
        color = colors[len(self.boats) % len(colors)]

        # Create new boat using stored polar table
        boat_name = f"Boat {len(self.boats) + 1}"
        from core.boat import Boat
        new_boat = Boat(self.polar, lat, lon, heading, target_speed, boat_name, color)

        self.boats.append(new_boat)
        self.active_boat_index = len(self.boats) - 1

        print(f"Added {boat_name} at ({lat:.4f}, {lon:.4f})")

    def _cycle_ai_router(self):
        """Cycle through available AI routers for active boat."""
        from ai.router_factory import list_routers, create_router

        routers = list_routers()
        if not routers:
            print("No AI routers available")
            return

        boat = self.active_boat
        if not boat:
            return

        # Find current router name
        current_name = boat.ai_router.get_name() if boat.ai_router else None

        # Find next router
        try:
            if current_name:
                # Try to find current in list
                router_names = [r for r in routers]
                # The get_name() returns class name, we need to match against registry keys
                # For now, just cycle through the list
                current_idx = 0
                next_idx = (current_idx + 1) % len(routers)
            else:
                next_idx = 0

            # Create new router
            next_name = routers[next_idx]
            new_router = create_router(next_name)

            boat.set_ai_router(new_router)

        except Exception as e:
            print(f"Failed to cycle router: {e}")
