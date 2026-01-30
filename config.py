"""
SF Bay Sailing Simulator - Configuration
All constants and settings for the simulator.
"""

# ==================== Screen Dimensions ====================
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 1000
MAP_WIDTH = 1200
MAP_HEIGHT = 1000
INSTRUMENT_WIDTH = 400
FPS = 60

# ==================== Physics Constants ====================
TIME_STEP = 1.0  # seconds - fixed physics time step
IN_IRONS_ANGLE = 30  # degrees - boat stalls if TWA < this
COLLISION_BUFFER = 0.0001  # degrees (~10 meters)
KNOTS_TO_MS = 0.514444  # knots to meters per second conversion
MS_TO_KNOTS = 1.0 / KNOTS_TO_MS
METERS_PER_DEGREE_LAT = 111000  # meters per degree latitude

# ==================== Colors (RGB tuples) ====================
# Water and environment
COLOR_WATER = (20, 40, 60)  # Dark blue
COLOR_LAND = (180, 180, 180)  # Light gray
COLOR_SKY = (135, 206, 235)  # Sky blue

# UI elements
COLOR_BOAT = (255, 0, 0)  # Red
COLOR_TRACK = (100, 150, 255)  # Light blue
COLOR_WAYPOINT = (255, 255, 0)  # Yellow
COLOR_TEXT = (255, 255, 255)  # White
COLOR_LABEL = (180, 180, 180)  # Light gray
COLOR_BORDER = (200, 200, 200)  # Border gray

# Panel colors
COLOR_PANEL_BG = (40, 40, 40)  # Dark gray background
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (255, 0, 0)

# Wind/current overlay colors
COLOR_WIND_LIGHT = (100, 255, 100)  # Light green
COLOR_WIND_MODERATE = (200, 255, 0)  # Yellow-green
COLOR_WIND_STRONG = (255, 200, 0)  # Orange
COLOR_WIND_VERY_STRONG = (255, 100, 0)  # Dark orange

COLOR_CURRENT_WEAK = (0, 255, 255)  # Cyan
COLOR_CURRENT_LIGHT = (0, 150, 255)  # Blue
COLOR_CURRENT_MODERATE = (255, 150, 0)  # Orange
COLOR_CURRENT_STRONG = (255, 0, 0)  # Red

# ==================== File Paths ====================
GEOJSON_PATH = 'sf_bay.geojson'
CACHE_DIR = '.cache'
POLAR_PATH = 'assets/polars/default_keelboat.json'
REPLAY_DIR = 'replays'

# ==================== NOAA Data Endpoints ====================
# HRRR (High-Resolution Rapid Refresh) weather data
HRRR_S3_BASE_URL = 'https://noaa-hrrr-bdp-pds.s3.amazonaws.com'
HRRR_URL_TEMPLATE = '{base}/hrrr.{date}/conus/hrrr.t{cycle:02d}z.wrfsfcf{hour:02d}.grib2'

# SFBOFS (San Francisco Bay Operational Forecast System) currents
SFBOFS_OPENDAP_BASE_URL = 'https://opendap.co-ops.nos.noaa.gov/thredds/dodsC/NOAA/SFBOFS/MODELS'
SFBOFS_URL_TEMPLATE = '{base}/{year}/{month:02d}/{day:02d}/sfbofs.t{cycle:02d}z.{date}.fields.f{hour:03d}.nc'

# ==================== Starting Locations ====================
LOCATIONS = {
    'Golden Gate': (37.8199, -122.4783),
    'Bay Bridge': (37.7920, -122.3700),
    'Alcatraz': (37.8200, -122.4100),
    'Angel Island': (37.8604, -122.4320),
    'Berkeley Marina': (37.8660, -122.3135),
    'Treasure Island': (37.8256, -122.3716),
    'Sausalito': (37.8590, -122.4852),
    'Alameda': (37.7650, -122.2416),
    'South Bay': (37.4900, -122.1200),
    'Richmond': (37.9200, -122.3534),
    'Oyster Point': (37.6620, -122.3780),
    'YRA-X': (37.811667, -122.443333),
}

# ==================== Weather Scenarios ====================
SCENARIOS = {
    'None': {
        'description': 'Use real NOAA data',
        'override_wind': False,
    },
    'Light Wind': {
        'description': '5 knots from West',
        'override_wind': True,
        'wind_speed': 5,
        'wind_direction': 270,
        'type': 'constant',
    },
    'Moderate Wind': {
        'description': '12 knots from Northwest',
        'override_wind': True,
        'wind_speed': 12,
        'wind_direction': 315,
        'type': 'constant',
    },
    'Heavy Wind': {
        'description': '25 knots from Northwest',
        'override_wind': True,
        'wind_speed': 25,
        'wind_direction': 315,
        'type': 'constant',
    },
    'Variable Wind': {
        'description': '15 knots from NW, oscillating ±20° every 5 min',
        'override_wind': True,
        'wind_speed': 15,
        'wind_direction': 315,
        'delta_degrees': 20,
        'period_seconds': 300,
        'type': 'variable',
    },
    'Spatial Wind': {
        'description': 'Wind varies by location (lighter near land)',
        'override_wind': True,
        'type': 'spatial',
    },
}

# ==================== Keyboard Controls ====================
CONTROLS = {
    'heading': {
        'left': 'LEFT',  # Adjust heading -10°
        'right': 'RIGHT',  # Adjust heading +10°
        'fine_left': 'a',  # Adjust heading -2°
        'fine_right': 'd',  # Adjust heading +2°
    },
    'maneuvers': {
        'tack': 't',  # Tack through wind
        'gybe': 'g',  # Gybe downwind
    },
    'simulation': {
        'pause': 'SPACE',  # Pause/resume
        'speed_up': '=',  # Increase sim speed
        'slow_down': '-',  # Decrease sim speed
    },
    'view': {
        'center_boat': 'c',  # Center map on boat
        'zoom_in': ']',  # Zoom in
        'zoom_out': '[',  # Zoom out
        'toggle_wind': 'w',  # Toggle wind overlay
        'toggle_current': 'u',  # Toggle current overlay
        'toggle_ladder_rungs': 'y',  # Toggle ladder rungs
        'help': 'h',  # Show help overlay
    },
    'wind_modifiers': {
        'speed_down': 'z',  # Decrease wind speed by 5%
        'speed_up': 'x',  # Increase wind speed by 5%
        'angle_ccw': 'q',  # Rotate wind CCW by 2°
        'angle_cw': 'e',  # Rotate wind CW by 2°
        'reset': 'W',  # Reset wind modifiers (Shift+W)
    },
    'marks': {
        'drop_mark': 'm',  # Drop waypoint at boat position
        'clear_marks': 'M',  # Clear all waypoints (Shift+M)
        'click_mark': 'MOUSE_LEFT',  # Drop waypoint at mouse position
    },
    'quit': {
        'quit': 'ESCAPE',  # Quit simulation
    },
}

# ==================== Simulation Speed Multipliers ====================
SPEED_MULTIPLIERS = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 25.0, 50.0, 100.0]
DEFAULT_SPEED_INDEX = 2  # Start at 1.0x

# ==================== Forecast Window Settings ====================
FORECAST_WINDOW_HOURS = 6  # Hours of forecast data to keep loaded
FORECAST_PRELOAD_MARGIN = 0.5  # Start loading next hour when <30 min away
FORECAST_LOAD_THROTTLE = 3.0  # Seconds between file downloads
FORECAST_PRIORITY_HOURS = 2  # Load hours 0-1 first (blocking)

# HRRR model run times (UTC)
# HRRR runs EVERY HOUR (00z, 01z, 02z, ..., 23z)
# Files available 1-2 hours after model run time

# SFBOFS model run times (UTC)
SFBOFS_MODEL_CYCLES = [3, 9, 15, 21]  # Hours (03z, 09z, 15z, 21z)

# ==================== Vector Overlay Settings ====================
VECTOR_GRID_SPACING_M = 1000  # Wind vector spacing in meters
CURRENT_GRID_SPACING_M = 500  # Current vector spacing in meters (denser)
VECTOR_SCALE_FACTOR = 5.0  # Pixels per knot for arrow length
VECTOR_ARROW_WIDTH = 3  # Pixels for arrow shaft
VECTOR_ARROWHEAD_SIZE = 10  # Pixels for arrowhead triangle
VECTOR_CACHE_INTERVAL = 1.0  # Refresh grid every N seconds (not every frame)

# Filtering thresholds
MIN_CURRENT_SPEED_KTS = 0.05  # Don't render currents weaker than this
MIN_WIND_SPEED_KTS = 1.0  # Don't render winds weaker than this

# ==================== Ladder Rungs Settings ====================
LADDER_RUNG_SPACING_M = 200           # Meters between rungs (~0.1nm)
LADDER_RUNG_COUNT = 5                 # Dotted rungs on each side
LADDER_RUNG_LENGTH_M = 10000          # Length of each rung in meters
LADDER_RUNG_MIN_WIND_SPEED = 2.0      # Min wind to render (kts)
LADDER_RUNG_COLOR = (255, 200, 100)   # Amber - good contrast
LADDER_RUNG_SOLID_WIDTH = 2           # Pixel width for solid rung
LADDER_RUNG_DASH_WIDTH = 1            # Pixel width for dotted rungs
LADDER_RUNG_DASH_LENGTH = 8           # Dash length in pixels
LADDER_RUNG_GAP_LENGTH = 6            # Gap length in pixels

# ==================== Laylines Settings ====================
LAYLINE_LENGTH_M = 5556               # 3 nautical miles
LAYLINE_MIN_WIND_SPEED = 2.0          # Min wind to render (kts)
LAYLINE_STARBOARD_COLOR = (0, 200, 0)     # Green
LAYLINE_PORT_COLOR = (200, 0, 0)          # Red
LAYLINE_WIDTH = 2                     # Pixel width

# ==================== Landmark Settings ====================
COLOR_LANDMARK = (128, 128, 128)      # Gray
LANDMARK_RADIUS = 3                   # Pixels

LANDMARKS = [
    {'name': 'RYC-BK', 'description': 'Bob Klein', 'lat': 37.886400, 'lon': -122.402600},
    {'name': 'YRA-16', 'description': 'Blackaller', 'lat': 37.810000, 'lon': -122.465000},
    {'name': 'Southampton Shoal', 'description': 'Southampton Shoal', 'lat': 37.881924, 'lon': -122.400219},
    {'name': 'YRA-Anita', 'description': 'Anita rock offset buoy', 'lat': 37.808333, 'lon': -122.453333},
    {'name': 'Point Blunt', 'description': 'Point Blunt offset buoy', 'lat': 37.8505, 'lon': -122.4175},
    {'name': 'Pier', 'description': 'Berkeley Marina channel light 2', 'lat': 37.8477, 'lon': -122.3606},
    {'name': '2CR', 'description': "R '2CR' Fl R 4s Castro Rocks Lighted Buoy 2CR", 'lat': 37.931664, 'lon': -122.420890},
    {'name': 'RHC#2', 'description': "R '2' Q R Richmond Harbor Channel Lighted Buoy 2", 'lat': 37.918193, 'lon': -122.417493},
    {'name': 'RHC#3', 'description': "R '3' Q R Richmond Harbor Channel Lighted Buoy 3", 'lat': 37.91513811087828, 'lon': -122.40970591705349},
    {'name': 'YBI CG #2', 'description': 'Regulated Area Buoy 2', 'lat': 37.8075, 'lon': -122.3597},
    {'name': 'YBI CG #1', 'description': 'Regulated Area Buoy 1', 'lat': 37.81167420413766, 'lon': -122.35967150446378},
    {'name': 'RYC Birdcage', 'description': 'End of jetty', 'lat': 37.903750616461366, 'lon': -122.39209756578727},
    {'name': 'Pt. Stuart', 'description': 'Buoy marking point stuart', 'lat': 37.86101238531544, 'lon': -122.44786594591845},
    {'name': 'Alcatraz', 'description': 'Alcatraz Lighted Bell Buoy, GR “AZ” FL(2+1) G 6s', 'lat':  37.8277, 'lon': -122.4282},
    {'name': 'YRA-12', 'description': 'Little Harding', 'lat': 37.843825, 'lon': -122.453357},
    {'name': 'YRA-17', 'description': 'Harding Rock', 'lat': 37.838239, 'lon': -122.445994},
    {'name': 'YRA-18', 'description': 'Blossom Rock', 'lat': 37.818376, 'lon': -122.403448}
]

# ==================== Breadcrumb Trail Settings ====================
BREADCRUMB_INTERVAL = 5.0  # seconds between breadcrumb points
MAX_BREADCRUMBS = 2000  # Maximum trail length

# ==================== History/Rewind Settings ====================
HISTORY_SNAPSHOT_INTERVAL = 60  # Seconds between snapshots
MAX_HISTORY_SNAPSHOTS = 1440    # 12 hours of history (720 * 60s = 43200s)

# ==================== UI Font Settings ====================
FONT_TITLE_SIZE = 16
FONT_LABEL_SIZE = 14
FONT_VALUE_SIZE = 18
FONT_SMALL_SIZE = 12
FONT_FAMILY = 'monospace'  # Use monospace for consistent alignment

# ==================== Boat Physics Tuning ====================
IN_IRONS_SPEED_KTS = 0.5  # Boat speed when in irons (nearly stopped)
TACK_ANGLE_OFFSET = 45  # Degrees off wind after tacking
GYBE_ANGLE_OFFSET = 135  # Degrees off wind after gybing

# ==================== Map View Settings ====================
MAP_ZOOM_MIN = 0.2
MAP_ZOOM_MAX = 50.0
MAP_ZOOM_STEP = 1.2  # Multiplier for zoom in/out
MAP_MARGIN_FACTOR = 0.9  # Scale to fit bay with 10% margin

# ==================== Instrument Panel Layout ====================
INSTRUMENT_PANEL_PADDING = 10  # Pixels between sections
INSTRUMENT_LINE_SPACING = 20  # Pixels between lines
INSTRUMENT_SECTION_SPACING = 30  # Pixels between sections
INSTRUMENT_VALUE_INDENT = 20  # Pixels to indent values

# ==================== Wind Indicator (Compass Rose) Settings ====================
WIND_INDICATOR_RADIUS = 40  # Pixels
WIND_INDICATOR_X_OFFSET = 60  # Pixels from right edge
WIND_INDICATOR_Y_OFFSET = 60  # Pixels from top edge

# ==================== Collision Detection ====================
COLLISION_CHECK_INTERVAL = 1.0  # Check every physics update (1 second)

# ==================== Data Caching ====================
CACHE_EXPIRY_DAYS = 7  # Delete cached files older than this
MAX_CACHE_SIZE_GB = 5  # Maximum cache directory size

# ==================== Threading ====================
BACKGROUND_THREAD_DAEMON = True  # Daemon threads exit when main exits
THREAD_JOIN_TIMEOUT = 1.0  # Seconds to wait for thread cleanup

# ==================== Performance Tuning ====================
VIEWPORT_CULL_MARGIN = 50  # Pixels - render objects slightly off-screen
COASTLINE_SIMPLIFY_TOLERANCE = 0.0  # Degrees - 0 = no simplification

# ==================== Debug Settings ====================
DEBUG_MODE = False  # Enable debug prints
SHOW_FPS = True  # Show FPS counter
SHOW_LOADING_PROGRESS = True  # Show data loading progress in UI

# ==================== Error Handling ====================
MAX_NOAA_RETRY_ATTEMPTS = 3  # Retry failed downloads this many times
NOAA_RETRY_DELAY = 5.0  # Seconds between retries
FALLBACK_WIND_DIRECTION = 315  # Northwest (degrees)
FALLBACK_WIND_SPEED = 10  # knots

# ==================== HRRR Grid Info (for reference) ====================
# HRRR grid size: 1059 x 1799 = 1,905,141 points
# Expected triangulation time: 20-30 seconds
# Grid coverage: Continental US
# Resolution: ~3km

# ==================== SFBOFS Grid Info (for reference) ====================
# SFBOFS element count: 102,264 elements
# Expected triangulation time: 5-10 seconds
# Grid coverage: San Francisco Bay only
# Element type: Triangular unstructured mesh
# Vertical layers: 20 sigma layers (0 = surface, 19 = bottom)

# ==================== Coordinate System Notes ====================
# Latitude: -90 to +90 (positive = North)
# Longitude: -180 to +180 (positive = East) OR 0 to 360
# SFBOFS uses 0-360° longitude convention!
# Wind direction: FROM (meteorological convention)
# Current set: TO (oceanographic convention)
# Screen coordinates: Origin top-left, Y increases downward

# ==================== Time Settings ====================
TIME_MODE_CURRENT = 'current'
TIME_MODE_FUTURE = 'future'
FUTURE_TIME_OFFSET_HOURS = 6  # When in future mode, start 6 hours ahead

# ==================== Startup Dialog Settings ====================
DIALOG_WIDTH = 800
DIALOG_HEIGHT = 600
DIALOG_TITLE_SIZE = 48
DIALOG_OPTION_SIZE = 20
DIALOG_DESCRIPTION_SIZE = 14

# ==================== AI Routing Settings ====================

# Decision parameters
AI_MAX_TURN_RATE = 10.0  # degrees per second (realistic turning)
AI_DECISION_INTERVAL = 1.0  # seconds (run every physics tick)

# Greedy VMG parameters
AI_VMG_HEADING_SAMPLES = 25  # Number of headings to sample
AI_VMG_TACK_THRESHOLD = 0.1  # knots VMG improvement to trigger tack
AI_VMG_TACK_TIME_COST = 10.0  # seconds of time lost during tack maneuver
AI_VMG_DECISION_HORIZON = 60.0  # seconds ahead to consider for tack decisions
AI_VMG_MANEUVER_COOLDOWN = 10.0  # seconds between tacks/gybes (prevents rapid tacking)
AI_VMG_COLLISION_CHECK_DISTANCE = 0.5  # nautical miles ahead to check collisions
AI_VMG_CHECK_COLLISIONS = True  # Whether to check for land collisions

# A* pathfinding parameters (for future implementation)
AI_ASTAR_GRID_SIZE_M = 100  # Grid cell size in meters
AI_ASTAR_REPLAN_INTERVAL = 10.0  # seconds between replanning
AI_ASTAR_MAX_NODES = 10000  # Maximum search nodes to prevent infinite loops

# Isochrone parameters (for future implementation)
AI_ISOCHRONE_TIME_STEPS = 12  # Number of isochrone rings
AI_ISOCHRONE_STEP_DURATION = 300  # seconds per ring
AI_ISOCHRONE_ANGULAR_RESOLUTION = 30  # degrees between heading samples

# Performance budgets
AI_MAX_COMPUTATION_MS = 50  # milliseconds per decision (timeout threshold)
