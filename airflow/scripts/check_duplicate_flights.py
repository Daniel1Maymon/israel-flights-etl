#!/usr/bin/env python3
# Script to detect duplicate flights and verify flight_id consistency in Postgres.
# Steps:
# 1) Check for duplicate flight_id values.
# 2) Check for duplicate natural-key combinations.
# 3) Verify flight_id hashes match natural keys.
# 4) Optionally remove duplicates (keeping the most recent by scrape_timestamp).
"""
Check for duplicate flights in the database and optionally remove them.

This script:
1. Checks for duplicate flight_id values (shouldn't exist due to PRIMARY KEY constraint)
2. Checks for duplicate natural keys (the combination of fields that make up flight_id)
3. Optionally removes duplicates, keeping the most recent record based on scrape_timestamp

The unified key (flight_id) is an MD5 hash of:
- airline_code
- flight_number
- direction (arrival_departure_code)
- location_iata (airport_code)
- scheduled_departure
"""

import sys
import os
import logging
import argparse
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_FLIGHTS_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_FLIGHTS_PORT', '5433')),
        database=os.getenv('POSTGRES_FLIGHTS_DB', 'flights_db'),
        user=os.getenv('POSTGRES_FLIGHTS_USER', 'daniel'),
        password=os.getenv('POSTGRES_FLIGHTS_PASSWORD', 'daniel')
    )


def compute_flight_uuid(airline_code, flight_number, direction, location_iata, scheduled_departure):
    """Compute flight_id using the same logic as the DAG."""
    natural_key = f"{airline_code}_{flight_number}_{direction}_{location_iata}_{scheduled_departure}"
    return hashlib.md5(natural_key.encode()).hexdigest()


def check_duplicate_flight_ids(conn):
    """
    Check for duplicate flight_id values.
    This shouldn't happen due to PRIMARY KEY constraint, but let's verify.
    """
    logger.info("Checking for duplicate flight_id values...")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT flight_id, COUNT(*) as count
        FROM flights
        GROUP BY flight_id
        HAVING COUNT(*) > 1
        ORDER BY count DESC;
    """)
    
    duplicates = cursor.fetchall()
    cursor.close()
    
    if duplicates:
        logger.warning(f"Found {len(duplicates)} duplicate flight_id values!")
        for flight_id, count in duplicates[:10]:  # Show first 10
            logger.warning(f"  flight_id: {flight_id}, count: {count}")
        if len(duplicates) > 10:
            logger.warning(f"  ... and {len(duplicates) - 10} more")
        return True, duplicates
    else:
        logger.info("✓ No duplicate flight_id values found (as expected)")
        return False, []


def check_duplicate_natural_keys(conn):
    """
    Check for duplicate natural keys (the combination that makes up flight_id).
    This can happen if the same flight appears multiple times with different flight_ids
    due to data inconsistencies or hash collisions.
    """
    logger.info("Checking for duplicate natural keys...")
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT 
            airline_code,
            flight_number,
            direction,
            location_iata,
            scheduled_time,
            COUNT(*) as count,
            COUNT(DISTINCT flight_id) as distinct_flight_ids,
            ARRAY_AGG(flight_id ORDER BY scrape_timestamp DESC) as flight_ids,
            ARRAY_AGG(scrape_timestamp ORDER BY scrape_timestamp DESC) as timestamps
        FROM flights
        GROUP BY airline_code, flight_number, direction, location_iata, scheduled_time
        HAVING COUNT(*) > 1
        ORDER BY count DESC;
    """)
    
    duplicates = cursor.fetchall()
    cursor.close()
    
    if duplicates:
        logger.warning(f"Found {len(duplicates)} duplicate natural key combinations!")
        
        # Show details of first 10 duplicates
        for dup in duplicates[:10]:
            logger.warning(
                f"  Natural key: {dup['airline_code']}_{dup['flight_number']}_"
                f"{dup['direction']}_{dup['location_iata']}_{dup['scheduled_time']} | "
                f"Count: {dup['count']} | "
                f"Distinct flight_ids: {dup['distinct_flight_ids']}"
            )
            logger.warning(f"    Flight IDs: {dup['flight_ids']}")
        
        if len(duplicates) > 10:
            logger.warning(f"  ... and {len(duplicates) - 10} more")
        
        return True, duplicates
    else:
        logger.info("✓ No duplicate natural keys found")
        return False, []


def verify_flight_id_consistency(conn):
    """
    Verify that flight_id values match the computed hash of natural keys.
    This helps identify if there are any inconsistencies in the data.
    """
    logger.info("Verifying flight_id consistency with natural keys...")
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT 
            flight_id,
            airline_code,
            flight_number,
            direction,
            location_iata,
            scheduled_time
        FROM flights
        LIMIT 10000;
    """)
    
    rows = cursor.fetchall()
    cursor.close()
    
    inconsistencies = []
    for row in rows:
        computed_id = compute_flight_uuid(
            str(row['airline_code'] or ''),
            str(row['flight_number'] or ''),
            str(row['direction'] or ''),
            str(row['location_iata'] or ''),
            str(row['scheduled_time'] or '')
        )
        
        if computed_id != row['flight_id']:
            inconsistencies.append({
                'flight_id': row['flight_id'],
                'computed_id': computed_id,
                'natural_key': f"{row['airline_code']}_{row['flight_number']}_{row['direction']}_{row['location_iata']}_{row['scheduled_time']}"
            })
    
    if inconsistencies:
        logger.warning(f"Found {len(inconsistencies)} inconsistent flight_id values!")
        for inc in inconsistencies[:10]:
            logger.warning(
                f"  Stored: {inc['flight_id']} | "
                f"Computed: {inc['computed_id']} | "
                f"Natural key: {inc['natural_key']}"
            )
        if len(inconsistencies) > 10:
            logger.warning(f"  ... and {len(inconsistencies) - 10} more")
        return True, inconsistencies
    else:
        logger.info(f"✓ All {len(rows)} checked flight_id values are consistent")
        return False, []


def remove_duplicate_natural_keys(conn, dry_run=True):
    """
    Remove duplicate records based on natural keys, keeping the most recent one.
    
    Args:
        conn: Database connection
        dry_run: If True, only show what would be deleted without actually deleting
    """
    logger.info(f"Removing duplicate natural keys (dry_run={dry_run})...")
    
    cursor = conn.cursor()
    
    # Find duplicates and keep the one with the most recent scrape_timestamp
    query = """
        WITH ranked_flights AS (
            SELECT 
                flight_id,
                ROW_NUMBER() OVER (
                    PARTITION BY airline_code, flight_number, direction, location_iata, scheduled_time
                    ORDER BY scrape_timestamp DESC NULLS LAST, flight_id
                ) as rn
            FROM flights
        )
        SELECT flight_id
        FROM ranked_flights
        WHERE rn > 1;
    """
    
    cursor.execute(query)
    duplicate_ids = [row[0] for row in cursor.fetchall()]
    
    if not duplicate_ids:
        logger.info("✓ No duplicates to remove")
        cursor.close()
        return 0
    
    logger.info(f"Found {len(duplicate_ids)} duplicate records to remove")
    
    if dry_run:
        logger.info("DRY RUN: Would delete the following flight_ids:")
        for flight_id in duplicate_ids[:20]:
            logger.info(f"  {flight_id}")
        if len(duplicate_ids) > 20:
            logger.info(f"  ... and {len(duplicate_ids) - 20} more")
        cursor.close()
        return len(duplicate_ids)
    
    # Actually delete duplicates
    delete_query = """
        DELETE FROM flights
        WHERE flight_id = ANY(%s);
    """
    
    cursor.execute(delete_query, (duplicate_ids,))
    deleted_count = cursor.rowcount
    conn.commit()
    cursor.close()
    
    logger.info(f"✓ Deleted {deleted_count} duplicate records")
    return deleted_count


def get_database_stats(conn):
    """Get general database statistics."""
    cursor = conn.cursor()
    
    stats = {}
    
    # Total count
    cursor.execute("SELECT COUNT(*) FROM flights;")
    stats['total_flights'] = cursor.fetchone()[0]
    
    # Unique flight_ids
    cursor.execute("SELECT COUNT(DISTINCT flight_id) FROM flights;")
    stats['unique_flight_ids'] = cursor.fetchone()[0]
    
    # Unique natural keys
    cursor.execute("""
        SELECT COUNT(DISTINCT (airline_code, flight_number, direction, location_iata, scheduled_time))
        FROM flights;
    """)
    stats['unique_natural_keys'] = cursor.fetchone()[0]
    
    # Date range
    cursor.execute("SELECT MIN(scheduled_time), MAX(scheduled_time) FROM flights;")
    min_date, max_date = cursor.fetchone()
    stats['date_range'] = (min_date, max_date)
    
    cursor.close()
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Check for duplicate flights in the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check for duplicates (read-only)
  python check_duplicate_flights.py

  # Check and show what would be removed
  python check_duplicate_flights.py --dry-run

  # Actually remove duplicates
  python check_duplicate_flights.py --remove-duplicates
        """
    )
    parser.add_argument(
        '--remove-duplicates',
        action='store_true',
        help='Remove duplicate records (keeps most recent based on scrape_timestamp)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--skip-consistency-check',
        action='store_true',
        help='Skip flight_id consistency verification (faster for large databases)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("DUPLICATE FLIGHTS CHECKER")
    logger.info("=" * 80)
    
    try:
        conn = get_db_connection()
        logger.info("✓ Connected to database")
        
        # Get database statistics
        stats = get_database_stats(conn)
        logger.info("\nDatabase Statistics:")
        logger.info(f"  Total flights: {stats['total_flights']:,}")
        logger.info(f"  Unique flight_ids: {stats['unique_flight_ids']:,}")
        logger.info(f"  Unique natural keys: {stats['unique_natural_keys']:,}")
        if stats['date_range'][0] and stats['date_range'][1]:
            logger.info(f"  Date range: {stats['date_range'][0]} to {stats['date_range'][1]}")
        
        # Check for issues
        logger.info("\n" + "=" * 80)
        logger.info("CHECKING FOR DUPLICATES")
        logger.info("=" * 80)
        
        has_duplicate_ids, duplicate_ids = check_duplicate_flight_ids(conn)
        has_duplicate_keys, duplicate_keys = check_duplicate_natural_keys(conn)
        
        if not args.skip_consistency_check:
            has_inconsistencies, inconsistencies = verify_flight_id_consistency(conn)
        else:
            has_inconsistencies = False
            logger.info("Skipping flight_id consistency check (--skip-consistency-check)")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        
        issues_found = False
        
        if has_duplicate_ids:
            logger.warning(f"⚠ Found {len(duplicate_ids)} duplicate flight_id values")
            issues_found = True
        else:
            logger.info("✓ No duplicate flight_id values")
        
        if has_duplicate_keys:
            total_duplicate_records = sum(dup['count'] - 1 for dup in duplicate_keys)
            logger.warning(f"⚠ Found {len(duplicate_keys)} duplicate natural key combinations")
            logger.warning(f"  Total duplicate records: {total_duplicate_records:,}")
            issues_found = True
        else:
            logger.info("✓ No duplicate natural keys")
        
        if has_inconsistencies:
            logger.warning(f"⚠ Found {len(inconsistencies)} inconsistent flight_id values")
            issues_found = True
        else:
            logger.info("✓ All flight_id values are consistent")
        
        # Remove duplicates if requested
        if args.remove_duplicates or args.dry_run:
            logger.info("\n" + "=" * 80)
            logger.info("REMOVING DUPLICATES")
            logger.info("=" * 80)
            
            deleted = remove_duplicate_natural_keys(conn, dry_run=args.dry_run)
            
            if not args.dry_run and deleted > 0:
                # Get updated statistics
                stats_after = get_database_stats(conn)
                logger.info("\nUpdated Statistics:")
                logger.info(f"  Total flights: {stats_after['total_flights']:,} (removed {stats['total_flights'] - stats_after['total_flights']:,})")
                logger.info(f"  Unique flight_ids: {stats_after['unique_flight_ids']:,}")
                logger.info(f"  Unique natural keys: {stats_after['unique_natural_keys']:,}")
        
        conn.close()
        
        if issues_found and not args.remove_duplicates and not args.dry_run:
            logger.info("\n💡 Tip: Use --dry-run to see what would be removed, or --remove-duplicates to actually remove duplicates")
            return 1
        else:
            return 0
            
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
