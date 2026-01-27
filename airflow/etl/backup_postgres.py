"""
Utilities to back up the flights PostgreSQL database to S3.

This is designed to run inside the Airflow containers.
"""

from __future__ import annotations

import gzip
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3


@dataclass(frozen=True)
class PostgresConnInfo:
    host: str
    port: int
    user: str
    password: str
    database: str


def _truthy_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def get_flights_db_conn_from_env() -> PostgresConnInfo:
    """
    Uses the same env var names that are already used across the repo.
    """
    return PostgresConnInfo(
        host=os.getenv("POSTGRES_FLIGHTS_HOST", "postgres_flights"),
        port=int(os.getenv("POSTGRES_FLIGHTS_PORT", "5432")),
        user=os.getenv("POSTGRES_FLIGHTS_USER", "daniel"),
        password=os.getenv("POSTGRES_FLIGHTS_PASSWORD", "daniel"),
        database=os.getenv("POSTGRES_FLIGHTS_DB", "flights_db"),
    )


def backup_flights_db_to_s3(
    *,
    bucket: Optional[str] = None,
    prefix: str = "backups/postgres",
    conn: Optional[PostgresConnInfo] = None,
) -> Dict[str, Any]:
    """
    Create a gzip-compressed pg_dump and upload it to S3.

    Returns:
        Dict with keys: status, s3_bucket, s3_key, bytes
    """
    if not _truthy_env("ENABLE_DB_BACKUPS", "false"):
        logging.info("DB backup skipped: ENABLE_DB_BACKUPS is not true")
        return {"status": "skipped", "reason": "ENABLE_DB_BACKUPS is not true"}

    if bucket is None:
        bucket = os.getenv("S3_BUCKET_NAME")
        if not bucket:
            try:
                from config.settings import S3_BUCKET_NAME as _S3_BUCKET_NAME

                bucket = _S3_BUCKET_NAME
            except Exception:
                bucket = None
    if not bucket:
        raise ValueError("S3_BUCKET_NAME is not set; cannot upload DB backup")

    if conn is None:
        conn = get_flights_db_conn_from_env()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    key = f"{prefix}/flights_db_{ts}.sql.gz"

    # Create raw dump file then gzip it (more reliable than relying on pg_dump gzip options)
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, "flights_db.sql")
        gz_path = os.path.join(tmpdir, "flights_db.sql.gz")

        env = os.environ.copy()
        env["PGPASSWORD"] = conn.password

        cmd = [
            "pg_dump",
            "--no-owner",
            "--no-privileges",
            "--format=plain",
            "--host",
            conn.host,
            "--port",
            str(conn.port),
            "--username",
            conn.user,
            conn.database,
        ]

        logging.info("Starting pg_dump for flights_db")
        with open(raw_path, "wb") as f:
            subprocess.run(cmd, env=env, check=True, stdout=f, stderr=subprocess.PIPE)

        logging.info("Compressing pg_dump output")
        with open(raw_path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)

        size = os.path.getsize(gz_path)
        logging.info("Uploading DB backup to S3", extra={"bucket": bucket, "key": key, "bytes": size})

        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
        s3.upload_file(gz_path, bucket, key)

    logging.info("DB backup uploaded", extra={"s3_bucket": bucket, "s3_key": key, "bytes": size})
    return {"status": "success", "s3_bucket": bucket, "s3_key": key, "bytes": size}

