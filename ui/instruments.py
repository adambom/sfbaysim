"""
Instrument Panel
Displays boat telemetry and environmental data in dashboard panels.
"""

import pygame
import math
from config import (
    COLOR_PANEL_BG,
    COLOR_BORDER,
    COLOR_TEXT,
    COLOR_LABEL,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_WHITE,
    FONT_TITLE_SIZE,
    FONT_LABEL_SIZE,
    FONT_VALUE_SIZE,
    FONT_SMALL_SIZE,
    FONT_FAMILY,
    INSTRUMENT_PANEL_PADDING,
    INSTRUMENT_LINE_SPACING,
    INSTRUMENT_SECTION_SPACING,
    INSTRUMENT_VALUE_INDENT,
    MS_TO_KNOTS
)


class Button:
    """
    Clickable button for instrument panel.
    """
    def __init__(self, x, y, width, height, text, color=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color or COLOR_LABEL
        self.hovered = False
        self.font = pygame.font.SysFont(FONT_FAMILY, 11, bold=True)

    def draw(self, surface):
        # Background color - brighter if hovered
        bg_color = (60, 60, 60) if self.hovered else (40, 40, 40)
        pygame.draw.rect(surface, bg_color, self.rect)
        pygame.draw.rect(surface, self.color, self.rect, 2)

        # Text
        text_surface = self.font.render(self.text, True, COLOR_WHITE)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

    def check_hover(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)
        return self.hovered

    def check_click(self, mouse_pos):
        return self.rect.collidepoint(mouse_pos)


class InstrumentPanel:
    """
    Renders instrument dashboard showing boat and environmental data.
    """

    def __init__(self, x, y, width, height):
        """
        Initialize instrument panel.

        Args:
            x, y: Top-left position in pixels
            width, height: Panel dimensions in pixels
        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        # Load fonts
        self.font_title = pygame.font.SysFont(FONT_FAMILY, FONT_TITLE_SIZE, bold=True)
        self.font_label = pygame.font.SysFont(FONT_FAMILY, FONT_LABEL_SIZE)
        self.font_value = pygame.font.SysFont(FONT_FAMILY, FONT_VALUE_SIZE, bold=True)
        self.font_small = pygame.font.SysFont(FONT_FAMILY, FONT_SMALL_SIZE)

        # Buttons (will be positioned dynamically)
        self.buttons = {}

    def render(self, surface, boat, sim_time, sim_speed, load_progress, waypoints=None, is_paused=False, controls=None):
        """
        Render all instrument panels.

        Args:
            surface: Pygame surface
            boat: Boat instance
            sim_time: Simulation datetime
            sim_speed: Simulation speed multiplier
            load_progress: Dict with weather/current loading progress
            waypoints: Shared waypoints list (optional)
            is_paused: Whether simulation is paused
            controls: ControlHandler instance (for button states)
        """
        if waypoints is None:
            waypoints = []
        # Draw background
        bg_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(surface, COLOR_PANEL_BG, bg_rect)
        pygame.draw.rect(surface, COLOR_BORDER, bg_rect, 2)

        # Render panels top to bottom
        y_pos = self.y + INSTRUMENT_PANEL_PADDING

        # Render boat name header with AI indicator
        if boat.is_ai_controlled:
            boat_title = self.font_title.render(f"[AI] {boat.name}", True, boat.color)
        else:
            boat_title = self.font_title.render(f"> {boat.name}", True, boat.color)

        surface.blit(boat_title, (self.x + INSTRUMENT_PANEL_PADDING, y_pos))

        # Pause/Preview indicator and controls
        if is_paused:
            if controls and controls.forecast_preview_mode:
                # Forecast preview mode indicator
                offset = controls.preview_time_offset_minutes
                preview_text = self.font_title.render(f"FCST {offset:+d}min", True, (100, 200, 255))
                surface.blit(preview_text, (self.x + self.width - preview_text.get_width() - 10, y_pos))
            else:
                # Regular pause indicator
                pause_text = self.font_title.render("|| PAUSED", True, COLOR_RED)
                surface.blit(pause_text, (self.x + self.width - pause_text.get_width() - 10, y_pos))

        y_pos += 25

        # Show AI router name if AI-controlled
        if boat.is_ai_controlled and boat.ai_router:
            router_name_text = self.font_small.render(f"AI: {boat.ai_router.get_name()}", True, COLOR_LABEL)
            surface.blit(router_name_text, (self.x + INSTRUMENT_PANEL_PADDING, y_pos))
            y_pos += 20
        else:
            y_pos += 5

        y_pos = self._render_time_panel(surface, y_pos, sim_time, sim_speed, load_progress, boat.elapsed_time)
        y_pos = self._render_speed_panel(surface, y_pos, boat, waypoints)
        y_pos = self._render_compass_panel(surface, y_pos, boat)
        y_pos = self._render_wind_panel(surface, y_pos, boat)
        y_pos = self._render_current_panel(surface, y_pos, boat)
        y_pos = self._render_stats_panel(surface, y_pos, boat, waypoints)

        # Render control buttons at bottom
        self._render_buttons(surface, is_paused, controls)

    def _render_time_panel(self, surface, y_pos, sim_time, sim_speed, load_progress, elapsed_time):
        """Render time, date, elapsed time, simulation speed, and loading progress."""
        x = self.x + INSTRUMENT_PANEL_PADDING
        from datetime import timezone
        import time as time_module

        # Title
        title = self.font_title.render("TIME", True, COLOR_TEXT)
        surface.blit(title, (x, y_pos))
        y_pos += 25

        # Convert UTC sim_time to local time for display
        # sim_time is naive (no timezone), so add UTC timezone then convert to local
        sim_time_utc = sim_time.replace(tzinfo=timezone.utc)
        sim_time_local = sim_time_utc.astimezone()

        # Current time (Local)
        time_str = sim_time_local.strftime("%H:%M:%S")
        value = self.font_value.render(time_str, True, COLOR_TEXT)
        surface.blit(value, (x, y_pos))
        y_pos += 20

        date_str = sim_time_local.strftime("%Y-%m-%d")
        value = self.font_label.render(date_str, True, COLOR_LABEL)
        surface.blit(value, (x, y_pos))
        y_pos += 18

        # Timezone indicator
        tz_name = sim_time_local.strftime("%Z")
        tz_label = self.font_small.render(tz_name, True, COLOR_LABEL)
        surface.blit(tz_label, (x, y_pos))
        y_pos += 20

        # Elapsed time
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        elapsed_str = f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}"
        label = self.font_small.render(elapsed_str, True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        y_pos += 20

        # Simulation speed
        label = self.font_small.render(f"Speed: {sim_speed:.1f}x", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        y_pos += 18

        # Loading progress (compact)
        if load_progress['weather']['loading'] or load_progress['current']['loading']:
            if load_progress['weather']['loading']:
                prog_str = f"Wx: {load_progress['weather']['loaded']}/{load_progress['weather']['total']}"
                label = self.font_small.render(prog_str, True, COLOR_LABEL)
                surface.blit(label, (x, y_pos))
                y_pos += 16

            if load_progress['current']['loading']:
                prog_str = f"Cur: {load_progress['current']['loaded']}/{load_progress['current']['total']}"
                label = self.font_small.render(prog_str, True, COLOR_LABEL)
                surface.blit(label, (x, y_pos))
                y_pos += 16

        y_pos += 10
        return y_pos

    def _render_speed_panel(self, surface, y_pos, boat, waypoints):
        """Render speed panel: boat speed, SOG, VMG."""
        x = self.x + INSTRUMENT_PANEL_PADDING
        from core.physics import bearing_between, calculate_vmg

        # Title
        title = self.font_title.render("SPEED", True, COLOR_TEXT)
        surface.blit(title, (x, y_pos))
        y_pos += 25

        # Boat speed and SOG on one line each (compact)
        label = self.font_label.render("Boat:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{boat.boat_speed:.1f}", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        label = self.font_label.render("SOG:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{boat.sog:.1f}", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        # VMG upwind (toward wind direction)
        vmg_upwind = boat.get_vmg_upwind()
        color = COLOR_GREEN if vmg_upwind > 0 else COLOR_RED
        label = self.font_label.render("VMG:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{vmg_upwind:.1f}", True, color)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        # Target speed factor
        label = self.font_small.render(f"Target: {boat.target_speed_factor*100:.0f}%", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        y_pos += 18

        # VMG to current target mark (course racing)
        vmg_to_mark = boat.get_vmg_to_current_mark(waypoints)
        if vmg_to_mark is not None and vmg_to_mark != 0.0:
            color = COLOR_GREEN if vmg_to_mark > 0 else COLOR_RED
            label = self.font_small.render("VMG->Mark:", True, COLOR_LABEL)
            surface.blit(label, (x, y_pos))
            value = self.font_label.render(f"{vmg_to_mark:.1f}", True, color)
            surface.blit(value, (x + 100, y_pos))
            y_pos += 20

        y_pos += 10
        return y_pos

    def _render_compass_panel(self, surface, y_pos, boat):
        """Render compass panel: heading, COG."""
        x = self.x + INSTRUMENT_PANEL_PADDING

        # Title
        title = self.font_title.render("COMPASS", True, COLOR_TEXT)
        surface.blit(title, (x, y_pos))
        y_pos += 25

        # Heading and COG on one line each (compact)
        label = self.font_label.render("Hdg:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{boat.heading:.0f}°", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        label = self.font_label.render("COG:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{boat.cog:.0f}°", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        y_pos += 10
        return y_pos

    def _render_wind_panel(self, surface, y_pos, boat):
        """Render wind panel: TWD, TWA, TWS, AWA, AWS."""
        x = self.x + INSTRUMENT_PANEL_PADDING
        from core.physics import normalize_angle

        # Title
        title = self.font_title.render("WIND", True, COLOR_TEXT)
        surface.blit(title, (x, y_pos))
        y_pos += 25

        # True wind direction (calculated from heading + TWA)
        twd = normalize_angle(boat.heading + boat.twa)
        label = self.font_label.render("TWD:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{twd:.0f}°", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        # TWA with port/starboard indicator (compact)
        tack_indicator = "P" if boat.twa < 0 else "S"
        tack_color = COLOR_RED if boat.twa < 0 else COLOR_GREEN

        label = self.font_label.render("TWA:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{abs(boat.twa):.0f}°", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        tack = self.font_value.render(tack_indicator, True, tack_color)
        surface.blit(tack, (x + 200, y_pos))
        y_pos += 22

        # TWS
        label = self.font_label.render("TWS:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{boat.tws:.1f}", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        # AWA (compact)
        label = self.font_label.render("AWA:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{abs(boat.awa):.0f}°", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        # AWS
        label = self.font_label.render("AWS:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{boat.aws:.1f}", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        y_pos += 10
        return y_pos

    def _render_current_panel(self, surface, y_pos, boat):
        """Render current panel: speed and set (direction)."""
        x = self.x + INSTRUMENT_PANEL_PADDING

        # Title
        title = self.font_title.render("CURRENT", True, COLOR_TEXT)
        surface.blit(title, (x, y_pos))
        y_pos += 25

        # Calculate current speed and direction from u/v
        current_speed_ms = math.sqrt(boat.current_u**2 + boat.current_v**2)
        current_speed_kts = current_speed_ms * MS_TO_KNOTS

        # Current set (direction current flows TO)
        if current_speed_ms > 0.01:
            current_set = math.degrees(math.atan2(boat.current_u, boat.current_v)) % 360
        else:
            current_set = 0.0

        # Compact display
        label = self.font_label.render("Speed:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{current_speed_kts:.2f}", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        label = self.font_label.render("Set:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{current_set:.0f}°", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        y_pos += 10
        return y_pos

    def _render_stats_panel(self, surface, y_pos, boat, waypoints):
        """Render statistics panel: distance traveled and course progress."""
        x = self.x + INSTRUMENT_PANEL_PADDING

        # Title
        title = self.font_title.render("STATS", True, COLOR_TEXT)
        surface.blit(title, (x, y_pos))
        y_pos += 25

        # Distance (compact)
        label = self.font_label.render("Dist:", True, COLOR_LABEL)
        surface.blit(label, (x, y_pos))
        value = self.font_value.render(f"{boat.distance_nm:.2f}", True, COLOR_TEXT)
        surface.blit(value, (x + 100, y_pos))
        y_pos += 22

        # Course progress (if racing)
        if waypoints:
            # Show which mark boat is targeting
            if boat.current_waypoint_index < len(waypoints):
                mark = waypoints[boat.current_waypoint_index]
                dist = boat.get_distance_to_current_mark(waypoints)

                # Current target mark
                label = self.font_small.render(f"->{mark['name']}:", True, COLOR_LABEL)
                surface.blit(label, (x, y_pos))
                value = self.font_label.render(f"{dist:.2f}", True, COLOR_TEXT)
                surface.blit(value, (x + 100, y_pos))
                y_pos += 20

                # Progress through course
                progress_text = f"{boat.marks_rounded}/{len(waypoints)} marks"
                label = self.font_small.render(progress_text, True, COLOR_LABEL)
                surface.blit(label, (x, y_pos))
                y_pos += 18
            else:
                # Finished course
                label = self.font_small.render("FINISHED!", True, COLOR_GREEN)
                surface.blit(label, (x, y_pos))
                y_pos += 20

        return y_pos

    def _render_buttons(self, surface, is_paused, controls=None):
        """Render clickable control buttons."""
        x = self.x + INSTRUMENT_PANEL_PADDING
        y = self.height - 260  # Position near bottom

        # Section title
        title = self.font_title.render("CONTROLS", True, COLOR_TEXT)
        surface.blit(title, (x, y))
        y += 30

        button_width = 85
        button_height = 30
        button_spacing = 5

        # Create buttons dynamically
        self.buttons = {}

        # Row 1: Simulation controls
        row_y = y
        self.buttons['pause'] = Button(x, row_y, button_width, button_height,
                                       "RESUME" if is_paused else "PAUSE",
                                       COLOR_GREEN if is_paused else COLOR_RED)
        self.buttons['add_boat'] = Button(x + button_width + button_spacing, row_y,
                                          button_width, button_height, "+ BOAT", COLOR_GREEN)

        # AI button - show green if AI is on
        ai_active = controls and controls.active_boat and controls.active_boat.is_ai_controlled
        self.buttons['toggle_ai'] = Button(x + (button_width + button_spacing) * 2, row_y,
                                           button_width, button_height, "[AI]",
                                           COLOR_GREEN if ai_active else COLOR_LABEL)

        # Row 2: Maneuvers
        row_y += button_height + button_spacing
        self.buttons['tack'] = Button(x, row_y, button_width, button_height, "TACK", COLOR_LABEL)
        self.buttons['gybe'] = Button(x + button_width + button_spacing, row_y,
                                      button_width, button_height, "GYBE", COLOR_LABEL)
        self.buttons['center'] = Button(x + (button_width + button_spacing) * 2, row_y,
                                        button_width, button_height, "CENTER", COLOR_LABEL)

        # Row 3: Overlays
        row_y += button_height + button_spacing
        wind_on = controls and controls.show_wind_overlay
        current_on = controls and controls.show_current_overlay
        course_on = controls and controls.show_course_lines

        self.buttons['wind'] = Button(x, row_y, button_width, button_height, "WIND",
                                      COLOR_GREEN if wind_on else COLOR_LABEL)
        self.buttons['current'] = Button(x + button_width + button_spacing, row_y,
                                         button_width, button_height, "CURRENT",
                                         COLOR_GREEN if current_on else COLOR_LABEL)
        self.buttons['course'] = Button(x + (button_width + button_spacing) * 2, row_y,
                                        button_width, button_height, "COURSE",
                                        COLOR_GREEN if course_on else COLOR_LABEL)

        # Row 4: More overlays
        row_y += button_height + button_spacing
        marks_on = controls and controls.show_mark_lines
        help_on = controls and controls.show_help

        self.buttons['marks'] = Button(x, row_y, button_width, button_height, "MARKS",
                                       COLOR_GREEN if marks_on else COLOR_LABEL)
        self.buttons['help'] = Button(x + button_width + button_spacing, row_y,
                                      button_width, button_height, "HELP",
                                      COLOR_GREEN if help_on else COLOR_LABEL)
        self.buttons['reset'] = Button(x + (button_width + button_spacing) * 2, row_y,
                                       button_width, button_height, "RESET", COLOR_LABEL)

        # Row 5: Forecast preview (only when paused)
        if is_paused:
            row_y += button_height + button_spacing + 10  # Extra space

            # Forecast label
            label = self.font_small.render("FORECAST:", True, COLOR_LABEL)
            surface.blit(label, (x, row_y - 15))

            preview_on = controls and controls.forecast_preview_mode
            self.buttons['forecast'] = Button(x, row_y, button_width, button_height, "PREVIEW",
                                             (100, 200, 255) if preview_on else COLOR_LABEL)

            # Time scrubbing buttons (only if preview active)
            if preview_on:
                btn_small = 40
                self.buttons['time_back'] = Button(x + button_width + button_spacing, row_y,
                                                   btn_small, button_height, "<", COLOR_LABEL)
                self.buttons['time_fwd'] = Button(x + button_width + button_spacing + btn_small + button_spacing,
                                                  row_y, btn_small, button_height, ">", COLOR_LABEL)

                # Show time offset
                if controls:
                    offset_text = f"{controls.preview_time_offset_minutes:+d}m"
                    offset_label = self.font_small.render(offset_text, True, (100, 200, 255))
                    surface.blit(offset_label, (x + button_width + button_spacing + 2*btn_small + 2*button_spacing + 10, row_y + 8))

        # Draw all buttons
        for button in self.buttons.values():
            button.draw(surface)

    def handle_button_click(self, mouse_pos, controls):
        """
        Handle button clicks.

        Args:
            mouse_pos: (x, y) mouse position
            controls: ControlHandler instance

        Returns:
            True if a button was clicked, False otherwise
        """
        if 'pause' in self.buttons and self.buttons['pause'].check_click(mouse_pos):
            controls.paused = not controls.paused
            print(f"Simulation {'PAUSED' if controls.paused else 'RESUMED'}")
            return True

        if 'tack' in self.buttons and self.buttons['tack'].check_click(mouse_pos):
            if controls.active_boat:
                controls.active_boat.tack()
            return True

        if 'gybe' in self.buttons and self.buttons['gybe'].check_click(mouse_pos):
            if controls.active_boat:
                controls.active_boat.gybe()
            return True

        if 'add_boat' in self.buttons and self.buttons['add_boat'].check_click(mouse_pos):
            controls._add_new_boat()
            return True

        if 'center' in self.buttons and self.buttons['center'].check_click(mouse_pos):
            if controls.active_boat:
                controls.map_view.center_on_boat(controls.active_boat)
                print(f"Centered on {controls.active_boat.name}")
            return True

        if 'wind' in self.buttons and self.buttons['wind'].check_click(mouse_pos):
            controls.show_wind_overlay = not controls.show_wind_overlay
            print(f"Wind overlay {'ON' if controls.show_wind_overlay else 'OFF'}")
            return True

        if 'current' in self.buttons and self.buttons['current'].check_click(mouse_pos):
            controls.show_current_overlay = not controls.show_current_overlay
            print(f"Current overlay {'ON' if controls.show_current_overlay else 'OFF'}")
            return True

        if 'course' in self.buttons and self.buttons['course'].check_click(mouse_pos):
            controls.show_course_lines = not controls.show_course_lines
            print(f"Course lines {'ON' if controls.show_course_lines else 'OFF'}")
            return True

        if 'marks' in self.buttons and self.buttons['marks'].check_click(mouse_pos):
            controls.show_mark_lines = not controls.show_mark_lines
            print(f"Mark lines {'ON' if controls.show_mark_lines else 'OFF'}")
            return True

        if 'help' in self.buttons and self.buttons['help'].check_click(mouse_pos):
            controls.show_help = not controls.show_help
            return True

        if 'reset' in self.buttons and self.buttons['reset'].check_click(mouse_pos):
            for boat in controls.boats:
                boat.current_waypoint_index = 0
                boat.marks_rounded = 0
            print("All boats reset to start of course")
            return True

        # Forecast preview buttons (only when paused)
        if 'forecast' in self.buttons and self.buttons['forecast'].check_click(mouse_pos):
            controls.forecast_preview_mode = not controls.forecast_preview_mode
            if controls.forecast_preview_mode:
                controls.preview_time_offset_minutes = 0
                print("Forecast preview mode ON")
            else:
                controls.preview_time_offset_minutes = 0
                print("Forecast preview mode OFF")
            return True

        if 'time_back' in self.buttons and self.buttons['time_back'].check_click(mouse_pos):
            if controls.forecast_preview_mode:
                controls.preview_time_offset_minutes = max(-60, controls.preview_time_offset_minutes - 10)
                print(f"Preview time: {controls.preview_time_offset_minutes:+d} minutes")
            return True

        if 'time_fwd' in self.buttons and self.buttons['time_fwd'].check_click(mouse_pos):
            if controls.forecast_preview_mode:
                controls.preview_time_offset_minutes = min(360, controls.preview_time_offset_minutes + 10)
                print(f"Preview time: {controls.preview_time_offset_minutes:+d} minutes")
            return True

        if 'toggle_ai' in self.buttons and self.buttons['toggle_ai'].check_click(mouse_pos):
            if controls.active_boat:
                if controls.active_boat.is_ai_controlled:
                    controls.active_boat.toggle_ai_control()
                else:
                    from ai.router_factory import create_router
                    try:
                        router = create_router('vmg')
                        controls.active_boat.set_ai_router(router)
                    except Exception as e:
                        print(f"Failed to enable AI: {e}")
            return True

        return False

    def update_button_hover(self, mouse_pos):
        """Update hover state for all buttons."""
        for button in self.buttons.values():
            button.check_hover(mouse_pos)


class ControlsHelpOverlay:
    """
    Displays keyboard controls help overlay.
    """

    def __init__(self):
        """Initialize help overlay."""
        self.font_title = pygame.font.SysFont(FONT_FAMILY, 24, bold=True)
        self.font_text = pygame.font.SysFont(FONT_FAMILY, 16)

    def render(self, surface):
        """
        Render help overlay (semi-transparent).

        Args:
            surface: Pygame surface
        """
        # Create semi-transparent overlay
        screen_width = surface.get_width()
        screen_height = surface.get_height()

        overlay = pygame.Surface((700, 600))
        overlay.set_alpha(230)
        overlay.fill((40, 40, 40))

        # Border
        pygame.draw.rect(overlay, COLOR_WHITE, overlay.get_rect(), 3)

        # Title
        title = self.font_title.render("KEYBOARD CONTROLS", True, COLOR_WHITE)
        overlay.blit(title, (200, 20))

        # Controls list
        y = 70
        controls = [
            ("BOATS", ""),
            ("  TAB", "Switch between boats"),
            ("  N key", "Add new boat"),
            ("  DELETE", "Remove active boat"),
            ("  Click boat", "Select boat"),
            ("", ""),
            ("AI CONTROL", ""),
            ("  I key", "Toggle AI control"),
            ("  O key", "Cycle AI routers"),
            ("", ""),
            ("COURSE RACING", ""),
            ("  M key", "Drop mark (builds course)"),
            ("  R key", "Reset boats to start"),
            ("  Auto-advance", "Boats round marks in order"),
            ("", ""),
            ("HEADING", ""),
            ("  LEFT/RIGHT arrows", "Adjust heading ±10°"),
            ("  A / D keys", "Fine adjust ±2°"),
            ("", ""),
            ("MANEUVERS", ""),
            ("  T key", "Tack through wind"),
            ("  G key", "Gybe downwind"),
            ("", ""),
            ("SIMULATION", ""),
            ("  SPACE", "Pause/Resume"),
            ("  + / - keys", "Sim speed up/down"),
            ("", ""),
            ("FORECAST PREVIEW (while paused)", ""),
            ("  F key", "Toggle preview mode"),
            ("  , / . keys", "Scrub time -/+ 10 min"),
            ("", ""),
            ("BOAT PERFORMANCE", ""),
            ("  Shift+UP", "Target speed +5%"),
            ("  Shift+DOWN", "Target speed -5%"),
            ("", ""),
            ("VIEW", ""),
            ("  C key", "Center on boat"),
            ("  [ / ] keys", "Zoom out/in"),
            ("  Mouse wheel", "Zoom in/out"),
            ("  Left drag", "Pan map"),
            ("  L key", "Toggle course lines"),
            ("  K key", "Toggle mark lines"),
            ("  W key", "Toggle wind overlay"),
            ("  U key", "Toggle current overlay"),
            ("  H key", "Toggle this help"),
            ("", ""),
            ("WAYPOINTS", ""),
            ("  M key", "Drop mark at boat"),
            ("  Shift+M", "Clear all marks"),
            ("  Right click", "Drop mark at mouse"),
            ("", ""),
            ("  ESC", "Quit simulator"),
        ]

        for text, description in controls:
            if text and not text.startswith(" "):
                # Section header
                label = self.font_title.render(text, True, COLOR_GREEN)
                overlay.blit(label, (40, y))
                y += 35
            elif text:
                # Control
                key = self.font_text.render(text, True, COLOR_TEXT)
                overlay.blit(key, (40, y))

                if description:
                    desc = self.font_text.render(description, True, COLOR_LABEL)
                    overlay.blit(desc, (300, y))

                y += 25

        # Blit to center of screen
        x_pos = (screen_width - 700) // 2
        y_pos = (screen_height - 600) // 2
        surface.blit(overlay, (x_pos, y_pos))
