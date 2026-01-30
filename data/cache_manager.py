"""
Cache Manager for HRRR and SFBOFS Forecast Data

Singleton class that manages cached weather and current data files:
- Tracks files with metadata (type, date, cycle, forecast hour, size, timestamps)
- Enforces expiry (delete files older than N days)
- Enforces size limits (LRU eviction when over limit)
- Persists metadata to .cache/cache_metadata.json
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from config import CACHE_DIR, CACHE_EXPIRY_DAYS, MAX_CACHE_SIZE_GB


class CacheManager:
    """
    Singleton cache manager for forecast data files.

    Tracks HRRR (.grib2) and SFBOFS (.nc) files with metadata for
    intelligent cache management including expiry and size limits.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if CacheManager._initialized:
            return

        self.cache_dir = Path(CACHE_DIR)
        self.metadata_path = self.cache_dir / "cache_metadata.json"
        self.metadata: Dict[str, dict] = {}

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load existing metadata
        self._load_metadata()

        # Scan for any untracked files
        self._scan_for_untracked_files()

        CacheManager._initialized = True

    def _load_metadata(self):
        """Load metadata from disk if it exists."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                print(f"Loaded cache metadata: {len(self.metadata)} files tracked")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load cache metadata: {e}")
                self.metadata = {}
        else:
            self.metadata = {}

    def _save_metadata(self):
        """Persist metadata to disk."""
        try:
            with open(self.metadata_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save cache metadata: {e}")

    def _scan_for_untracked_files(self):
        """Scan cache directory for files not in metadata and add them."""
        if not self.cache_dir.exists():
            return

        added_count = 0
        for file_path in self.cache_dir.iterdir():
            if file_path.is_file() and file_path.name != "cache_metadata.json":
                filename = file_path.name
                if filename not in self.metadata:
                    # Parse filename to extract metadata
                    file_info = self._parse_filename(filename)
                    if file_info:
                        stat = file_path.stat()
                        self.metadata[filename] = {
                            **file_info,
                            'size_bytes': stat.st_size,
                            'created_time': stat.st_ctime,
                            'last_accessed': stat.st_atime
                        }
                        added_count += 1

        if added_count > 0:
            print(f"Added {added_count} untracked files to cache metadata")
            self._save_metadata()

    def _parse_filename(self, filename: str) -> Optional[dict]:
        """
        Parse cache filename to extract metadata.

        HRRR format: hrrr_{YYYYMMDD}_{HH}z_f{FF}.grib2
        SFBOFS format: sfbofs_{YYYYMMDD}_{HH}z_f{FFF}.nc
        """
        try:
            if filename.startswith('hrrr_') and filename.endswith('.grib2'):
                # hrrr_20250130_14z_f06.grib2
                parts = filename[5:-6].split('_')  # Remove 'hrrr_' and '.grib2'
                date_str = parts[0]
                cycle = int(parts[1].rstrip('z'))
                forecast_hour = int(parts[2].lstrip('f'))
                return {
                    'type': 'hrrr',
                    'date': date_str,
                    'cycle': cycle,
                    'forecast_hour': forecast_hour
                }

            elif filename.startswith('sfbofs_') and filename.endswith('.nc'):
                # sfbofs_20250130_14z_f006.nc
                parts = filename[7:-3].split('_')  # Remove 'sfbofs_' and '.nc'
                date_str = parts[0]
                cycle = int(parts[1].rstrip('z'))
                forecast_hour = int(parts[2].lstrip('f'))
                return {
                    'type': 'sfbofs',
                    'date': date_str,
                    'cycle': cycle,
                    'forecast_hour': forecast_hour
                }
        except (IndexError, ValueError):
            pass

        return None

    def get_cache_path(self, data_type: str, cycle_time: datetime, forecast_hour: int) -> Path:
        """
        Generate cache path for a data file.

        Args:
            data_type: 'hrrr' or 'sfbofs'
            cycle_time: Model cycle datetime
            forecast_hour: Forecast hour

        Returns:
            Path object for the cache file
        """
        date_str = cycle_time.strftime('%Y%m%d')
        cycle = cycle_time.hour

        if data_type == 'hrrr':
            filename = f"hrrr_{date_str}_{cycle:02d}z_f{forecast_hour:02d}.grib2"
        elif data_type == 'sfbofs':
            filename = f"sfbofs_{date_str}_{cycle:02d}z_f{forecast_hour:03d}.nc"
        else:
            raise ValueError(f"Unknown data type: {data_type}")

        return self.cache_dir / filename

    def is_cached(self, data_type: str, cycle_time: datetime, forecast_hour: int) -> bool:
        """
        Check if a data file is cached.

        Args:
            data_type: 'hrrr' or 'sfbofs'
            cycle_time: Model cycle datetime
            forecast_hour: Forecast hour

        Returns:
            True if file exists in cache
        """
        cache_path = self.get_cache_path(data_type, cycle_time, forecast_hour)
        return cache_path.exists()

    def register_file(self, data_type: str, cycle_time: datetime, forecast_hour: int,
                      file_path: Optional[Path] = None):
        """
        Register a newly cached file in metadata.

        Args:
            data_type: 'hrrr' or 'sfbofs'
            cycle_time: Model cycle datetime
            forecast_hour: Forecast hour
            file_path: Optional path (uses get_cache_path if not provided)
        """
        if file_path is None:
            file_path = self.get_cache_path(data_type, cycle_time, forecast_hour)

        if not file_path.exists():
            return

        filename = file_path.name
        stat = file_path.stat()

        self.metadata[filename] = {
            'type': data_type,
            'date': cycle_time.strftime('%Y%m%d'),
            'cycle': cycle_time.hour,
            'forecast_hour': forecast_hour,
            'size_bytes': stat.st_size,
            'created_time': stat.st_ctime,
            'last_accessed': time.time()
        }

        self._save_metadata()

    def update_access_time(self, filename: str):
        """Update last accessed time for a file (for LRU tracking)."""
        if filename in self.metadata:
            self.metadata[filename]['last_accessed'] = time.time()
            self._save_metadata()

    def enforce_expiry(self, days: Optional[int] = None) -> int:
        """
        Delete files older than specified days.

        Args:
            days: Number of days (uses CACHE_EXPIRY_DAYS if not specified)

        Returns:
            Number of files deleted
        """
        if days is None:
            days = CACHE_EXPIRY_DAYS

        cutoff_time = time.time() - (days * 24 * 60 * 60)
        deleted_count = 0
        files_to_remove = []

        for filename, info in self.metadata.items():
            created_time = info.get('created_time', 0)
            if created_time < cutoff_time:
                file_path = self.cache_dir / filename
                if file_path.exists():
                    try:
                        file_path.unlink()
                        print(f"Deleted expired cache file: {filename}")
                        deleted_count += 1
                    except OSError as e:
                        print(f"Warning: Could not delete {filename}: {e}")
                files_to_remove.append(filename)

        for filename in files_to_remove:
            del self.metadata[filename]

        if deleted_count > 0:
            self._save_metadata()
            print(f"Cleaned up {deleted_count} expired cache files")

        return deleted_count

    def enforce_size_limit(self, gb: Optional[float] = None) -> int:
        """
        Enforce cache size limit using LRU eviction.

        Args:
            gb: Size limit in GB (uses MAX_CACHE_SIZE_GB if not specified)

        Returns:
            Number of files deleted
        """
        if gb is None:
            gb = MAX_CACHE_SIZE_GB

        max_bytes = gb * 1024 * 1024 * 1024

        # Calculate current total size
        total_size = sum(info.get('size_bytes', 0) for info in self.metadata.values())

        if total_size <= max_bytes:
            return 0

        # Sort files by last accessed time (oldest first)
        sorted_files = sorted(
            self.metadata.items(),
            key=lambda x: x[1].get('last_accessed', 0)
        )

        deleted_count = 0
        files_to_remove = []

        for filename, info in sorted_files:
            if total_size <= max_bytes:
                break

            file_path = self.cache_dir / filename
            file_size = info.get('size_bytes', 0)

            if file_path.exists():
                try:
                    file_path.unlink()
                    print(f"LRU evicted cache file: {filename}")
                    total_size -= file_size
                    deleted_count += 1
                except OSError as e:
                    print(f"Warning: Could not delete {filename}: {e}")

            files_to_remove.append(filename)

        for filename in files_to_remove:
            del self.metadata[filename]

        if deleted_count > 0:
            self._save_metadata()
            print(f"Evicted {deleted_count} files to stay under {gb} GB limit")

        return deleted_count

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats including total size, file counts by type
        """
        total_size = 0
        hrrr_count = 0
        sfbofs_count = 0
        hrrr_size = 0
        sfbofs_size = 0

        for filename, info in self.metadata.items():
            size = info.get('size_bytes', 0)
            total_size += size

            if info.get('type') == 'hrrr':
                hrrr_count += 1
                hrrr_size += size
            elif info.get('type') == 'sfbofs':
                sfbofs_count += 1
                sfbofs_size += size

        return {
            'total_files': len(self.metadata),
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'total_size_gb': total_size / (1024 * 1024 * 1024),
            'hrrr_files': hrrr_count,
            'hrrr_size_mb': hrrr_size / (1024 * 1024),
            'sfbofs_files': sfbofs_count,
            'sfbofs_size_mb': sfbofs_size / (1024 * 1024),
            'max_size_gb': MAX_CACHE_SIZE_GB,
            'expiry_days': CACHE_EXPIRY_DAYS
        }

    def print_stats(self):
        """Print cache statistics to console."""
        stats = self.get_cache_stats()
        print(f"\nCache Statistics:")
        print(f"  Location: {self.cache_dir}")
        print(f"  Total files: {stats['total_files']}")
        print(f"  Total size: {stats['total_size_mb']:.1f} MB ({stats['total_size_gb']:.2f} GB)")
        print(f"  HRRR files: {stats['hrrr_files']} ({stats['hrrr_size_mb']:.1f} MB)")
        print(f"  SFBOFS files: {stats['sfbofs_files']} ({stats['sfbofs_size_mb']:.1f} MB)")
        print(f"  Size limit: {stats['max_size_gb']} GB")
        print(f"  Expiry: {stats['expiry_days']} days")


# Module-level function to get singleton instance
def get_cache_manager() -> CacheManager:
    """Get the singleton CacheManager instance."""
    return CacheManager()
