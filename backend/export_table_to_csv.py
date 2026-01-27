import argparse
import csv
import os
import re
from pathlib import Path
from typing import Iterable, List

from sqlalchemy import create_engine, text

# Reuse existing backend settings for DB connection
try:
    from app.config import settings
except Exception as import_error:  # Fallback to env if app.config isn't importable
    class _EnvSettings:
        @property
        def database_url(self) -> str:
            return os.environ.get("DATABASE_URL") or (
                f"postgresql+psycopg://{os.environ.get('DB_USER','daniel')}:"
                f"{os.environ.get('DB_PASSWORD','daniel')}@"
                f"{os.environ.get('DB_HOST','localhost')}:"
                f"{os.environ.get('DB_PORT','5433')}/"
                f"{os.environ.get('DB_NAME','flights_db')}"
            )

    settings = _EnvSettings()


def validate_table_identifier(identifier: str) -> None:
    """Ensure the table identifier is a simple SQL identifier to avoid injection."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?", identifier):
        raise ValueError(
            "Invalid table identifier. Use plain table or schema.table with letters, numbers and underscores only."
        )


def write_csv(path: Path, headers: List[str], rows: Iterable[Iterable]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def export_first_n_rows(table: str, limit: int, output_path: Path, order_by: str | None = None) -> Path:
    validate_table_identifier(table)
    if order_by:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", order_by):
            raise ValueError("Invalid order_by column name.")

    engine = create_engine(settings.database_url)

    order_clause = f" ORDER BY {order_by}" if order_by else ""
    # Note: table name cannot be bound as a parameter; validated above
    sql = text(f"SELECT * FROM {table}{order_clause} LIMIT :limit")

    with engine.connect() as conn:
        result = conn.execute(sql, {"limit": limit})
        headers = list(result.keys())
        rows = list(result.fetchall())

    write_csv(output_path, headers, rows)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export first N rows from a table to CSV")
    parser.add_argument("--table", required=True, help="Table name (optionally schema.table)")
    parser.add_argument("--limit", type=int, default=2000, help="Number of rows to export (default: 2000)")
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path. Default: data/exports/<table>_first<limit>.csv at repo root",
    )
    parser.add_argument(
        "--order-by",
        dest="order_by",
        default=None,
        help="Optional column name to ORDER BY for deterministic selection",
    )

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    default_out = repo_root / "data" / "exports" / f"{args.table.replace('.', '_')}_first{args.limit}.csv"
    output_path = Path(args.output) if args.output else default_out

    exported = export_first_n_rows(args.table, args.limit, output_path, args.order_by)
    print(str(exported))


if __name__ == "__main__":
    main()








