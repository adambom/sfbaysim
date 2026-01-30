#!/usr/bin/env python3
"""
Prefetch HRRR and SFBOFS data for offline use.

Downloads forecast data for a specified time window and caches it locally.

Usage:
    python scripts/prefetch_data.py --start "2025-01-30 14:00" --hours 6
    python scripts/prefetch_data.py --hours 12  # Start from now
    python scripts/prefetch_data.py --start "2025-01-30 14:00" --hours 6 --sfbofs-only
    python scripts/prefetch_data.py --start "2025-01-30 14:00" --hours 6 --hrrr-only
"""

import argparse
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CACHE_EXPIRY_DAYS, MAX_CACHE_SIZE_GB
from data.cache_manager import get_cache_manager


def parse_datetime(dt_str: str) -> datetime:
    """Parse datetime string in various formats."""
    formats = [
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M',
        '%Y-%m-%dT%H:%M:%S',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Could not parse datetime: {dt_str}")


def prefetch_hrrr(start_time: datetime, hours: int, cache_mgr) -> tuple:
    """
    Prefetch HRRR data for the specified time window.

    Returns:
        (files_downloaded, files_cached, files_failed)
    """
    from data.hrrr_grid import HRRRGridData

    downloaded = 0
    cached = 0
    failed = 0

    print(f"\nPrefetching HRRR data for {hours} hours starting {start_time}...")

    for hour_offset in range(hours):
        target_time = start_time + timedelta(hours=hour_offset)
        print(f"\n  Hour {hour_offset}: {target_time.strftime('%Y-%m-%d %H:%M')} UTC")

        try:
            # HRRRGridData will handle caching internally
            hrrr = HRRRGridData(target_time)
            hrrr.fetch_and_build()

            # Check if it was a cache hit or download
            # (The class prints this, so we can't easily tell, just count as success)
            downloaded += 1
            print(f"    OK")

        except Exception as e:
            print(f"    FAILED: {e}")
            failed += 1

    return downloaded, cached, failed


def prefetch_sfbofs(start_time: datetime, hours: int, cache_mgr) -> tuple:
    """
    Prefetch SFBOFS data for the specified time window.

    Returns:
        (files_downloaded, files_cached, files_failed)
    """
    from data.sfbofs_hour import SFBOFSHourData

    downloaded = 0
    cached = 0
    failed = 0

    print(f"\nPrefetching SFBOFS data for {hours} hours starting {start_time}...")

    # Share triangulation across all hours for efficiency
    shared_tri = None

    for hour_offset in range(hours):
        target_time = start_time + timedelta(hours=hour_offset)
        print(f"\n  Hour {hour_offset}: {target_time.strftime('%Y-%m-%d %H:%M')} UTC")

        try:
            sfbofs = SFBOFSHourData(target_time, shared_triangulation=shared_tri)
            sfbofs.fetch_and_build()

            # Reuse triangulation for subsequent hours
            if shared_tri is None and sfbofs.shared_tri is not None:
                shared_tri = sfbofs.shared_tri

            downloaded += 1
            print(f"    OK")

        except Exception as e:
            print(f"    FAILED: {e}")
            failed += 1

    return downloaded, cached, failed


def main():
    parser = argparse.ArgumentParser(
        description='Prefetch HRRR and SFBOFS forecast data for offline use.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Prefetch 6 hours starting now
    python scripts/prefetch_data.py --hours 6

    # Prefetch 12 hours starting from a specific time
    python scripts/prefetch_data.py --start "2025-01-30 14:00" --hours 12

    # Only prefetch SFBOFS data
    python scripts/prefetch_data.py --hours 6 --sfbofs-only

    # Only prefetch HRRR data
    python scripts/prefetch_data.py --hours 6 --hrrr-only
        """
    )

    parser.add_argument(
        '--start',
        type=str,
        help='Start time in UTC (default: now). Format: "YYYY-MM-DD HH:MM"'
    )

    parser.add_argument(
        '--hours',
        type=int,
        default=6,
        help='Number of hours to prefetch (default: 6)'
    )

    parser.add_argument(
        '--hrrr-only',
        action='store_true',
        help='Only prefetch HRRR (wind) data'
    )

    parser.add_argument(
        '--sfbofs-only',
        action='store_true',
        help='Only prefetch SFBOFS (current) data'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Just show cache statistics and exit'
    )

    args = parser.parse_args()

    # Initialize cache manager
    print("=" * 60)
    print("SF Bay Sailing Simulator - Data Prefetch Tool")
    print("=" * 60)

    cache_mgr = get_cache_manager()

    # Show stats and exit if requested
    if args.stats:
        cache_mgr.print_stats()
        return 0

    # Parse start time
    if args.start:
        try:
            start_time = parse_datetime(args.start)
        except ValueError as e:
            print(f"Error: {e}")
            return 1
    else:
        start_time = datetime.now(timezone.utc).replace(tzinfo=None)

    hours = args.hours

    print(f"\nPrefetch configuration:")
    print(f"  Start time: {start_time.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"  Duration: {hours} hours")
    print(f"  End time: {(start_time + timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M')} UTC")

    # Determine what to fetch
    fetch_hrrr = not args.sfbofs_only
    fetch_sfbofs = not args.hrrr_only

    if fetch_hrrr and fetch_sfbofs:
        print(f"  Data: HRRR (wind) + SFBOFS (currents)")
    elif fetch_hrrr:
        print(f"  Data: HRRR (wind) only")
    else:
        print(f"  Data: SFBOFS (currents) only")

    # Estimate data size
    hrrr_size_mb = hours * 155 if fetch_hrrr else 0
    sfbofs_size_mb = hours * 3 if fetch_sfbofs else 0
    total_mb = hrrr_size_mb + sfbofs_size_mb

    print(f"\nEstimated download size:")
    if fetch_hrrr:
        print(f"  HRRR: ~{hrrr_size_mb} MB ({hours} files x ~155 MB)")
    if fetch_sfbofs:
        print(f"  SFBOFS: ~{sfbofs_size_mb} MB ({hours} files x ~3 MB)")
    print(f"  Total: ~{total_mb} MB")

    # Confirm
    print("\nStarting prefetch...\n")

    total_downloaded = 0
    total_failed = 0

    # Prefetch HRRR
    if fetch_hrrr:
        downloaded, cached, failed = prefetch_hrrr(start_time, hours, cache_mgr)
        total_downloaded += downloaded
        total_failed += failed

    # Prefetch SFBOFS
    if fetch_sfbofs:
        downloaded, cached, failed = prefetch_sfbofs(start_time, hours, cache_mgr)
        total_downloaded += downloaded
        total_failed += failed

    # Summary
    print("\n" + "=" * 60)
    print("Prefetch complete!")
    print(f"  Files processed: {total_downloaded}")
    print(f"  Failed: {total_failed}")

    # Enforce cache policies
    print("\nEnforcing cache policies...")
    cache_mgr.enforce_expiry(CACHE_EXPIRY_DAYS)
    cache_mgr.enforce_size_limit(MAX_CACHE_SIZE_GB)

    # Final stats
    cache_mgr.print_stats()

    return 0 if total_failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
