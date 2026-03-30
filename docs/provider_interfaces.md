# Provider Interfaces

This document describes the abstract provider interfaces for weather and cloud data,
and how to add a new provider implementation.

---

## WeatherProvider (Abstract)

```python
class WeatherProvider(ABC):
    @abstractmethod
    async def get_forecast(
        self,
        lat: float,
        lon: float,
        days: int = 1,
    ) -> WeatherForecast:
        ...

    @abstractmethod
    async def get_surface_summary(
        self,
        lat: float,
        lon: float,
    ) -> SurfaceSummary:
        ...
```

### WeatherForecast

```python
@dataclass
class WeatherForecast:
    provider: str
    site_id: str
    location: dict         # {"lat": float, "lon": float}
    hourly: list[WeatherHour]
    fetched_at: datetime
```

### Registered Providers

| `WEATHER_PROVIDER` env value | Class | Notes |
|------------------------------|-------|-------|
| `open_meteo` | `OpenMeteoProvider` | Real API, requires internet |
| `mock` | `MockWeatherProvider` | Synthetic Gaussian diurnal cycle |

### Adding a New Weather Provider

1. Subclass `WeatherProvider` in `backend/data_ingestion/weather/`.
2. Implement `get_forecast()` and `get_surface_summary()`.
3. Register in `backend/data_ingestion/weather/provider_base.py`:
   ```python
   PROVIDER_REGISTRY["my_provider"] = MyProvider
   ```
4. Set `WEATHER_PROVIDER=my_provider` in `.env`.

### MockWeatherProvider Behaviour

Synthetic diurnal cycle centred on Eagle Ridge defaults (35.49°N, 118.19°W):
- Temperature: peaks 28°C at 14:00, minimum 12°C at 06:00
- Wind speed: peaks 22 km/h at 14:00, minimum 5 km/h at 07:00
- Wind direction: 210° (SW) throughout day with ±15° noise
- Cloud cover: builds from 10% at 09:00 to 55% by 15:00, then decreases
- Dewpoint: 6°C constant (giving spread 6–22°C across day)

---

## CloudProvider (Abstract)

```python
class CloudProvider(ABC):
    @abstractmethod
    async def get_observation(
        self,
        lat: float,
        lon: float,
    ) -> CloudObservation:
        ...
```

### CloudObservation

```python
@dataclass
class CloudObservation:
    site_id: str
    provider: str
    cover_pct: float          # 0–100
    cloud_base_m: float | None
    cloud_type_hint: str | None
    observed_at: datetime
    confidence: float
    interpretation: str        # human-readable summary
```

### Registered Cloud Providers

| `CLOUD_PROVIDER` env value | Class | Notes |
|----------------------------|-------|-------|
| `mock` | `MockCloudProvider` | Returns 35% cover, 2100m base, cumulus |

### Adding a New Cloud Provider

1. Subclass `CloudProvider` in `backend/data_ingestion/clouds/`.
2. Implement `get_observation()`.
3. Wire up in `backend/api/deps.py` alongside the weather provider.

---

## IGC / GPX Parsers

Both parsers produce a common output structure:

```python
@dataclass
class ParsedFlight:
    fixes: list[Fix]          # time-lat-lon-alt tuples
    segments: list[Segment]   # climb/glide/sink
    metadata: dict
```

### IGC Parser

- File: `backend/data_ingestion/flights/igc_parser.py`
- Handles IGC 2004 specification B-records
- Format: `BHHMMSSDDMMmmmNDDDMMmmmEVPPPPPGGGGG`
- Vario: 5-point centred moving average of altitude delta / time delta

### GPX Parser

- File: `backend/data_ingestion/flights/gpx_parser.py`
- Handles GPX 1.0 and 1.1 `<trkpt>` elements
- Elevation from `<ele>` element or `<gpxtpx:TrackPointExtension>`
- Reuses IGC segmentation thresholds (CLIMB_THRESHOLD=0.3, SINK_THRESHOLD=-0.8 m/s)

---

## Terrain / DEM

### DEMLoader

- File: `backend/data_ingestion/terrain/dem_loader.py`
- `load(path)`: loads a GeoTIFF via rasterio; falls back to synthetic 50×50 DEM if missing
- `extract_slope_aspect()`: numpy gradient-based slope (degrees) and aspect (degrees true)

### TerrainAnalyzer

- File: `backend/data_ingestion/terrain/terrain_analyzer.py`
- `identify_ridges()`: regions with slope > 25° and elevation above site median
- `identify_thermal_slopes()`: slope 15–38°, aspect 120–270° (south-facing)
- `identify_lee_zones(wind_dir)`: downwind faces within 90° of wind direction
- `identify_rotor_zones(wind_dir)`: combined slope + lee detection for mechanical turbulence
