"""
Startup Dialog
Interactive configuration dialog for simulation setup.
"""

import pygame
import os
import glob
from config import (
    LOCATIONS,
    SCENARIOS,
    COLOR_WATER,
    COLOR_WHITE,
    COLOR_GREEN,
    COLOR_LABEL,
    DIALOG_TITLE_SIZE,
    DIALOG_OPTION_SIZE,
    DIALOG_DESCRIPTION_SIZE
)


class StartupDialog:
    """
    Interactive startup configuration dialog.
    Users select location, heading, time mode, and scenario.
    """

    def __init__(self, screen, geography=None):
        """
        Initialize startup dialog.

        Args:
            screen: Pygame display surface
            geography: Optional GeographyProvider for custom location selection
        """
        self.screen = screen
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()
        self.geography = geography

        # Options
        self.locations = list(LOCATIONS.keys()) + ['Custom...']
        self.scenarios = list(SCENARIOS.keys())

        # Find available polar tables
        self.polar_files = self._find_polar_files()
        self.polar_names = [os.path.splitext(os.path.basename(f))[0] for f in self.polar_files]

        # Selections
        self.selected_location = 0
        self.selected_heading = 270  # Default: West
        self.forecast_hours = 0  # Hours into the future (0=current, up to 48)
        self.selected_scenario = 0
        self.selected_polar = 0  # Default to first polar found
        self.target_speed_factor = 1.0  # Default: 100% (ideal conditions)

        # Custom location state
        self.custom_mode = False
        self.custom_lat = None
        self.custom_lon = None

        # Text input state
        self.editing_lat = False
        self.editing_lon = False
        self.lat_input = ""
        self.lon_input = ""

        # Fonts
        self.font_title = pygame.font.SysFont('monospace', DIALOG_TITLE_SIZE, bold=True)
        self.font_option = pygame.font.SysFont('monospace', DIALOG_OPTION_SIZE, bold=True)
        self.font_description = pygame.font.SysFont('monospace', DIALOG_DESCRIPTION_SIZE)
        self.font_small = pygame.font.SysFont('monospace', 14)

    def _find_polar_files(self):
        """Find all polar table JSON files in assets/polars directory."""
        polar_files = glob.glob('assets/polars/*.json')
        if not polar_files:
            # Fallback to default if none found
            return ['assets/polars/default_keelboat.json']
        return sorted(polar_files)

    def _handle_custom_click(self, mouse_pos):
        """
        Handle mouse click for custom location selection.

        Args:
            mouse_pos: (x, y) tuple of mouse position
        """
        if not self.geography:
            return

        # Define map preview area (left side of screen)
        map_x = 50
        map_y = 150
        map_width = 600
        map_height = 600

        # Check if click is within map preview area
        if not (map_x <= mouse_pos[0] <= map_x + map_width and
                map_y <= mouse_pos[1] <= map_y + map_height):
            return

        # Convert screen position to lat/lon
        # Simple projection based on geography bounds
        min_lat, min_lon, max_lat, max_lon = self.geography.get_bounds()

        # Calculate position within map area
        rel_x = (mouse_pos[0] - map_x) / map_width
        rel_y = (mouse_pos[1] - map_y) / map_height

        # Map to lat/lon (Y is flipped)
        self.custom_lon = min_lon + rel_x * (max_lon - min_lon)
        self.custom_lat = max_lat - rel_y * (max_lat - min_lat)

        self.custom_mode = True
        print(f"Custom location selected: ({self.custom_lat:.4f}, {self.custom_lon:.4f})")

    def _check_input_field_click(self, mouse_pos):
        """
        Check if user clicked on lat or lon input field.

        Args:
            mouse_pos: (x, y) tuple

        Returns:
            True if clicked on input field, False otherwise
        """
        # Input field positions (right side of screen)
        x = 700
        lat_y = 500
        lon_y = 550
        field_width = 250
        field_height = 30

        # Check lat field
        if (x <= mouse_pos[0] <= x + field_width and
            lat_y <= mouse_pos[1] <= lat_y + field_height):
            self.editing_lat = True
            self.editing_lon = False
            if not self.lat_input and self.custom_lat is not None:
                self.lat_input = f"{self.custom_lat:.4f}"
            return True

        # Check lon field
        if (x <= mouse_pos[0] <= x + field_width and
            lon_y <= mouse_pos[1] <= lon_y + field_height):
            self.editing_lon = True
            self.editing_lat = False
            if not self.lon_input and self.custom_lon is not None:
                self.lon_input = f"{self.custom_lon:.4f}"
            return True

        return False

    def _apply_text_input(self):
        """Parse and apply text input for lat/lon."""
        try:
            if self.editing_lat and self.lat_input:
                lat = float(self.lat_input)
                # Validate range
                if -90 <= lat <= 90:
                    self.custom_lat = lat
                    print(f"Latitude set to: {lat:.4f}°")
                else:
                    print(f"Invalid latitude: {lat} (must be -90 to 90)")

            if self.editing_lon and self.lon_input:
                lon = float(self.lon_input)
                # Validate range
                if -180 <= lon <= 180:
                    self.custom_lon = lon
                    print(f"Longitude set to: {lon:.4f}°")
                else:
                    print(f"Invalid longitude: {lon} (must be -180 to 180)")

            # Clear input buffers
            self.lat_input = ""
            self.lon_input = ""

        except ValueError:
            print("Invalid number format")
            self.lat_input = ""
            self.lon_input = ""

    def show(self):
        """
        Display dialog and wait for user configuration.

        Returns:
            Configuration dict with selected values, or None if user quit
        """
        clock = pygame.time.Clock()
        running = True

        while running:
            clock.tick(30)  # 30 FPS for dialog

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None

                elif event.type == pygame.KEYDOWN:
                    # Handle text input for lat/lon in custom mode
                    if self.editing_lat or self.editing_lon:
                        if event.key == pygame.K_RETURN:
                            # Confirm input
                            self._apply_text_input()
                            self.editing_lat = False
                            self.editing_lon = False
                        elif event.key == pygame.K_ESCAPE:
                            # Cancel input
                            self.editing_lat = False
                            self.editing_lon = False
                            self.lat_input = ""
                            self.lon_input = ""
                        elif event.key == pygame.K_BACKSPACE:
                            # Delete character
                            if self.editing_lat:
                                self.lat_input = self.lat_input[:-1]
                            else:
                                self.lon_input = self.lon_input[:-1]
                        else:
                            # Add character if valid (numbers, minus, decimal)
                            char = event.unicode
                            if char in '0123456789.-':
                                if self.editing_lat:
                                    self.lat_input += char
                                else:
                                    self.lon_input += char
                        continue  # Skip other key handling while editing

                    if event.key == pygame.K_UP:
                        self.selected_location = (self.selected_location - 1) % len(self.locations)
                        # Exit custom mode if we move away from Custom
                        if self.locations[self.selected_location] != 'Custom...':
                            self.custom_mode = False

                    elif event.key == pygame.K_DOWN:
                        self.selected_location = (self.selected_location + 1) % len(self.locations)
                        # Exit custom mode if we move away from Custom
                        if self.locations[self.selected_location] != 'Custom...':
                            self.custom_mode = False

                    elif event.key == pygame.K_LEFT:
                        self.selected_heading = (self.selected_heading - 10) % 360

                    elif event.key == pygame.K_RIGHT:
                        self.selected_heading = (self.selected_heading + 10) % 360

                    elif event.key == pygame.K_t:
                        # Cycle forecast hours: 0, 6, 12, 18, 24, 36, 48
                        hours_options = [0, 6, 12, 18, 24, 36, 48]
                        current_idx = hours_options.index(self.forecast_hours) if self.forecast_hours in hours_options else 0
                        next_idx = (current_idx + 1) % len(hours_options)
                        self.forecast_hours = hours_options[next_idx]

                    elif event.key == pygame.K_COMMA:
                        # Decrease forecast hour by 1
                        self.forecast_hours = max(0, self.forecast_hours - 1)

                    elif event.key == pygame.K_PERIOD:
                        # Increase forecast hour by 1
                        self.forecast_hours = min(48, self.forecast_hours + 1)

                    elif event.key == pygame.K_s:
                        self.selected_scenario = (self.selected_scenario + 1) % len(self.scenarios)

                    elif event.key == pygame.K_p:
                        self.selected_polar = (self.selected_polar + 1) % len(self.polar_files)

                    elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                        # Increase target speed factor by 5%
                        self.target_speed_factor = min(1.0, self.target_speed_factor + 0.05)

                    elif event.key == pygame.K_MINUS:
                        # Decrease target speed factor by 5%
                        self.target_speed_factor = max(0.1, self.target_speed_factor - 0.05)

                    elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        # Start simulation
                        running = False

                    elif event.key == pygame.K_ESCAPE:
                        return None

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Check if in custom mode
                    if self.locations[self.selected_location] == 'Custom...' and self.geography:
                        if event.button == 1:  # Left click
                            # Check if clicking on input fields
                            if self._check_input_field_click(event.pos):
                                continue
                            # Otherwise, clicking on map to set position
                            self._handle_custom_click(event.pos)

            # Render dialog
            self._render()
            pygame.display.flip()

        # Build configuration dict
        location_name = self.locations[self.selected_location]

        # Use custom location if selected, otherwise use predefined
        if location_name == 'Custom...' and self.custom_lat is not None and self.custom_lon is not None:
            lat, lon = self.custom_lat, self.custom_lon
        elif location_name == 'Custom...':
            # Custom selected but not set - use default
            lat, lon = LOCATIONS['Golden Gate']
            location_name = 'Golden Gate'
        else:
            lat, lon = LOCATIONS[location_name]

        scenario_name = self.scenarios[self.selected_scenario]
        polar_path = self.polar_files[self.selected_polar]

        return {
            'lat': lat,
            'lon': lon,
            'heading': self.selected_heading,
            'forecast_hours': self.forecast_hours,
            'scenario': scenario_name if scenario_name != 'None' else None,
            'location_name': location_name,
            'polar_path': polar_path,
            'target_speed_factor': self.target_speed_factor
        }

    def _render(self):
        """Render dialog contents."""
        self.screen.fill(COLOR_WATER)

        # Check if showing custom location mode
        is_custom_selected = self.locations[self.selected_location] == 'Custom...'

        if is_custom_selected and self.geography:
            # Show map preview for custom location selection
            self._render_custom_mode()
        else:
            # Show standard dialog
            self._render_standard_mode()

    def _render_standard_mode(self):
        """Render standard dialog mode."""
        # Title
        title = self.font_title.render("SF BAY SAILING SIMULATOR", True, COLOR_WHITE)
        title_rect = title.get_rect(center=(self.screen_width // 2, 50))
        self.screen.blit(title, title_rect)

        y = 120

        # Location selection
        self._render_section("LOCATION", y)
        y += 30

        for i, location in enumerate(self.locations):
            color = COLOR_GREEN if i == self.selected_location else COLOR_LABEL
            text = self.font_option.render(f"  {location}", True, color)
            self.screen.blit(text, (200, y))
            y += 26

        y += 10

        # Heading selection
        self._render_section(f"HEADING: {self.selected_heading}°", y)
        y += 30
        hint = self.font_description.render("Use LEFT/RIGHT arrows to adjust", True, COLOR_LABEL)
        self.screen.blit(hint, (200, y))
        y += 40

        # Time mode selection
        self._render_section(f"FORECAST TIME: +{self.forecast_hours}h", y)
        y += 30
        if self.forecast_hours == 0:
            time_desc = "Current time (now)"
        else:
            time_desc = f"{self.forecast_hours} hours in the future"
        text = self.font_option.render(f"  {time_desc}", True, COLOR_GREEN)
        self.screen.blit(text, (200, y))
        y += 25
        hint = self.font_description.render("T: cycle (0,6,12,18,24,36,48) | ,/. : ±1 hour", True, COLOR_LABEL)
        self.screen.blit(hint, (200, y))
        y += 40

        # Scenario selection
        self._render_section("SCENARIO", y)
        y += 30
        scenario_name = self.scenarios[self.selected_scenario]
        scenario_desc = SCENARIOS[scenario_name]['description']
        text = self.font_option.render(f"  {scenario_name}", True, COLOR_GREEN)
        self.screen.blit(text, (200, y))
        y += 25
        desc = self.font_description.render(f"  {scenario_desc}", True, COLOR_LABEL)
        self.screen.blit(desc, (200, y))
        y += 22
        hint = self.font_description.render("Press S to cycle scenarios", True, COLOR_LABEL)
        self.screen.blit(hint, (200, y))
        y += 35

        # Polar selection
        self._render_section("BOAT / POLAR", y)
        y += 30
        polar_name = self.polar_names[self.selected_polar]
        text = self.font_option.render(f"  {polar_name}", True, COLOR_GREEN)
        self.screen.blit(text, (200, y))
        y += 25
        hint = self.font_description.render("Press P to cycle polar tables", True, COLOR_LABEL)
        self.screen.blit(hint, (200, y))
        y += 35

        # Target speed factor
        self._render_section(f"TARGET SPEED: {self.target_speed_factor*100:.0f}%", y)
        y += 30
        desc = self.font_description.render("  Accounts for sea state, crew skill, etc.", True, COLOR_LABEL)
        self.screen.blit(desc, (200, y))
        y += 22
        hint = self.font_description.render("Press +/- to adjust", True, COLOR_LABEL)
        self.screen.blit(hint, (200, y))

        # Instructions
        y = self.screen_height - 120
        inst1 = self.font_description.render("UP/DOWN: location | LEFT/RIGHT: heading | T: forecast time | ,/.: ±1h", True, COLOR_WHITE)
        inst2 = self.font_description.render("S: scenario | P: polar | +/-: target speed", True, COLOR_WHITE)
        inst3 = self.font_option.render("Press ENTER to start", True, COLOR_GREEN)

        self.screen.blit(inst1, (self.screen_width // 2 - inst1.get_width() // 2, y))
        self.screen.blit(inst2, (self.screen_width // 2 - inst2.get_width() // 2, y + 22))
        self.screen.blit(inst3, (self.screen_width // 2 - inst3.get_width() // 2, y + 55))

    def _render_custom_mode(self):
        """Render custom location selection mode with map preview."""
        # Title
        title = self.font_title.render("SELECT CUSTOM START LOCATION", True, COLOR_WHITE)
        title_rect = title.get_rect(center=(self.screen_width // 2, 50))
        self.screen.blit(title, title_rect)

        # Map preview area
        map_x = 50
        map_y = 150
        map_width = 600
        map_height = 600

        # Create map surface
        map_surface = pygame.Surface((map_width, map_height))
        map_surface.fill(COLOR_WATER)

        # Draw simplified coastline
        if self.geography:
            min_lat, min_lon, max_lat, max_lon = self.geography.get_bounds()

            # Simple projection
            for idx, feature in self.geography.gdf.iterrows():
                geom = feature.geometry

                if geom.geom_type == 'LineString':
                    points = []
                    for lon, lat in geom.coords:
                        # Map to screen
                        rel_x = (lon - min_lon) / (max_lon - min_lon)
                        rel_y = (lat - min_lat) / (max_lat - min_lat)
                        px = int(rel_x * map_width)
                        py = int((1.0 - rel_y) * map_height)  # Flip Y
                        points.append((px, py))

                    if len(points) >= 2:
                        pygame.draw.lines(map_surface, COLOR_LABEL, False, points, 1)

            # Draw selected position if set
            if self.custom_lat is not None and self.custom_lon is not None:
                rel_x = (self.custom_lon - min_lon) / (max_lon - min_lon)
                rel_y = (self.custom_lat - min_lat) / (max_lat - min_lat)
                px = int(rel_x * map_width)
                py = int((1.0 - rel_y) * map_height)

                # Draw crosshair
                pygame.draw.circle(map_surface, COLOR_GREEN, (px, py), 8, 2)
                pygame.draw.line(map_surface, COLOR_GREEN, (px - 12, py), (px + 12, py), 2)
                pygame.draw.line(map_surface, COLOR_GREEN, (px, py - 12), (px, py + 12), 2)

        # Draw map border
        pygame.draw.rect(map_surface, COLOR_WHITE, map_surface.get_rect(), 2)

        # Blit to screen
        self.screen.blit(map_surface, (map_x, map_y))

        # Instructions on right side
        x = 700
        y = 200

        inst = self.font_option.render("Click on map OR", True, COLOR_WHITE)
        self.screen.blit(inst, (x, y))
        y += 40

        inst = self.font_option.render("Enter coordinates:", True, COLOR_WHITE)
        self.screen.blit(inst, (x, y))
        y += 60

        # Latitude input field
        lat_label = self.font_description.render("Latitude:", True, COLOR_LABEL)
        self.screen.blit(lat_label, (x, y))
        y += 25

        # Draw input box for latitude
        lat_box = pygame.Rect(x, y, 250, 30)
        box_color = COLOR_GREEN if self.editing_lat else COLOR_LABEL
        pygame.draw.rect(self.screen, (30, 30, 30), lat_box)
        pygame.draw.rect(self.screen, box_color, lat_box, 2)

        # Show input text or current value
        if self.editing_lat:
            display_text = self.lat_input + "_"
        elif self.custom_lat is not None:
            display_text = f"{self.custom_lat:.4f}"
        else:
            display_text = "Click to edit"

        text_surface = self.font_description.render(display_text, True, COLOR_WHITE)
        self.screen.blit(text_surface, (x + 5, y + 5))
        y += 50

        # Longitude input field
        lon_label = self.font_description.render("Longitude:", True, COLOR_LABEL)
        self.screen.blit(lon_label, (x, y))
        y += 25

        # Draw input box for longitude
        lon_box = pygame.Rect(x, y, 250, 30)
        box_color = COLOR_GREEN if self.editing_lon else COLOR_LABEL
        pygame.draw.rect(self.screen, (30, 30, 30), lon_box)
        pygame.draw.rect(self.screen, box_color, lon_box, 2)

        # Show input text or current value
        if self.editing_lon:
            display_text = self.lon_input + "_"
        elif self.custom_lon is not None:
            display_text = f"{self.custom_lon:.4f}"
        else:
            display_text = "Click to edit"

        text_surface = self.font_description.render(display_text, True, COLOR_WHITE)
        self.screen.blit(text_surface, (x + 5, y + 5))
        y += 50

        if self.editing_lat or self.editing_lon:
            hint = self.font_small.render("Press ENTER to confirm, ESC to cancel", True, COLOR_LABEL)
            self.screen.blit(hint, (x, y))

        # Other settings
        y += 60
        text = self.font_description.render(f"Heading: {self.selected_heading}° (use ←/→)", True, COLOR_LABEL)
        self.screen.blit(text, (x, y))
        y += 25

        text = self.font_description.render(f"Forecast: +{self.forecast_hours}h (T/,/.)", True, COLOR_LABEL)
        self.screen.blit(text, (x, y))
        y += 25

        text = self.font_description.render(f"Polar: {self.polar_names[self.selected_polar]} (P)", True, COLOR_LABEL)
        self.screen.blit(text, (x, y))
        y += 25

        text = self.font_description.render(f"Target: {self.target_speed_factor*100:.0f}% (+/-)", True, COLOR_LABEL)
        self.screen.blit(text, (x, y))

        # Bottom instructions
        y = self.screen_height - 100
        inst1 = self.font_option.render("UP/DOWN to change location type", True, COLOR_WHITE)
        inst2 = self.font_option.render("Press ENTER to start", True, COLOR_GREEN)

        self.screen.blit(inst1, (self.screen_width // 2 - inst1.get_width() // 2, y))
        self.screen.blit(inst2, (self.screen_width // 2 - inst2.get_width() // 2, y + 35))

    def _render_section(self, title, y):
        """Render section title."""
        text = self.font_option.render(title, True, COLOR_WHITE)
        self.screen.blit(text, (100, y))
