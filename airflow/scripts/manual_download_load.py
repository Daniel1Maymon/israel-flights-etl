#!/usr/bin/env python3
# Script to manually download flight data from S3 and load it into Postgres without Airflow.
# Steps:
# 1) Parse CLI args (S3 key, prefix, dry-run, etc.).
# 2) Optionally show processed-file status.
# 3) Download raw data files from S3.
# 4) Transform and load data into Postgres.
# 5) Report results and close connections.
"""
Manual script to download flight data from S3 and load it into the database.

This script can be run manually to download and load flight data without
using Airflow. Useful for testing, debugging, or one-off data loads.

Usage:
    python scripts/manual_download_load.py [options]

Options:
    --s3-key KEY        Specific S3 key to download (default: latest.json.gz)
    --no-gzip          Don't expect gzipped files
    --dry-run          Show what would be done without actually doing it
    --help             Show this help message
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.download_and_load import (
    download_and_load_latest,
    download_and_load_from_s3,
    download_gzipped_json_from_s3,
    download_and_load_all_files,
    get_processed_files_status,
    get_postgres_connection
)
from config.settings import S3_BUCKET_NAME, S3_RAW_PATH

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def show_processing_status():
    """Show the processing status of all files."""
    try:
        conn = get_postgres_connection()
        try:
            status_data = get_processed_files_status(conn)
            
            print("\n" + "="*60)
            print("FILE PROCESSING STATUS REPORT")
            print("="*60)
            
            if not status_data:
                print("No files have been processed yet.")
                return
            
            # Count by status
            success_count = sum(1 for item in status_data if item['status'] == 'success')
            failed_count = sum(1 for item in status_data if item['status'] == 'failed')
            
            print(f"Total processed files: {len(status_data)}")
            print(f"Successfully processed: {success_count}")
            print(f"Failed: {failed_count}")
            print()
            
            # Show recent files
            print("Recent files processed:")
            print("-" * 60)
            for item in status_data[:10]:  # Show last 10
                status_icon = "✅" if item['status'] == 'success' else "❌"
                print(f"{status_icon} {item['file_name']} ({item['processed_at']})")
            
            if len(status_data) > 10:
                print(f"... and {len(status_data) - 10} more files")
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        print(f"Error: {e}")


def setup_argument_parser():
    """Set up command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Download flight data from S3 and load it into the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process all files (default behavior)
    python scripts/manual_download_load.py

    # Process all files with specific prefix
    python scripts/manual_download_load.py --prefix uploads/

    # Process a specific file
    python scripts/manual_download_load.py --s3-key uploads/flights_data_20250919_105215.json

    # Dry run (show what would be done)
    python scripts/manual_download_load.py --dry-run

    # Show processing status
    python scripts/manual_download_load.py --status
        """
    )
    
    parser.add_argument('--s3-key', default=None, help='Specific S3 key to download (e.g., uploads/flights_data_20250919_105215.json)')
    parser.add_argument('--no-gzip', action='store_true', default=True, help='Don\'t expect gzipped files (default: True)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without actually doing it')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--all-files', action='store_true', help='Process ALL files from S3 instead of just one file')
    parser.add_argument('--prefix', default=None, help='S3 prefix to filter files (e.g., uploads/, raw/flights/)')
    parser.add_argument('--force', action='store_true', help='Reprocess all files even if already processed')
    parser.add_argument('--status', action='store_true', help='Show processing status of all files')
    
    return parser


def log_configuration(args):
    """Log the script configuration."""
    logger.info("MANUAL DOWNLOAD AND LOAD SCRIPT")
    logger.info("="*60)
    logger.info(f"S3 Bucket: {S3_BUCKET_NAME}")
    logger.info(f"S3 Key: {args.s3_key}")
    logger.info(f"Expect Gzipped: {not args.no_gzip}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info(f"Force Reprocess: {args.force}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("="*60)


def handle_dry_run(args):
    """Handle dry run mode - show what would be done without doing it."""
    logger.info("DRY RUN MODE - No actual operations will be performed")
    if args.all_files:
        logger.info(f"Would process ALL files from: s3://{S3_BUCKET_NAME}/{args.prefix or S3_RAW_PATH}/")
        logger.info("Would process both .json and .json.gz files")
    else:
        logger.info(f"Would download from: s3://{S3_BUCKET_NAME}/{args.s3_key}")
        logger.info(f"Would expect gzipped: {not args.no_gzip}")
    logger.info("Would load data into PostgreSQL database")
    logger.info("Would use identifier-based deduplication (flight_id)")


def process_data(args):
    """Process the data based on command line arguments."""
    # STEP 6A: Decide which processing mode to use
    if args.all_files:
        # MODE 1: Process ALL files from S3 bucket (with file tracking)
        # This downloads every .json and .json.gz file from the specified S3 prefix
        # and processes them one by one, skipping already processed files
        logger.info("Using download_and_load_all_files() to process all files")
        return download_and_load_all_files(prefix=args.prefix, force=args.force)
    elif args.s3_key is None:
        # MODE 2: No specific file provided - default to all files mode
        logger.info("No specific file provided - processing all files by default")
        return download_and_load_all_files(prefix=args.prefix, force=args.force)
    else:
        # MODE 3: Process a specific file that you specify
        # This downloads one specific file from S3 and processes it
        logger.info(f"Using download_and_load_from_s3() with key: {args.s3_key}")
        return download_and_load_from_s3(
            s3_key=args.s3_key,
            use_gzipped=not args.no_gzip,
            force=args.force
        )


def display_results(result, args):
    """Display the processing results."""
    # STEP 7A: Show success header
    logger.info("="*60)
    if result.get("status") == "skipped":
        logger.info("DOWNLOAD AND LOAD SKIPPED (ALREADY PROCESSED)")
    else:
        logger.info("DOWNLOAD AND LOAD COMPLETED SUCCESSFULLY")
    logger.info("="*60)
    logger.info(f"Status: {result['status']}")
    
    # STEP 7B: Show file processing statistics (different for single vs all files mode)
    if 'files_processed' in result:
        # Show results for "all files" mode
        logger.info(f"Files Processed: {result['files_processed']}")
        logger.info(f"Files Failed: {result['files_failed']}")
        logger.info(f"Files Skipped: {result['files_skipped']}")
        logger.info(f"Total Files: {result['total_files']}")
    else:
        # Show results for single file mode
        logger.info(f"S3 Key: {args.s3_key}")
    
    # STEP 7C: Show data processing statistics
    logger.info(f"Total Records: {result['total_records']}")  # How many flight records were found
    logger.info(f"Rows Loaded: {result['rows_loaded']}")      # How many rows were inserted into database
    logger.info(f"Rows Skipped: {result['rows_skipped']}")    # How many rows were duplicates (skipped)
    logger.info(f"Processing Time: {result['processing_time_seconds']:.2f} seconds")  # How long it took
    logger.info(f"S3 Source: {result['s3_source']}")          # Which S3 file was used
    logger.info(f"Timestamp: {result['timestamp']}")          # When the processing happened
    
    # STEP 7D: Show duplicate rate if available
    if 'duplicate_rate' in result:
        logger.info(f"Duplicate Rate: {result['duplicate_rate']:.2f}%")
    
    # STEP 7E: Close the results section
    logger.info("="*60)


def handle_error(e):
    """Handle processing errors."""
    # STEP 8A: Show error header
    logger.error("="*60)
    logger.error("DOWNLOAD AND LOAD FAILED")
    logger.error("="*60)
    
    # STEP 8B: Show error details
    logger.error(f"Error: {str(e)}")  # Show what went wrong
    logger.error(f"Timestamp: {datetime.now().isoformat()}")  # Show when it failed
    
    # STEP 8C: Close error section
    logger.error("="*60)


def main():
    """Main function to handle command line arguments and execute download/load."""
    # STEP 1: Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()
    logger.info(f"Arguments: {args}")
    
    # STEP 2: Configure logging level based on user input
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # STEP 3: Handle special status command (show processing history)
    if args.status:
        show_processing_status()
        return 0
    
    # STEP 4: Log the configuration so user knows what will happen
    log_configuration(args)
    
    # STEP 5: Handle dry run mode (show what would be done without doing it)
    if args.dry_run:
        handle_dry_run(args)
        return 0
    
    # STEP 6: Actually process the data (download, transform, load)
    try:
        result = process_data(args)
        # STEP 7: Show the results of the processing
        display_results(result, args)
        return 0
    except Exception as e:
        # STEP 8: Handle any errors that occurred during processing
        handle_error(e)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
