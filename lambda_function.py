# file: lambda_function.py
# Purpose: Fetch full CKAN dataset (JSON with pagination), upload to S3 (timestamped + latest),
#          store small state to skip uploads when data hasn't changed.

import os
import json
import logging
import hashlib
import tempfile
import gzip
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

import boto3
import requests
from dotenv import load_dotenv

# Load .env for local debugging (no effect in Lambda unless layer/code includes it)
load_dotenv()

# ---- Logging ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# ---- Environment ----
S3_BUCKET_NAME: str = os.environ["S3_BUCKET_NAME"]
S3_RAW_PATH: str = os.environ.get("S3_RAW_PATH", "raw/flights")
STATE_KEY: str = os.environ.get("STATE_KEY", "state/feed_state.json")
RESOURCE_ID: str = os.environ.get("RESOURCE_ID", "e83f763b-b7d7-479e-b172-ae981ddc6de5")
CKAN_URL: str = os.environ.get("CKAN_URL", "https://data.gov.il/api/3/action/datastore_search")
BATCH_SIZE: int = int(os.environ.get("BATCH_SIZE", "1000"))
REQUEST_TIMEOUT: int = int(os.environ.get("REQUEST_TIMEOUT", "60"))

# ---- AWS ----
s3 = boto3.client("s3")


def _fetch_ckan_full(resource_id: str, base_url: str, batch_size: int, timeout: int) -> List[Dict[str, Any]]:
    """Fetch all records from CKAN datastore_search with pagination."""
    all_records: List[Dict[str, Any]] = []
    offset: int = 0
    while True:
        params = {"resource_id": resource_id, "limit": batch_size, "offset": offset}
        resp = requests.get(base_url, params=params, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"CKAN request failed: {resp.status_code} {resp.text[:200]}")
        payload = resp.json()
        result = payload.get("result") or {}
        records = result.get("records") or []
        if not records:
            break
        all_records.extend(records)
        offset += batch_size
        logger.info("Fetched %d records (total: %d)", len(records), len(all_records))
    return all_records


def _calc_hash(records: List[Dict[str, Any]]) -> str:
    """Return stable SHA256 over the JSON content (indent=0 to avoid spacing diffs)."""
    blob = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _get_state(bucket: str, key: str) -> Tuple[Optional[str], Optional[int]]:
    """Read small state (hash, count) from S3; return (hash, last_count)."""
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        st = json.loads(obj["Body"].read().decode("utf-8"))
        return st.get("hash"), st.get("last_count")
    except s3.exceptions.NoSuchKey:
        return None, None
    except Exception as e:
        logger.warning("State read failed (%s); continuing without state.", e)
        return None, None


def _put_state(bucket: str, key: str, data_hash: str, count: int) -> None:
    """Write small state JSON to S3."""
    body = json.dumps({"hash": data_hash, "last_count": count}, ensure_ascii=False).encode("utf-8")
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ServerSideEncryption="AES256",
        ContentType="application/json",
    )


def _upload_json_gzip(bucket: str, prefix: str, records: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Upload timestamped JSON.gz and latest.json.gz; return (timestamped_key, latest_key)."""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    timestamped_key = f"{prefix}/flights_data_{ts}.json.gz"
    latest_key = f"{prefix}/latest.json.gz"

    # Create JSON string
    json_str = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    
    # Compress to gzip
    compressed_data = gzip.compress(json_str.encode("utf-8"))

    # Upload compressed data directly to S3
    s3.put_object(
        Bucket=bucket,
        Key=timestamped_key,
        Body=compressed_data,
        ServerSideEncryption="AES256",
        ContentType="application/json",
        ContentEncoding="gzip"
    )
    
    s3.put_object(
        Bucket=bucket,
        Key=latest_key,
        Body=compressed_data,
        ServerSideEncryption="AES256",
        ContentType="application/json",
        ContentEncoding="gzip"
    )

    return timestamped_key, latest_key




def read_gzip_from_s3(bucket: str, key: str) -> List[Dict[str, Any]]:
    """Read and decompress a gzipped JSON file from S3."""
    try:
        # Get the gzipped object from S3
        response = s3.get_object(Bucket=bucket, Key=key)
        
        # Read and decompress the data
        compressed_data = response['Body'].read()
        decompressed_data = gzip.decompress(compressed_data)
        
        # Parse JSON
        json_str = decompressed_data.decode('utf-8')
        records = json.loads(json_str)
        
        logger.info('Successfully read and decompressed %d records from s3://%s/%s', 
                   len(records), bucket, key)
        return records
        
    except Exception as e:
        logger.error('Failed to read gzipped file from s3://%s/%s: %s', bucket, key, e)
        raise


def test_read_latest_gzip() -> None:
    """Test function to read and verify the latest gzipped file."""
    try:
        latest_key = f"{S3_RAW_PATH}/latest.json.gz"
        records = read_gzip_from_s3(S3_BUCKET_NAME, latest_key)
        
        logger.info("Successfully read %d records from gzipped file", len(records))
        logger.info("File: s3://%s/%s", S3_BUCKET_NAME, latest_key)
        
        # Show sample record
        if records:
            logger.info("Sample record keys: %s", list(records[0].keys()))
            logger.info("First record: %s...", json.dumps(records[0], ensure_ascii=False, indent=2)[:200])
        
    except Exception as e:
        logger.error("Error reading gzipped file: %s", e)


def print_first_10_records(records: List[Dict[str, Any]]) -> None:
    """Print the first 10 records from the dataset."""
    logger.info("Total records: %d", len(records))
    logger.info("=" * 80)
    logger.info("First 10 records:")
    logger.info("=" * 80)
    
    for i, record in enumerate(records[:1], 1):
        logger.info("Record %d:", i)
        for key, value in record.items():
            logger.info("  %s: %s", key, value)
        logger.info("-" * 40)


def create_and_test_gzip_file(records: List[Dict[str, Any]]) -> str:
    """Create a gzip file, test reading it, print 10 rows, return file path."""
    import tempfile
    
    # Step 1: Create gzipped file on disk
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    temp_dir = tempfile.gettempdir()
    gzip_file_path = f"{temp_dir}/flights_data_{ts}.json.gz"
    
    logger.info("Creating gzipped file: %s", gzip_file_path)
    json_str = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    
    with gzip.open(gzip_file_path, 'wt', encoding='utf-8') as f:
        f.write(json_str)
    
    # Step 2: Test reading the gzipped file back to JSON
    logger.info("Testing: Reading gzipped file back to JSON...")
    with gzip.open(gzip_file_path, 'rt', encoding='utf-8') as f:
        test_json_str = f.read()
        test_records = json.loads(test_json_str)
    
    # Step 3: Print first 10 rows from the test read
    logger.info("Test successful! Printing first 10 rows from gzipped file:")
    print_first_10_records(test_records)
    
    logger.info("Gzip file created and tested successfully: %s", gzip_file_path)
    return gzip_file_path


def upload_gzip_file_to_s3(gzip_file_path: str, bucket: str, prefix: str) -> Tuple[str, str]:
    """Upload a gzipped file to S3 and return the S3 keys."""
    import os
    
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    timestamped_key = f"{prefix}/flights_data_{ts}.json.gz"
    latest_key = f"{prefix}/latest.json.gz"
    
    # Upload the gzipped file
    s3.upload_file(
        gzip_file_path, 
        bucket, 
        timestamped_key,
        ExtraArgs={
            'ServerSideEncryption': 'AES256',
            'ContentType': 'application/json',
            'ContentEncoding': 'gzip'
        }
    )
    
    s3.upload_file(
        gzip_file_path, 
        bucket, 
        latest_key,
        ExtraArgs={
            'ServerSideEncryption': 'AES256',
            'ContentType': 'application/json',
            'ContentEncoding': 'gzip'
        }
    )
    
    # Clean up the temporary file
    try:
        os.remove(gzip_file_path)
        logger.info("Cleaned up temporary file: %s", gzip_file_path)
    except OSError:
        pass
    
    return timestamped_key, latest_key
def lambda_handler(event, context) -> Dict[str, Any]:
    """AWS Lambda entrypoint (also callable locally)."""
    # Step 1: Fetch data from API
    records = _fetch_ckan_full(
        resource_id=RESOURCE_ID,
        base_url=CKAN_URL,
        batch_size=BATCH_SIZE,
        timeout=REQUEST_TIMEOUT,
    )
    count = len(records)
    data_hash = _calc_hash(records)

    prev_hash, prev_count = _get_state(S3_BUCKET_NAME, STATE_KEY)
    if prev_hash == data_hash:
        logger.info("No change detected (same hash). Skipping upload.")
        return {"status": "no_change", "records": count}

    # Step 2: Create gzipped file, test reading it, print 10 rows
    gzip_file_path = create_and_test_gzip_file(records)
    
    # Step 3: Upload the gzipped file to S3
    logger.info("Uploading gzipped file to AWS S3...")
    key_ts, key_latest = upload_gzip_file_to_s3(gzip_file_path, S3_BUCKET_NAME, S3_RAW_PATH)
    _put_state(S3_BUCKET_NAME, STATE_KEY, data_hash, count)

    logger.info("Uploaded %d records to s3://%s/{%s , %s}", count, S3_BUCKET_NAME, key_ts, key_latest)
    return {
        "status": "uploaded",
        "records": count,
        "timestamped_key": key_ts,
        "latest_key": key_latest,
    }


if __name__ == "__main__":
    # Local debug entrypoint (simulate Lambda)
    out = lambda_handler(event={}, context=None)
    logger.info("Lambda execution result: %s", json.dumps(out, ensure_ascii=False, indent=2))
