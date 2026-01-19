"""
SF Bay Sailing Simulator - Main Entry Point
Integrates all components and runs the main game loop.
"""

import pygame
import sys
from datetime import datetime, timedelta, timezone

# Import configuration
from config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    MAP_WIDTH,
    MAP_HEIGHT,
    INSTRUMENT_WIDTH,
    FPS,
    TIME_STEP,
    BREADCRUMB_INTERVAL,
    MAX_BREADCRUMBS,
    POLAR_PATH,
    SHOW_FPS,
    COLOR_WHITE
)

# Import core components
from core.boat import Boat
from core.polar import PolarTable

# Import data providers
from data.geography import GeographyProvider
from data.weather import WeatherProvider
from data.currents import CurrentProvider
from data.grid_weather import GridWeatherProvider, GridCurrentProvider

# Import UI components
from ui.map_view import MapView
from ui.instruments import InstrumentPanel, ControlsHelpOverlay
from ui.controls import ControlHandler
from ui.overlays import VectorFieldOverlay
from ui.dialogs import StartupDialog


def main():
    """Main simulator entry point."""
    print("=" * 60)
    print("SF Bay Sailing Simulator")
    print("=" * 60)

    # Initialize Pygame
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("SF Bay Sailing Simulator")
    clock = pygame.time.Clock()

    # Load geography first (needed for custom location selection)
    print("Loading geography for startup dialog...")
    geography = GeographyProvider()

    # Show startup dialog
    print("\nShowing startup dialog...")
    dialog = StartupDialog(screen, geography)
    config = dialog.show()

    if config is None:
        print("User cancelled startup")
        pygame.quit()
        return

    print(f"\nStarting simulation:")
    print(f"  Location: {config['location_name']}")
    print(f"  Position: ({config['lat']:.4f}, {config['lon']:.4f})")
    print(f"  Heading: {config['heading']}°")
    print(f"  Forecast time: +{config['forecast_hours']} hours")
    print(f"  Scenario: {config['scenario'] or 'Real data'}")
    print(f"  Polar: {config['polar_path']}")

    # Load polar table
    print("Loading polar table...")
    polar = PolarTable(config['polar_path'])

    # Create boat list (start with one boat)
    print("Creating boat...")
    print(f"  Target speed factor: {config['target_speed_factor']*100:.0f}%")
    boat = Boat(polar, config['lat'], config['lon'], config['heading'], config['target_speed_factor'], "Boat 1", (255, 0, 0))
    boats = [boat]  # List of all boats

    # Initialize simulation time
    sim_time = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=config['forecast_hours'])

    print(f"Simulation time: {sim_time.strftime('%Y-%m-%d %H:%M:%S')} UTC (+{config['forecast_hours']}h)")

    # Create data providers
    print("\nInitializing data providers...")
    weather = WeatherProvider(sim_time, source='hrrr', scenario=config['scenario'])
    currents = CurrentProvider(sim_time)

    # Create grid providers for overlays
    weather_grid = GridWeatherProvider(weather, geography)
    current_grid = GridCurrentProvider(currents, geography)

    # Create UI components
    print("Initializing UI...")
    map_view = MapView(geography, MAP_WIDTH, MAP_HEIGHT)
    instruments = InstrumentPanel(MAP_WIDTH, 0, INSTRUMENT_WIDTH, SCREEN_HEIGHT)
    controls = ControlHandler(boats, map_view, polar)  # Pass boats list and polar
    overlays = VectorFieldOverlay(map_view)
    help_overlay = ControlsHelpOverlay()

    # Simulation state
    accumulator = 0.0
    breadcrumb_timer = 0.0

    # Environmental data (updated each physics step)
    wind_data = (315, 10)  # Default NW 10 kts
    current_data = (0.0, 0.0)  # Default zero current

    print("\n" + "=" * 60)
    print("Simulation ready! PAUSED - Press SPACE to start.")
    print("Press H for help, ESC to quit.")
    print("=" * 60 + "\n")

    # Main game loop
    running = True
    while running:
        # Tick at target FPS
        frame_time = clock.tick(FPS) / 1000.0  # Convert ms to seconds

        # ===== EVENT HANDLING =====
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Check for button clicks first (instrument panel takes priority)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if instruments.handle_button_click(event.pos, controls):
                    continue  # Button was clicked, skip other event handling

            result = controls.handle_event(event)
            if result == 'quit':
                running = False

        # Update button hover states
        instruments.update_button_hover(pygame.mouse.get_pos())

        # ===== PHYSICS UPDATES (Fixed Time Step) =====
        if not controls.paused:
            sim_speed = controls.get_sim_speed()
            accumulator += frame_time * sim_speed

            # Process all accumulated time in fixed time steps
            while accumulator >= TIME_STEP:
                # Update all boats
                for boat in boats:
                    # Get environmental data at boat position
                    wind_data = weather.get_wind(sim_time, boat.lat, boat.lon)
                    if wind_data:
                        wind_dir, wind_speed = wind_data
                    else:
                        # Fallback
                        wind_dir, wind_speed = 315, 10

                    current_data = currents.get_current(sim_time, boat.lat, boat.lon)
                    current_u, current_v = current_data

                    # AI routing decision (if enabled)
                    if boat.is_ai_controlled and boat.ai_router:
                        from ai.base_router import RoutingContext
                        from core.physics import angle_difference

                        context = RoutingContext(
                            boat=boat,
                            sim_time=sim_time,
                            waypoints=controls.waypoints,
                            weather=weather,
                            currents=currents,
                            geography=geography,
                            polar=polar
                        )

                        # Check for maneuvers first (instant state changes)
                        if boat.ai_router.should_tack(context):
                            boat.tack()
                        elif boat.ai_router.should_gybe(context):
                            boat.gybe()
                        else:
                            # Compute heading and apply with turn rate limit
                            target_heading = boat.ai_router.compute_heading(context)
                            delta = angle_difference(boat.heading, target_heading)

                            # Limit turn rate (realistic sailing - 10°/sec max)
                            delta = max(-10.0, min(10.0, delta))

                            # Only adjust if significant change
                            if abs(delta) > 1.0:
                                boat.adjust_heading(delta)

                    # Save position before update (for collision recovery)
                    old_lat = boat.lat
                    old_lon = boat.lon

                    # Update boat physics
                    boat.update(TIME_STEP, wind_dir, wind_speed, current_u, current_v)

                    # Check collision - if on land, restore old position and stop
                    if geography.check_collision(boat.lat, boat.lon):
                        print(f"⚠ {boat.name} collision with land! Boat stopped.")
                        # Restore previous position
                        boat.lat = old_lat
                        boat.lon = old_lon
                        # Stop the boat
                        boat.boat_speed = 0
                        boat.sog = 0

                    # Check mark rounding (course racing)
                    boat.check_mark_rounding(controls.waypoints)

                # Record breadcrumb for active boat only
                breadcrumb_timer += TIME_STEP
                if breadcrumb_timer >= BREADCRUMB_INTERVAL and controls.active_boat:
                    controls.active_boat.add_breadcrumb()
                    breadcrumb_timer = 0.0

                    # Limit breadcrumb trail length
                    if len(controls.active_boat.breadcrumbs) > MAX_BREADCRUMBS:
                        controls.active_boat.breadcrumbs.pop(0)

                # Advance simulation time
                sim_time += timedelta(seconds=TIME_STEP)
                accumulator -= TIME_STEP

                # Update forecast windows
                weather.update(sim_time)
                currents.update(sim_time)

        # ===== RENDERING (60 FPS) =====

        # Create map surface
        map_surface = pygame.Surface((MAP_WIDTH, MAP_HEIGHT))
        map_surface.fill((20, 40, 60))  # Water color

        # Render coastline
        map_view.render_coastline(map_surface)

        # Render breadcrumb trail for active boat only
        if controls.active_boat:
            map_view.render_breadcrumbs(map_surface, controls.active_boat)

        # Render shared waypoints (visible to all boats)
        map_view.render_waypoints(map_surface, controls.waypoints, boats, controls.show_mark_lines)

        # Determine display time (current sim time or preview time)
        if controls.forecast_preview_mode and controls.paused:
            display_time = sim_time + timedelta(minutes=controls.preview_time_offset_minutes)
        else:
            display_time = sim_time

        # Get current viewport dimensions based on zoom level
        viewport_width_m, viewport_height_m = map_view.get_viewport_dimensions_m()

        # Render wind overlay if enabled (use display_time for preview)
        if controls.show_wind_overlay:
            wind_grid_data = weather_grid.get_grid_data(
                display_time,
                map_view.center_lat,
                map_view.center_lon,
                viewport_width_m,
                viewport_height_m
            )
            overlays.render_wind_field(map_surface, wind_grid_data, pygame.mouse.get_pos())

        # Render current overlay if enabled (use display_time for preview)
        if controls.show_current_overlay:
            current_grid_data = current_grid.get_grid_data(
                display_time,
                map_view.center_lat,
                map_view.center_lon,
                viewport_width_m,
                viewport_height_m
            )
            overlays.render_current_field(map_surface, current_grid_data, pygame.mouse.get_pos())

        # Render course lines if enabled (only for active boat)
        if controls.show_course_lines and controls.active_boat:
            map_view.render_course_lines(map_surface, controls.active_boat)

        # Render all boats
        for idx, boat in enumerate(boats):
            is_active = (idx == controls.active_boat_index)
            map_view.render_boat(map_surface, boat, is_active)

        # Render wind indicator (use preview time if in forecast mode)
        if controls.forecast_preview_mode and controls.paused:
            preview_wind = weather.get_wind(display_time, map_view.center_lat, map_view.center_lon)
            if preview_wind:
                map_view.render_wind_indicator(map_surface, preview_wind[0])
        elif wind_data:
            map_view.render_wind_indicator(map_surface, wind_data[0])

        # Blit map to screen
        screen.blit(map_surface, (0, 0))

        # Render instrument panel (for active boat)
        if controls.active_boat:
            load_progress = {
                'weather': weather.get_load_progress(),
                'current': currents.get_load_progress()
            }

            instruments.render(
                screen,
                controls.active_boat,
                sim_time,
                controls.get_sim_speed(),
                load_progress,
                controls.waypoints,  # Pass shared waypoints
                controls.paused,  # Pass paused status
                controls  # Pass controls for button states
            )

        # Render help overlay if enabled
        if controls.show_help:
            help_overlay.render(screen)

        # Render FPS counter
        if SHOW_FPS:
            fps_font = pygame.font.SysFont('monospace', 14)
            fps_text = fps_font.render(f"FPS: {int(clock.get_fps())}", True, COLOR_WHITE)
            screen.blit(fps_text, (10, 10))

        # Flip display
        pygame.display.flip()

    # ===== CLEANUP =====
    print("\nShutting down...")
    weather.stop()
    currents.stop()
    pygame.quit()
    print("Simulator closed")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        pygame.quit()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        pygame.quit()
        sys.exit(1)
