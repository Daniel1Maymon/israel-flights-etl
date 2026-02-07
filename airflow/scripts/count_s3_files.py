#!/usr/bin/env python3
# Script to count S3 objects by prefix and file extension.
# Steps:
# 1) Parse CLI args for bucket and prefixes.
# 2) List objects for each prefix via S3 paginator.
# 3) Aggregate counts and total size by file type.
# 4) Print a human-readable or JSON summary.
"""
Count files in S3 bucket by prefix.

This script counts files in different S3 prefixes to understand the data volume.
"""

import argparse
import json
import os
import sys
from typing import Dict, List

import boto3

try:
    from config.settings import S3_BUCKET_NAME as DEFAULT_BUCKET
except Exception:
    DEFAULT_BUCKET = os.getenv("S3_BUCKET_NAME", "etl-flight-pipeline-bucket")


def count_files_in_prefix(bucket: str, prefix: str, s3_client) -> Dict[str, int]:
    """
    Count files in a given S3 prefix.
    
    Returns:
        Dict with counts by file extension and total
    """
    paginator = s3_client.get_paginator("list_objects_v2")
    
    counts = {
        "total": 0,
        ".json": 0,
        ".json.gz": 0,
        ".csv": 0,
        "other": 0
    }
    
    total_size_bytes = 0
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            size = obj.get("Size", 0)
            
            counts["total"] += 1
            total_size_bytes += size
            
            if key.endswith(".json.gz"):
                counts[".json.gz"] += 1
            elif key.endswith(".json"):
                counts[".json"] += 1
            elif key.endswith(".csv"):
                counts[".csv"] += 1
            else:
                counts["other"] += 1
    
    counts["total_size_mb"] = round(total_size_bytes / (1024 * 1024), 2)
    
    return counts


def main():
    parser = argparse.ArgumentParser(description="Count files in S3 bucket by prefix")
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"S3 bucket name (default: {DEFAULT_BUCKET})"
    )
    parser.add_argument(
        "--prefixes",
        nargs="+",
        default=["raw/", "uploads/", "processed/"],
        help="S3 prefixes to count (default: raw/ uploads/ processed/)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )
    
    results = {}
    
    print(f"Counting files in bucket: {args.bucket}")
    print("=" * 80)
    
    for prefix in args.prefixes:
        print(f"\nPrefix: {prefix}")
        try:
            counts = count_files_in_prefix(args.bucket, prefix, s3_client)
            results[prefix] = counts
            
            if args.json:
                continue
            
            print(f"  Total files: {counts['total']}")
            print(f"  Total size: {counts['total_size_mb']} MB")
            if counts[".json.gz"] > 0:
                print(f"  .json.gz files: {counts['.json.gz']}")
            if counts[".json"] > 0:
                print(f"  .json files: {counts['.json']}")
            if counts[".csv"] > 0:
                print(f"  .csv files: {counts['.csv']}")
            if counts["other"] > 0:
                print(f"  Other files: {counts['other']}")
                
        except Exception as e:
            error_msg = f"Error counting prefix {prefix}: {str(e)}"
            results[prefix] = {"error": error_msg}
            if not args.json:
                print(f"  ERROR: {error_msg}")
    
    # Summary
    total_all = sum(r.get("total", 0) for r in results.values() if isinstance(r, dict) and "error" not in r)
    
    if args.json:
        results["_summary"] = {"total_files_all_prefixes": total_all}
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "=" * 80)
        print(f"SUMMARY: Total files across all prefixes: {total_all}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
