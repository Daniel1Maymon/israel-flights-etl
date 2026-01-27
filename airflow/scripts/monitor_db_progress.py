#!/usr/bin/env python3
"""
Monitor database record count during ETL processing.

This script periodically checks the flights table count to monitor progress.
"""

import argparse
import os
import psycopg2
import time
from datetime import datetime


def get_db_count():
    """Get current record count from flights table."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_FLIGHTS_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_FLIGHTS_PORT', '5433')),
            database=os.getenv('POSTGRES_FLIGHTS_DB', 'flights_db'),
            user=os.getenv('POSTGRES_FLIGHTS_USER', 'daniel'),
            password=os.getenv('POSTGRES_FLIGHTS_PASSWORD', 'daniel')
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM flights;")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        return None


def main():
    parser = argparse.ArgumentParser(description="Monitor database progress during ETL")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Check interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--initial-count",
        type=int,
        help="Initial count (if not provided, will fetch from DB)"
    )
    
    args = parser.parse_args()
    
    initial_count = args.initial_count
    if initial_count is None:
        initial_count = get_db_count()
        if initial_count is None:
            print("ERROR: Could not connect to database")
            return 1
        print(f"Initial count: {initial_count} records")
    else:
        print(f"Starting with initial count: {initial_count} records")
    
    print(f"Monitoring every {args.interval} seconds...")
    print("Press Ctrl+C to stop\n")
    
    last_count = initial_count
    start_time = time.time()
    
    try:
        while True:
            time.sleep(args.interval)
            current_count = get_db_count()
            
            if current_count is None:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Could not read database")
                continue
            
            elapsed = time.time() - start_time
            new_records = current_count - last_count
            total_new = current_count - initial_count
            
            if new_records > 0:
                rate = new_records / args.interval
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"Count: {current_count:,} | "
                    f"+{new_records:,} (last {args.interval}s) | "
                    f"+{total_new:,} total | "
                    f"Rate: {rate:.1f} records/sec"
                )
            else:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"Count: {current_count:,} | "
                    f"No change (last {args.interval}s)"
                )
            
            last_count = current_count
            
    except KeyboardInterrupt:
        final_count = get_db_count()
        if final_count is not None:
            total_new = final_count - initial_count
            elapsed = time.time() - start_time
            print(f"\n\nFinal count: {final_count:,} records")
            print(f"Total new records: {total_new:,}")
            print(f"Total time: {elapsed/60:.1f} minutes")
            if elapsed > 0:
                print(f"Average rate: {total_new/elapsed:.1f} records/sec")
        return 0


if __name__ == "__main__":
    exit(main())
