# SF Bay Sailing Simulator

An interactive, physics-based sailing simulator for San Francisco Bay featuring real-time NOAA weather data, tidal currents, and comprehensive environmental visualization.

## Features

- **Realistic Physics**: Polar table-based boat performance with true and apparent wind calculations
- **Real-Time Weather**: NOAA HRRR high-resolution weather data (3km grid, updated hourly)
- **Tidal Currents**: NOAA SFBOFS tidal current forecasts for San Francisco Bay
- **Interactive UI**: 60 FPS rendering with zoom, pan, and overlay controls
- **Vector Overlays**: Visualize wind and current fields with color-coded arrows
- **Multiple Scenarios**: Test with constant, variable, or spatial wind patterns
- **11 Starting Locations**: Start from Golden Gate, Bay Bridge, Alcatraz, and more

## Installation

### System Dependencies

**macOS:**
```bash
brew install eccodes
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install libeccodes-dev
```

### Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

## Usage

### Starting the Simulator

```bash
source venv/bin/activate
python main.py
```

### Startup Dialog

Use arrow keys and keyboard to configure:
- **Location**: UP/DOWN to select starting location
  - Choose from 11 named locations OR
  - Select "Custom..." to choose any location by:
    - Clicking on the map preview, OR
    - Typing lat/lon coordinates in the input fields
- **Heading**: LEFT/RIGHT to adjust initial heading
- **Forecast Time**:
  - T to cycle through common intervals (0, 6, 12, 18, 24, 36, 48 hours)
  - , (comma) to decrease by 1 hour
  - . (period) to increase by 1 hour
- **Scenario**: S to cycle through weather scenarios
- **Polar Table**: P to cycle through available boat polars
- **Target Speed**: +/- to adjust performance factor (accounts for sea state, crew skill, etc.)
- **Start**: ENTER to begin simulation

### Keyboard Controls

**Note:** The simulation starts **PAUSED**. Press `SPACE` to begin.

**Multi-Boat:**
- `TAB`: Switch between boats
- `N`: Add new boat near active boat
- `DELETE`: Remove active boat (if more than one)
- `Click on boat`: Select that boat as active

**AI Control:**
- `I`: Toggle AI control for active boat (enables/disables autopilot)
- `O`: Cycle through AI routing algorithms
- AI boats navigate course autonomously using weather/current data
- **Layline VMG Router**: Uses proper sailing geometry with laylines
  - Outside laylines: points directly at mark
  - Inside laylines: beats upwind using optimal polar angles
  - 30-second minimum tack commitment to prevent oscillation

**Course Racing:**
- `M`: Drop mark at boat position (creates sequential course)
- `R`: Reset all boats to start of course
- `K`: Toggle mark target lines (dashed lines from boats to their marks)
- Boats automatically advance to next mark when rounded (~40m)
- Stats panel shows current target mark and progress (e.g., "2/5 marks")

**Heading:**
- `LEFT/RIGHT` arrows: Adjust heading ±5°
- `A/D`: Fine adjust ±1°

**Maneuvers:**
- `T`: Tack through wind
- `G`: Gybe downwind

**Simulation:**
- `SPACE`: Pause/resume (starts paused)
- `+/-`: Speed up/slow down (0x to 100x)

**Forecast Preview (while paused):**
- `F`: Toggle forecast preview mode
- `,` (comma): Scrub time backward 10 minutes
- `.` (period): Scrub time forward 10 minutes
- Shows how wind/current will evolve (-1 hour to +6 hours)
- Exit preview mode (F) to return to current time

**Boat Performance:**
- `Shift+UP`: Increase target speed factor by 5%
- `Shift+DOWN`: Decrease target speed factor by 5%

**View:**
- `C`: Center map on boat
- `[/]`: Zoom out/in
- `Mouse wheel`: Zoom in/out
- `Left click + drag`: Pan map
- `L`: Toggle course lines (heading and COG)
- `K`: Toggle mark target lines (dashed lines to marks)
- `W`: Toggle wind overlay
- `U`: Toggle current overlay
- `H`: Toggle help overlay

**Waypoints:**
- `M`: Drop mark at boat position
- `Shift+M`: Clear all marks
- `Right click`: Drop mark at mouse position
- `Ctrl/Cmd + Left click`: Drop mark at mouse position

**Quit:**
- `ESC`: Exit simulator

## How It Works

### Physics Model

The simulator uses a fixed 1-second time step with:
- **True Wind Angle** calculation from boat heading and wind direction
- **Polar table lookup** for boat speed through water
- **Apparent wind** calculation from true wind and boat motion
- **Velocity over ground** combining boat velocity and tidal current
- **In irons detection** when pointing too close to wind (<30°)

### Data Sources

**Weather (HRRR):**
- High-Resolution Rapid Refresh model from NOAA
- 3km resolution, model runs **every hour** (00z-23z)
- Forecasts available 0-48 hours out
- Downloads GRIB2 files from AWS S3
- Uses bilinear interpolation on regular grid (fast!)
- Progressive loading in background thread
- Automatically finds most recent available hourly run
- No API fallback - uses GRIB data only (or scenarios)

**Currents (SFBOFS):**
- San Francisco Bay Operational Forecast System
- Unstructured triangular mesh (102K elements)
- Loaded via OpenDAP (no download required)
- Surface layer currents from 20-layer vertical model
- Shared triangulation across forecast hours (performance optimization)

### Performance

- **Startup**: Dialog appears instantly, first frame within 1 second
- **Data Loading**: Hours 0-1 load in ~40-60 seconds (background), full window in ~3 minutes
- **Frame Rate**: Solid 60 FPS with all overlays enabled
- **Memory**: ~500MB with full 6-hour forecast window loaded

## Scenarios

Test different wind conditions without waiting for real data:

- **None**: Use real NOAA data (default)
- **Light Wind**: 5 knots from West - gentle sailing
- **Moderate Wind**: 12 knots from Northwest - typical bay conditions
- **Heavy Wind**: 25 knots from Northwest - challenging conditions
- **Variable Wind**: 15 knots oscillating ±20° every 5 minutes - practice tacking
- **Spatial Wind**: Wind varies by location (lighter near land)

## Project Structure

```
sfbaysim2/
├── main.py                 # Entry point and game loop
├── config.py               # All configuration constants
├── requirements.txt        # Python dependencies
├── sf_bay.geojson          # San Francisco Bay coastline data
├── core/                   # Simulation engine
│   ├── physics.py          # Vector math and nautical calculations
│   ├── polar.py            # Polar table interpolation
│   └── boat.py             # Boat state management
├── data/                   # Data providers
│   ├── geography.py        # GeoJSON coastline loading
│   ├── hrrr_grid.py        # HRRR weather data
│   ├── sfbofs_hour.py      # SFBOFS current data
│   ├── forecast_window.py  # Weather sliding window manager
│   ├── current_window.py   # Current sliding window manager
│   ├── weather.py          # Weather provider interface
│   ├── currents.py         # Current provider interface
│   └── grid_weather.py     # Grid sampling for overlays
├── ui/                     # User interface
│   ├── map_view.py         # Map projection and rendering
│   ├── instruments.py      # Dashboard panels
│   ├── controls.py         # Input handling
│   ├── overlays.py         # Vector field visualization
│   └── dialogs.py          # Startup dialog
├── ai/                     # AI routing algorithms
│   ├── base_router.py      # Router interface and base class
│   ├── router_factory.py   # Router instantiation
│   ├── state.py            # AI state management
│   ├── utils.py            # Navigation utilities
│   └── simple/
│       └── greedy_vmg.py   # Layline-based VMG router
├── scenarios/              # Weather scenarios
│   └── weather_overrides.py
├── replays/                # Saved session replays
└── assets/
    └── polars/             # Boat polar performance tables
        ├── default_keelboat.json
        └── express_27.json
```

## Troubleshooting

**"cfgrib import error":**
- Ensure eccodes is installed: `brew install eccodes` (macOS) or `apt-get install libeccodes-dev` (Linux)
- Try conda installation: `conda install -c conda-forge cfgrib`

**"HRRR data not available":**
- Simulator will use default constant wind (NW 10 kts)
- Try using a scenario (select in startup dialog)
- Check internet connection
- Verify AWS S3 access to HRRR data

**"SFBOFS data not available":**
- Simulator will use zero current and continue normally
- Current data may lag real-time by 1-2 hours

**Low FPS with overlays:**
- Disable overlays (W/U keys)
- Reduce simulation speed
- Increase grid spacing in config.py

## License

This is a technical demonstration project. Real-world sailing should reference official NOAA data sources and professional navigation tools.

## Credits

- Weather data: NOAA HRRR via AWS
- Current data: NOAA SFBOFS via OpenDAP
- Coastline: GeoJSON data for San Francisco Bay
