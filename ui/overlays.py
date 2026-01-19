"""
Vector Field Overlays
Renders wind and current vector fields as colored arrows.
Includes tooltips on hover showing magnitude and direction.
"""

import pygame
import math
from config import (
    VECTOR_SCALE_FACTOR,
    VECTOR_ARROW_WIDTH,
    VECTOR_ARROWHEAD_SIZE,
    COLOR_WIND_LIGHT,
    COLOR_WIND_MODERATE,
    COLOR_WIND_STRONG,
    COLOR_WIND_VERY_STRONG,
    COLOR_CURRENT_WEAK,
    COLOR_CURRENT_LIGHT,
    COLOR_CURRENT_MODERATE,
    COLOR_CURRENT_STRONG,
    COLOR_WHITE,
    COLOR_BLACK,
    VIEWPORT_CULL_MARGIN
)


class VectorFieldOverlay:
    """
    Renders vector fields (wind/current) as arrows with color-coded magnitudes.
    """

    def __init__(self, map_view):
        """
        Initialize vector field overlay.

        Args:
            map_view: MapView instance for coordinate projection
        """
        self.map_view = map_view
        self.font = pygame.font.SysFont('monospace', 12)

    def render_wind_field(self, surface, grid_data, mouse_pos):
        """
        Render wind vectors as green arrows.

        Args:
            surface: Pygame surface
            grid_data: List of (lat, lon, direction, speed) tuples
            mouse_pos: Mouse position (x, y) for hover detection
        """
        hover_info = None

        for lat, lon, wind_dir, wind_speed in grid_data:
            # Convert to screen coordinates
            screen_x, screen_y = self.map_view.latlon_to_screen(lat, lon)

            # Viewport culling
            if not self._is_on_screen(screen_x, screen_y):
                continue

            # Calculate arrow (scaled down to match current vector sizes)
            arrow_length = wind_speed * VECTOR_SCALE_FACTOR * 0.75  # Reduced from 1.0 to 0.75

            # Convert wind direction to screen angle
            # Wind direction is FROM (meteorological), but we want to show where it's blowing TO
            # So flip by 180 degrees to show the blowing direction (more intuitive)
            wind_to_dir = (wind_dir + 180) % 360
            angle_rad = math.radians(90 - wind_to_dir)

            end_x = screen_x + arrow_length * math.cos(angle_rad)
            end_y = screen_y - arrow_length * math.sin(angle_rad)

            # Color by magnitude
            color = self._wind_color(wind_speed)

            # Draw arrow shaft (thinner than before)
            pygame.draw.line(surface, color, (screen_x, screen_y), (end_x, end_y), 2)

            # Draw arrowhead (smaller)
            self._draw_arrowhead(surface, end_x, end_y, angle_rad, 8, color)

            # Check hover
            if mouse_pos:
                dist = math.sqrt((mouse_pos[0] - screen_x)**2 + (mouse_pos[1] - screen_y)**2)
                if dist < 15:
                    hover_info = (mouse_pos[0], mouse_pos[1], wind_dir, wind_speed, "wind")

        # Render tooltip if hovering
        if hover_info:
            self._render_tooltip(surface, hover_info)

    def render_current_field(self, surface, grid_data, mouse_pos):
        """
        Render current vectors as cyan-to-red arrows.

        Args:
            surface: Pygame surface
            grid_data: List of (lat, lon, u, v, speed_kts, direction) tuples
            mouse_pos: Mouse position for hover detection
        """
        hover_info = None

        for lat, lon, u, v, speed_kts, direction in grid_data:
            # Convert to screen coordinates
            screen_x, screen_y = self.map_view.latlon_to_screen(lat, lon)

            # Viewport culling
            if not self._is_on_screen(screen_x, screen_y):
                continue

            # Calculate arrow
            arrow_length = speed_kts * VECTOR_SCALE_FACTOR * 3.0  # Scale up (currents weaker)

            # Current direction is TO (oceanographic), so arrow points that way
            angle_rad = math.radians(90 - direction)

            end_x = screen_x + arrow_length * math.cos(angle_rad)
            end_y = screen_y - arrow_length * math.sin(angle_rad)

            # Color by magnitude
            color = self._current_color(speed_kts)

            # Draw arrow shaft
            pygame.draw.line(surface, color, (screen_x, screen_y), (end_x, end_y), VECTOR_ARROW_WIDTH)

            # Draw arrowhead
            self._draw_arrowhead(surface, end_x, end_y, angle_rad, VECTOR_ARROWHEAD_SIZE, color)

            # Check hover
            if mouse_pos:
                dist = math.sqrt((mouse_pos[0] - screen_x)**2 + (mouse_pos[1] - screen_y)**2)
                if dist < 15:
                    hover_info = (mouse_pos[0], mouse_pos[1], direction, speed_kts, "current")

        # Render tooltip
        if hover_info:
            self._render_tooltip(surface, hover_info)

    def _is_on_screen(self, screen_x, screen_y):
        """
        Check if point is visible on screen (with margin).

        Args:
            screen_x, screen_y: Screen coordinates

        Returns:
            True if visible, False if off-screen
        """
        return (-VIEWPORT_CULL_MARGIN <= screen_x <= self.map_view.width + VIEWPORT_CULL_MARGIN and
                -VIEWPORT_CULL_MARGIN <= screen_y <= self.map_view.height + VIEWPORT_CULL_MARGIN)

    def _wind_color(self, speed_kts):
        """
        Get color for wind speed (gradient from light green to orange).

        Args:
            speed_kts: Wind speed in knots

        Returns:
            RGB tuple
        """
        if speed_kts < 5:
            return COLOR_WIND_LIGHT  # Light green
        elif speed_kts < 10:
            # Interpolate between light green and moderate
            fraction = (speed_kts - 5) / 5
            return self._interpolate_color(COLOR_WIND_LIGHT, COLOR_WIND_MODERATE, fraction)
        elif speed_kts < 15:
            # Interpolate between moderate and strong
            fraction = (speed_kts - 10) / 5
            return self._interpolate_color(COLOR_WIND_MODERATE, COLOR_WIND_STRONG, fraction)
        elif speed_kts < 20:
            # Interpolate between strong and very strong
            fraction = (speed_kts - 15) / 5
            return self._interpolate_color(COLOR_WIND_STRONG, COLOR_WIND_VERY_STRONG, fraction)
        else:
            return COLOR_WIND_VERY_STRONG  # Dark orange

    def _current_color(self, speed_kts):
        """
        Get color for current speed (gradient from cyan to red).

        Args:
            speed_kts: Current speed in knots

        Returns:
            RGB tuple
        """
        if speed_kts < 0.3:
            return COLOR_CURRENT_WEAK  # Cyan
        elif speed_kts < 0.6:
            # Interpolate between weak and light
            fraction = (speed_kts - 0.3) / 0.3
            return self._interpolate_color(COLOR_CURRENT_WEAK, COLOR_CURRENT_LIGHT, fraction)
        elif speed_kts < 1.0:
            # Interpolate between light and moderate
            fraction = (speed_kts - 0.6) / 0.4
            return self._interpolate_color(COLOR_CURRENT_LIGHT, COLOR_CURRENT_MODERATE, fraction)
        else:
            # Interpolate between moderate and strong
            fraction = min((speed_kts - 1.0) / 1.0, 1.0)
            return self._interpolate_color(COLOR_CURRENT_MODERATE, COLOR_CURRENT_STRONG, fraction)

    def _interpolate_color(self, color1, color2, fraction):
        """
        Linear interpolation between two colors.

        Args:
            color1: RGB tuple
            color2: RGB tuple
            fraction: Interpolation fraction (0-1)

        Returns:
            Interpolated RGB tuple
        """
        fraction = max(0.0, min(1.0, fraction))
        r = int(color1[0] + fraction * (color2[0] - color1[0]))
        g = int(color1[1] + fraction * (color2[1] - color1[1]))
        b = int(color1[2] + fraction * (color2[2] - color1[2]))
        return (r, g, b)

    def _draw_arrowhead(self, surface, x, y, angle_rad, size, color):
        """
        Draw triangular arrowhead at tip of arrow.

        Args:
            surface: Pygame surface
            x, y: Tip position
            angle_rad: Arrow direction in radians
            size: Arrowhead size in pixels
            color: RGB tuple
        """
        # Calculate three vertices of triangle
        tip = (x, y)

        left = (
            x - size * math.cos(angle_rad - 0.5),
            y + size * math.sin(angle_rad - 0.5)
        )

        right = (
            x - size * math.cos(angle_rad + 0.5),
            y + size * math.sin(angle_rad + 0.5)
        )

        vertices = [
            (int(tip[0]), int(tip[1])),
            (int(left[0]), int(left[1])),
            (int(right[0]), int(right[1]))
        ]

        pygame.draw.polygon(surface, color, vertices)

    def _render_tooltip(self, surface, hover_info):
        """
        Render tooltip showing data on hover.

        Args:
            surface: Pygame surface
            hover_info: (x, y, direction, magnitude, type) tuple
        """
        x, y, direction, magnitude, data_type = hover_info

        # Create tooltip background
        tooltip_width = 160
        tooltip_height = 55
        tooltip_x = x + 20
        tooltip_y = y - 30

        # Keep tooltip on screen
        if tooltip_x + tooltip_width > surface.get_width():
            tooltip_x = x - tooltip_width - 20
        if tooltip_y < 0:
            tooltip_y = y + 20

        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)

        # Draw background
        pygame.draw.rect(surface, (40, 40, 40), tooltip_rect)
        pygame.draw.rect(surface, COLOR_WHITE, tooltip_rect, 1)

        # Render text
        y_text = tooltip_y + 5

        if data_type == "wind":
            dir_text = self.font.render(f"Wind: {direction:.0f}°", True, COLOR_WHITE)
            mag_text = self.font.render(f"Speed: {magnitude:.1f} kts", True, COLOR_WHITE)
        else:  # current
            dir_text = self.font.render(f"Current: {direction:.0f}°", True, COLOR_WHITE)
            mag_text = self.font.render(f"Speed: {magnitude:.2f} kts", True, COLOR_WHITE)

        surface.blit(dir_text, (tooltip_x + 5, y_text))
        surface.blit(mag_text, (tooltip_x + 5, y_text + 20))
