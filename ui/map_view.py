"""
Map View - Coordinate Projection and Rendering
Handles lat/lon to screen projection, zoom/pan, and rendering of map elements.
"""

import pygame
import math
from config import (
    COLOR_WATER,
    COLOR_LAND,
    COLOR_BOAT,
    COLOR_TRACK,
    COLOR_WAYPOINT,
    COLOR_WHITE,
    COLOR_WIND_LIGHT,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_LANDMARK,
    LANDMARK_RADIUS,
    MAP_ZOOM_MIN,
    MAP_ZOOM_MAX,
    MAP_ZOOM_STEP,
    MAP_MARGIN_FACTOR,
    WIND_INDICATOR_RADIUS,
    WIND_INDICATOR_X_OFFSET,
    WIND_INDICATOR_Y_OFFSET,
    VIEWPORT_CULL_MARGIN,
    LADDER_RUNG_SPACING_M,
    LADDER_RUNG_COUNT,
    LADDER_RUNG_LENGTH_M,
    LADDER_RUNG_MIN_WIND_SPEED,
    LADDER_RUNG_COLOR,
    LADDER_RUNG_SOLID_WIDTH,
    LADDER_RUNG_DASH_WIDTH,
    LADDER_RUNG_DASH_LENGTH,
    LADDER_RUNG_GAP_LENGTH,
    LAYLINE_LENGTH_M,
    LAYLINE_MIN_WIND_SPEED,
    LAYLINE_STARBOARD_COLOR,
    LAYLINE_PORT_COLOR,
    LAYLINE_WIDTH,
)


class MapView:
    """
    Manages map projection, zoom/pan, and rendering of geographic elements.
    """

    def __init__(self, geography, map_width, map_height):
        """
        Initialize map view.

        Args:
            geography: GeographyProvider instance
            map_width: Map surface width in pixels
            map_height: Map surface height in pixels
        """
        self.geography = geography
        self.width = map_width
        self.height = map_height

        # Camera state
        center_lat, center_lon = geography.get_center()
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.zoom = 1.0

        # Calculate initial scale to fit bay in viewport
        self.base_scale = self._calculate_initial_scale()

        print(f"Map view initialized: {map_width}x{map_height} pixels")
        print(f"  Center: ({self.center_lat:.4f}, {self.center_lon:.4f})")
        print(f"  Scale: {self.base_scale:.2f} pixels/degree")

    def _calculate_initial_scale(self):
        """
        Calculate scale to fit entire bay in viewport with margin.

        Returns:
            Pixels per degree
        """
        width_deg, height_deg = self.geography.get_dimensions_deg()

        # Calculate pixels per degree for each dimension
        pixels_per_deg_lat = self.height / height_deg
        pixels_per_deg_lon = self.width / width_deg

        # Use smaller scale to ensure everything fits
        # Apply margin factor (0.9 = 10% margin)
        scale = min(pixels_per_deg_lat, pixels_per_deg_lon) * MAP_MARGIN_FACTOR

        return scale

    def latlon_to_screen(self, lat, lon):
        """
        Convert lat/lon to screen coordinates.

        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees

        Returns:
            (screen_x, screen_y) tuple in pixels
        """
        # Offset from center in degrees
        dx_deg = lon - self.center_lon
        dy_deg = lat - self.center_lat

        # Project to screen with zoom
        screen_x = self.width / 2 + dx_deg * self.base_scale * self.zoom
        screen_y = self.height / 2 - dy_deg * self.base_scale * self.zoom  # Flip Y axis

        return (screen_x, screen_y)

    def screen_to_latlon(self, screen_x, screen_y):
        """
        Convert screen coordinates to lat/lon (inverse projection).

        Args:
            screen_x: X pixel coordinate
            screen_y: Y pixel coordinate

        Returns:
            (lat, lon) tuple in degrees
        """
        # Offset from center in pixels
        dx_px = screen_x - self.width / 2
        dy_px = screen_y - self.height / 2

        # Unproject to degrees
        dx_deg = dx_px / (self.base_scale * self.zoom)
        dy_deg = -dy_px / (self.base_scale * self.zoom)  # Flip Y axis

        lat = self.center_lat + dy_deg
        lon = self.center_lon + dx_deg

        return (lat, lon)

    def render_coastline(self, surface):
        """
        Render coastline features with viewport culling.

        Args:
            surface: Pygame surface to draw on
        """
        # Calculate viewport size in meters for culling
        viewport_width_m = (self.width / (self.base_scale * self.zoom)) * 111000
        viewport_height_m = (self.height / (self.base_scale * self.zoom)) * 111000

        # Get visible features (R-tree query)
        visible_features = self.geography.get_visible_features(
            self.center_lat,
            self.center_lon,
            viewport_width_m * 1.2,  # Add margin
            viewport_height_m * 1.2
        )

        # Render each feature
        for idx, feature in visible_features.iterrows():
            geom = feature.geometry

            if geom.geom_type == 'LineString':
                # Convert coordinates to screen space
                points = []
                for lon, lat in geom.coords:
                    screen_x, screen_y = self.latlon_to_screen(lat, lon)
                    points.append((int(screen_x), int(screen_y)))

                # Draw line
                if len(points) >= 2:
                    pygame.draw.lines(surface, COLOR_LAND, False, points, 2)

            elif geom.geom_type == 'Polygon':
                # Convert exterior ring to screen space
                points = []
                for lon, lat in geom.exterior.coords:
                    screen_x, screen_y = self.latlon_to_screen(lat, lon)
                    points.append((int(screen_x), int(screen_y)))

                # Draw filled polygon
                if len(points) >= 3:
                    pygame.draw.polygon(surface, COLOR_LAND, points)
                    pygame.draw.polygon(surface, COLOR_WHITE, points, 1)  # Outline

    def render_boat(self, surface, boat, is_active=True):
        """
        Render boat as triangle pointing in heading direction.

        Args:
            surface: Pygame surface
            boat: Boat instance
            is_active: Whether this is the active/selected boat
        """
        screen_x, screen_y = self.latlon_to_screen(boat.lat, boat.lon)

        # Convert nautical heading to screen angle
        # Nautical: 0°=N, 90°=E (clockwise from north)
        # Screen: 0°=right, 90°=down (clockwise from right)
        angle_rad = math.radians(90 - boat.heading)

        size = 15  # Triangle size in pixels

        # Calculate triangle vertices
        nose_x = screen_x + size * math.cos(angle_rad)
        nose_y = screen_y - size * math.sin(angle_rad)

        base_left_x = screen_x + size * 0.6 * math.cos(angle_rad + 2.6)
        base_left_y = screen_y - size * 0.6 * math.sin(angle_rad + 2.6)

        base_right_x = screen_x + size * 0.6 * math.cos(angle_rad - 2.6)
        base_right_y = screen_y - size * 0.6 * math.sin(angle_rad - 2.6)

        vertices = [
            (int(nose_x), int(nose_y)),
            (int(base_left_x), int(base_left_y)),
            (int(base_right_x), int(base_right_y))
        ]

        # Draw filled triangle with boat's color
        pygame.draw.polygon(surface, boat.color, vertices)

        # Outline: white for active boat, gray for inactive
        outline_color = COLOR_WHITE if is_active else (150, 150, 150)
        outline_width = 3 if is_active else 2
        pygame.draw.polygon(surface, outline_color, vertices, outline_width)

        # Draw boat name label
        font = pygame.font.SysFont('monospace', 11, bold=True)
        name_text = font.render(boat.name, True, COLOR_WHITE)

        # Position label above and to the side of boat
        label_x = int(screen_x) + 20
        label_y = int(screen_y) - 20

        # Draw background for label
        label_bg = pygame.Rect(label_x - 2, label_y - 2, name_text.get_width() + 4, name_text.get_height() + 4)
        pygame.draw.rect(surface, (0, 0, 0), label_bg)
        pygame.draw.rect(surface, boat.color, label_bg, 1)

        surface.blit(name_text, (label_x, label_y))

    def render_course_lines(self, surface, boat):
        """
        Render course projection lines (heading and COG).

        Args:
            surface: Pygame surface
            boat: Boat instance
        """
        screen_x, screen_y = self.latlon_to_screen(boat.lat, boat.lon)

        # Calculate projection length (5nm in screen pixels)
        projection_nm = 5.0
        projection_m = projection_nm * 1852.0

        # Heading line (cyan) - direction boat is pointing
        heading_rad = math.radians(boat.heading)
        heading_dx = projection_m * math.sin(heading_rad)
        heading_dy = projection_m * math.cos(heading_rad)

        # Convert to screen coordinates
        heading_end_lat = boat.lat + heading_dy / 111000
        heading_end_lon = boat.lon + heading_dx / (111000 * math.cos(math.radians(boat.lat)))
        heading_end_x, heading_end_y = self.latlon_to_screen(heading_end_lat, heading_end_lon)

        # Draw heading line (cyan/light blue)
        pygame.draw.line(surface, (0, 255, 255), (screen_x, screen_y), (heading_end_x, heading_end_y), 2)

        # Label for heading line
        font = pygame.font.SysFont('monospace', 10, bold=True)
        hdg_label = font.render("HDG", True, (0, 255, 255))
        surface.blit(hdg_label, (int(heading_end_x) + 5, int(heading_end_y) - 5))

        # COG line (magenta) - actual direction of travel
        cog_rad = math.radians(boat.cog)
        cog_dx = projection_m * math.sin(cog_rad)
        cog_dy = projection_m * math.cos(cog_rad)

        # Convert to screen coordinates
        cog_end_lat = boat.lat + cog_dy / 111000
        cog_end_lon = boat.lon + cog_dx / (111000 * math.cos(math.radians(boat.lat)))
        cog_end_x, cog_end_y = self.latlon_to_screen(cog_end_lat, cog_end_lon)

        # Draw COG line
        pygame.draw.line(surface, (255, 0, 255), (screen_x, screen_y), (cog_end_x, cog_end_y), 2)

        # Label for COG line
        cog_label = font.render("COG", True, (255, 0, 255))
        surface.blit(cog_label, (int(cog_end_x) + 5, int(cog_end_y) - 5))

    def render_breadcrumbs(self, surface, boat):
        """
        Render breadcrumb trail.

        Args:
            surface: Pygame surface
            boat: Boat instance
        """
        if len(boat.breadcrumbs) < 2:
            return

        # Convert breadcrumbs to screen coordinates
        points = []
        for lat, lon in boat.breadcrumbs:
            screen_x, screen_y = self.latlon_to_screen(lat, lon)
            points.append((int(screen_x), int(screen_y)))

        # Draw trail as connected lines
        if len(points) >= 2:
            pygame.draw.lines(surface, COLOR_TRACK, False, points, 2)

    def render_waypoints(self, surface, waypoints, boats=None, show_target_lines=False):
        """
        Render waypoint markers with optional boat target indicators.

        Args:
            surface: Pygame surface
            waypoints: List of waypoint dicts
            boats: Optional list of boats (to show target lines)
            show_target_lines: Whether to show dashed lines from boats to marks
        """
        for idx, waypoint in enumerate(waypoints):
            screen_x, screen_y = self.latlon_to_screen(waypoint['lat'], waypoint['lon'])

            # Draw circle
            pygame.draw.circle(surface, COLOR_WAYPOINT, (int(screen_x), int(screen_y)), 8)
            pygame.draw.circle(surface, COLOR_WHITE, (int(screen_x), int(screen_y)), 8, 2)

            # Draw name if present
            if waypoint.get('name'):
                font = pygame.font.SysFont('monospace', 12, bold=True)
                text = font.render(waypoint['name'], True, COLOR_WHITE)

                # Background for readability
                text_bg = pygame.Rect(int(screen_x) + 10, int(screen_y) - 8, text.get_width() + 4, text.get_height() + 2)
                pygame.draw.rect(surface, (0, 0, 0), text_bg)

                surface.blit(text, (int(screen_x) + 12, int(screen_y) - 6))

            # Draw lines from boats targeting this mark (only if enabled)
            if show_target_lines and boats:
                for boat in boats:
                    if boat.current_waypoint_index == idx:
                        # This boat is targeting this mark
                        boat_x, boat_y = self.latlon_to_screen(boat.lat, boat.lon)
                        # Draw dashed line from boat to mark in boat's color
                        self._draw_dashed_line(surface, (boat_x, boat_y), (screen_x, screen_y), boat.color, 1)

    def _draw_dashed_line(self, surface, start, end, color, width):
        """Draw a dashed line between two points."""
        x1, y1 = start
        x2, y2 = end

        # Calculate distance
        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx*dx + dy*dy)

        if distance < 1:
            return

        # Dash pattern
        dash_length = 10
        gap_length = 5
        pattern_length = dash_length + gap_length

        num_dashes = int(distance / pattern_length)

        for i in range(num_dashes):
            # Calculate dash start and end
            t_start = i * pattern_length / distance
            t_end = (i * pattern_length + dash_length) / distance

            dash_start = (x1 + t_start * dx, y1 + t_start * dy)
            dash_end = (x1 + t_end * dx, y1 + t_end * dy)

            pygame.draw.line(surface, color, dash_start, dash_end, width)

    def _draw_dashed_line_params(self, surface, start, end, color, width, dash_length, gap_length):
        """Draw a dashed line with custom dash/gap parameters."""
        x1, y1 = start
        x2, y2 = end

        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx*dx + dy*dy)

        if distance < 1:
            return

        pattern_length = dash_length + gap_length
        num_dashes = int(distance / pattern_length)

        for i in range(num_dashes + 1):
            t_start = i * pattern_length / distance
            t_end = min((i * pattern_length + dash_length) / distance, 1.0)

            if t_start >= 1.0:
                break

            dash_start = (x1 + t_start * dx, y1 + t_start * dy)
            dash_end = (x1 + t_end * dx, y1 + t_end * dy)

            pygame.draw.line(surface, color, dash_start, dash_end, width)

    def render_ladder_rungs(self, surface, boat, wind_dir, wind_speed):
        """
        Render ladder rungs perpendicular to wind direction.

        Ladder rungs help visualize upwind/downwind positions relative to
        the true wind. A solid line runs through the boat position, with
        dotted lines at regular intervals upwind and downwind.

        Args:
            surface: Pygame surface to draw on
            boat: Boat instance (for position)
            wind_dir: True wind direction in degrees (FROM)
            wind_speed: True wind speed in knots
        """
        # Skip if wind too light
        if wind_speed < LADDER_RUNG_MIN_WIND_SPEED:
            return

        # Rungs are perpendicular to wind direction
        # Wind direction is FROM, so rungs are perpendicular to this
        rung_dir_rad = math.radians(wind_dir + 90)

        # Half length of each rung
        half_length_m = LADDER_RUNG_LENGTH_M / 2

        # Calculate rung endpoints relative to a center point
        def get_rung_endpoints(center_lat, center_lon):
            """Calculate screen coordinates for rung endpoints."""
            # Calculate delta in meters for perpendicular direction
            dx_m = half_length_m * math.sin(rung_dir_rad)
            dy_m = half_length_m * math.cos(rung_dir_rad)

            # Convert to lat/lon offset
            lat_factor = 1.0 / 111000  # meters to degrees lat
            lon_factor = 1.0 / (111000 * math.cos(math.radians(center_lat)))

            # Endpoint 1 (one side of rung)
            lat1 = center_lat + dy_m * lat_factor
            lon1 = center_lon + dx_m * lon_factor

            # Endpoint 2 (other side)
            lat2 = center_lat - dy_m * lat_factor
            lon2 = center_lon - dx_m * lon_factor

            # Convert to screen coordinates
            screen1 = self.latlon_to_screen(lat1, lon1)
            screen2 = self.latlon_to_screen(lat2, lon2)

            return screen1, screen2

        # Wind direction (where wind comes FROM) - offset upwind is in this direction
        wind_rad = math.radians(wind_dir)

        # Calculate offset position along wind axis
        def get_offset_position(base_lat, base_lon, offset_m):
            """Get lat/lon offset along wind direction axis."""
            # Positive offset = upwind (toward where wind comes from)
            dx_m = offset_m * math.sin(wind_rad)
            dy_m = offset_m * math.cos(wind_rad)

            lat_factor = 1.0 / 111000
            lon_factor = 1.0 / (111000 * math.cos(math.radians(base_lat)))

            new_lat = base_lat + dy_m * lat_factor
            new_lon = base_lon + dx_m * lon_factor

            return new_lat, new_lon

        # Draw solid rung through boat position
        p1, p2 = get_rung_endpoints(boat.lat, boat.lon)
        pygame.draw.line(surface, LADDER_RUNG_COLOR, p1, p2, LADDER_RUNG_SOLID_WIDTH)

        # Draw dotted rungs upwind (positive offset)
        for i in range(1, LADDER_RUNG_COUNT + 1):
            offset_m = i * LADDER_RUNG_SPACING_M
            offset_lat, offset_lon = get_offset_position(boat.lat, boat.lon, offset_m)
            p1, p2 = get_rung_endpoints(offset_lat, offset_lon)
            self._draw_dashed_line_params(surface, p1, p2, LADDER_RUNG_COLOR,
                                          LADDER_RUNG_DASH_WIDTH, LADDER_RUNG_DASH_LENGTH,
                                          LADDER_RUNG_GAP_LENGTH)

        # Draw dotted rungs downwind (negative offset)
        for i in range(1, LADDER_RUNG_COUNT + 1):
            offset_m = -i * LADDER_RUNG_SPACING_M
            offset_lat, offset_lon = get_offset_position(boat.lat, boat.lon, offset_m)
            p1, p2 = get_rung_endpoints(offset_lat, offset_lon)
            self._draw_dashed_line_params(surface, p1, p2, LADDER_RUNG_COLOR,
                                          LADDER_RUNG_DASH_WIDTH, LADDER_RUNG_DASH_LENGTH,
                                          LADDER_RUNG_GAP_LENGTH)

    def render_laylines(self, surface, waypoints, wind_dir, wind_speed, polar):
        """
        Render laylines at each waypoint showing optimal sailing angles.

        Laylines show the optimal paths for approaching marks upwind and downwind.
        Green lines indicate starboard tack/gybe, red lines indicate port.

        Args:
            surface: Pygame surface to draw on
            waypoints: List of waypoint dicts with 'lat' and 'lon' keys
            wind_dir: True wind direction in degrees (FROM)
            wind_speed: True wind speed in knots
            polar: PolarTable instance for optimal angles
        """
        # Skip if wind too light
        if wind_speed < LAYLINE_MIN_WIND_SPEED:
            return

        # Get optimal angles from polar
        optimal_upwind = polar.get_optimal_upwind_angle(wind_speed)
        optimal_downwind = polar.get_optimal_downwind_angle(wind_speed)

        def calculate_endpoint(lat, lon, heading_deg, distance_m):
            """Calculate endpoint given start position, heading and distance."""
            heading_rad = math.radians(heading_deg)

            # Delta in meters
            dx_m = distance_m * math.sin(heading_rad)
            dy_m = distance_m * math.cos(heading_rad)

            # Convert to lat/lon
            lat_factor = 1.0 / 111000
            lon_factor = 1.0 / (111000 * math.cos(math.radians(lat)))

            end_lat = lat + dy_m * lat_factor
            end_lon = lon + dx_m * lon_factor

            return end_lat, end_lon

        # Draw laylines for each waypoint
        for waypoint in waypoints:
            mark_lat = waypoint['lat']
            mark_lon = waypoint['lon']
            mark_screen = self.latlon_to_screen(mark_lat, mark_lon)

            # Upwind laylines (boat sails toward wind)
            # Wind direction is FROM, upwind direction is same as wind_dir
            # Starboard layline: wind_dir + optimal_twa + 180 (drawing FROM mark)
            # Port layline: wind_dir - optimal_twa + 180

            upwind_starboard_heading = (wind_dir + optimal_upwind + 180) % 360
            upwind_port_heading = (wind_dir - optimal_upwind + 180) % 360

            # Calculate endpoints
            up_stbd_lat, up_stbd_lon = calculate_endpoint(
                mark_lat, mark_lon, upwind_starboard_heading, LAYLINE_LENGTH_M)
            up_port_lat, up_port_lon = calculate_endpoint(
                mark_lat, mark_lon, upwind_port_heading, LAYLINE_LENGTH_M)

            up_stbd_screen = self.latlon_to_screen(up_stbd_lat, up_stbd_lon)
            up_port_screen = self.latlon_to_screen(up_port_lat, up_port_lon)

            # Draw upwind laylines
            pygame.draw.line(surface, LAYLINE_STARBOARD_COLOR, mark_screen, up_stbd_screen, LAYLINE_WIDTH)
            pygame.draw.line(surface, LAYLINE_PORT_COLOR, mark_screen, up_port_screen, LAYLINE_WIDTH)

            # Downwind laylines (boat sails away from wind)
            # Downwind direction is opposite of wind (wind_dir + 180)
            # Starboard layline: (wind_dir + 180) + (180 - optimal_downwind) + 180
            # Simplified: wind_dir + optimal_downwind (since 180 + 180 - optimal + 180 = 180 + 360 - optimal)
            # Actually: downwind approach means coming from downwind of the mark
            # Starboard: wind_dir + (180 - optimal_downwind) + 180 = wind_dir - optimal_downwind
            # Port: wind_dir - (180 - optimal_downwind) + 180 = wind_dir + optimal_downwind

            downwind_starboard_heading = (wind_dir - optimal_downwind) % 360
            downwind_port_heading = (wind_dir + optimal_downwind) % 360

            # Calculate endpoints
            dn_stbd_lat, dn_stbd_lon = calculate_endpoint(
                mark_lat, mark_lon, downwind_starboard_heading, LAYLINE_LENGTH_M)
            dn_port_lat, dn_port_lon = calculate_endpoint(
                mark_lat, mark_lon, downwind_port_heading, LAYLINE_LENGTH_M)

            dn_stbd_screen = self.latlon_to_screen(dn_stbd_lat, dn_stbd_lon)
            dn_port_screen = self.latlon_to_screen(dn_port_lat, dn_port_lon)

            # Draw downwind laylines
            pygame.draw.line(surface, LAYLINE_STARBOARD_COLOR, mark_screen, dn_stbd_screen, LAYLINE_WIDTH)
            pygame.draw.line(surface, LAYLINE_PORT_COLOR, mark_screen, dn_port_screen, LAYLINE_WIDTH)

    def render_landmarks(self, surface, landmarks, mouse_pos):
        """
        Render landmark markers with hover tooltips.

        Args:
            surface: Pygame surface to draw on
            landmarks: List of landmark dicts with 'name', 'description', 'lat', 'lon'
            mouse_pos: Current mouse position (x, y)
        """
        hover_threshold = 15  # Pixels - distance to trigger hover
        hovered_landmark = None
        hovered_screen_pos = None

        for landmark in landmarks:
            screen_x, screen_y = self.latlon_to_screen(landmark['lat'], landmark['lon'])

            # Draw filled circle with white outline
            pygame.draw.circle(surface, COLOR_LANDMARK, (int(screen_x), int(screen_y)), LANDMARK_RADIUS)
            pygame.draw.circle(surface, COLOR_WHITE, (int(screen_x), int(screen_y)), LANDMARK_RADIUS, 1)

            # Check if mouse is hovering over this landmark
            if mouse_pos:
                distance = math.sqrt((mouse_pos[0] - screen_x)**2 + (mouse_pos[1] - screen_y)**2)
                if distance <= hover_threshold:
                    hovered_landmark = landmark
                    hovered_screen_pos = (screen_x, screen_y)

        # Render tooltip for hovered landmark (after all circles so it's on top)
        if hovered_landmark and hovered_screen_pos:
            font = pygame.font.SysFont('monospace', 12, bold=True)
            font_small = pygame.font.SysFont('monospace', 10)

            # Tooltip text
            name_text = font.render(hovered_landmark['name'], True, COLOR_WHITE)
            coord_text = font_small.render(
                f"{hovered_landmark['lat']:.4f}, {hovered_landmark['lon']:.4f}",
                True, COLOR_LANDMARK
            )

            # Calculate tooltip dimensions
            tooltip_width = max(name_text.get_width(), coord_text.get_width()) + 10
            tooltip_height = name_text.get_height() + coord_text.get_height() + 8

            # Position tooltip above and to the right of the landmark
            tooltip_x = int(hovered_screen_pos[0]) + 15
            tooltip_y = int(hovered_screen_pos[1]) - tooltip_height - 5

            # Keep tooltip on screen
            if tooltip_x + tooltip_width > surface.get_width():
                tooltip_x = int(hovered_screen_pos[0]) - tooltip_width - 15
            if tooltip_y < 0:
                tooltip_y = int(hovered_screen_pos[1]) + 15

            # Draw tooltip background
            tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)
            pygame.draw.rect(surface, (20, 20, 20), tooltip_rect)
            pygame.draw.rect(surface, COLOR_LANDMARK, tooltip_rect, 1)

            # Draw tooltip text
            surface.blit(name_text, (tooltip_x + 5, tooltip_y + 3))
            surface.blit(coord_text, (tooltip_x + 5, tooltip_y + 3 + name_text.get_height()))

    def render_wind_indicator(self, surface, wind_direction):
        """
        Render wind indicator compass in top-right corner.

        Args:
            surface: Pygame surface
            wind_direction: Wind direction in degrees (FROM)
        """
        # Position in top-right
        center_x = self.width - WIND_INDICATOR_X_OFFSET
        center_y = WIND_INDICATOR_Y_OFFSET
        radius = WIND_INDICATOR_RADIUS

        # Draw compass circle
        pygame.draw.circle(surface, COLOR_WHITE, (center_x, center_y), radius, 2)

        # Draw cardinal directions
        font = pygame.font.SysFont('monospace', 14, bold=True)

        # N
        n_text = font.render('N', True, COLOR_WHITE)
        surface.blit(n_text, (center_x - 7, center_y - radius - 20))

        # E
        e_text = font.render('E', True, COLOR_WHITE)
        surface.blit(e_text, (center_x + radius + 5, center_y - 7))

        # S
        s_text = font.render('S', True, COLOR_WHITE)
        surface.blit(s_text, (center_x - 6, center_y + radius + 5))

        # W
        w_text = font.render('W', True, COLOR_WHITE)
        surface.blit(w_text, (center_x - radius - 18, center_y - 7))

        # Draw wind arrow showing direction wind is blowing TO (flip from FROM)
        wind_to_dir = (wind_direction + 180) % 360
        angle_rad = math.radians(90 - wind_to_dir)

        # Arrow shaft
        shaft_length = radius * 0.7
        end_x = center_x + shaft_length * math.cos(angle_rad)
        end_y = center_y - shaft_length * math.sin(angle_rad)

        pygame.draw.line(surface, COLOR_WIND_LIGHT, (center_x, center_y), (end_x, end_y), 3)

        # Arrowhead
        head_size = 8
        left_x = end_x - head_size * math.cos(angle_rad - 0.5)
        left_y = end_y + head_size * math.sin(angle_rad - 0.5)
        right_x = end_x - head_size * math.cos(angle_rad + 0.5)
        right_y = end_y + head_size * math.sin(angle_rad + 0.5)

        pygame.draw.polygon(surface, COLOR_WIND_LIGHT, [(end_x, end_y), (left_x, left_y), (right_x, right_y)])

    def zoom_in(self):
        """Increase zoom level."""
        self.zoom = min(self.zoom * MAP_ZOOM_STEP, MAP_ZOOM_MAX)

    def zoom_out(self):
        """Decrease zoom level."""
        self.zoom = max(self.zoom / MAP_ZOOM_STEP, MAP_ZOOM_MIN)

    def center_on_boat(self, boat):
        """
        Center map on boat position.

        Args:
            boat: Boat instance
        """
        self.center_lat = boat.lat
        self.center_lon = boat.lon

    def pan(self, dx_pixels, dy_pixels):
        """
        Pan camera by pixel offset.

        Args:
            dx_pixels: X offset in pixels (drag delta)
            dy_pixels: Y offset in pixels (drag delta)
        """
        # Convert pixels to degrees
        # Negate to move map opposite to drag (natural panning behavior)
        dx_deg = -dx_pixels / (self.base_scale * self.zoom)
        dy_deg = dy_pixels / (self.base_scale * self.zoom)  # Already flipped due to Y axis

        self.center_lon += dx_deg
        self.center_lat += dy_deg

    def get_viewport_dimensions_m(self):
        """
        Get current viewport dimensions in meters based on zoom level.

        Returns:
            (width_m, height_m) tuple
        """
        # Convert screen dimensions to degrees at current zoom
        width_deg = self.width / (self.base_scale * self.zoom)
        height_deg = self.height / (self.base_scale * self.zoom)

        # Convert to meters
        # Use center latitude for longitude conversion
        width_m = width_deg * 111000 * math.cos(math.radians(self.center_lat))
        height_m = height_deg * 111000

        return (width_m, height_m)
