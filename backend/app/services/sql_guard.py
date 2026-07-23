"""
sql_guard.py — parser-based validation for LLM-generated SQL (the AI-search fallback path).

We do NOT trust regex keyword-blocking (trivially bypassed: DR/**/OP, casing, writing CTEs).
Instead we parse to an AST with sqlglot and assert *structure*:
  - exactly ONE statement, and it is a SELECT / set-operation
  - no DML/DDL nodes anywhere (incl. data-modifying CTEs, SELECT INTO)
  - every referenced table is in the whitelist (CTE aliases excepted)
  - no dangerous functions (pg_sleep, pg_read_file, copy, dblink, current_setting, ...)
  - a LIMIT is present and <= max_rows (injected/clamped)

This is one layer; the read-only DB role + statement_timeout are the ultimate backstop.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

# Only these tables may be referenced.
ALLOWED_TABLES = {"flights"}

# Statement/expression node *type names* that must never appear (version-robust: compare by name).
FORBIDDEN_NODE_NAMES = {
    "Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter", "AlterTable",
    "TruncateTable", "Command", "Set", "SetItem", "Grant", "Into", "Copy", "Transaction",
    "Commit", "Rollback", "Use", "LoadData", "Attach", "Detach",
}

# Root must be one of these (otherwise it's a DDL/DML/command).
ALLOWED_ROOT_NAMES = {"Select", "Union", "Except", "Intersect", "Subquery"}

# Dangerous functions (file/network/process/config/exec).
BANNED_FUNCS = {
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_read_server_files",
    "pg_ls_dir", "pg_stat_file", "lo_import", "lo_export", "lo_get", "lo_put",
    "dblink", "dblink_exec", "dblink_connect", "set_config", "current_setting",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf", "copy",
    "query_to_xml", "txid_current", "inet_server_addr", "inet_client_addr",
    "pg_ls_waldir", "convert_from", "pg_read_binary_file",
}


class SqlGuardError(Exception):
    """Raised when generated SQL fails validation. Message is for logs only — never shown raw."""


def validate_and_prepare(sql: str, max_rows: int = 50) -> str:
    """Validate LLM SQL and return a sanitized, LIMIT-bounded SELECT, or raise SqlGuardError."""
    if not sql or not sql.strip():
        raise SqlGuardError("empty sql")

    # 1) exactly one statement
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception as e:  # parse failure = reject
        raise SqlGuardError(f"unparseable: {e}") from e
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SqlGuardError(f"expected 1 statement, got {len(statements)}")

    root = statements[0]

    # 2) root must be a SELECT / set-operation (not a DDL/DML/command)
    if type(root).__name__ not in ALLOWED_ROOT_NAMES:
        raise SqlGuardError(f"root is not a SELECT: {type(root).__name__}")

    # 3) no forbidden node types anywhere (catches writing CTEs, SELECT INTO, stacked DDL, COPY)
    for node in root.walk():
        node = node[0] if isinstance(node, tuple) else node
        if type(node).__name__ in FORBIDDEN_NODE_NAMES:
            raise SqlGuardError(f"forbidden node: {type(node).__name__}")

    # 4) table whitelist (allow CTE aliases, reject schema-qualified like pg_catalog.*)
    cte_names = {c.alias_or_name.lower() for c in root.find_all(exp.CTE)}
    for tbl in root.find_all(exp.Table):
        schema = (tbl.text("db") or "").lower()
        if schema and schema != "public":
            raise SqlGuardError(f"schema-qualified table not allowed: {schema}.{tbl.name}")
        name = (tbl.name or "").lower()
        if name not in ALLOWED_TABLES and name not in cte_names:
            raise SqlGuardError(f"table not allowed: {name or '<none>'}")

    # 5) banned functions
    for fn in root.find_all(exp.Func, exp.Anonymous):
        fname = (fn.name or "").lower()
        if fname in BANNED_FUNCS:
            raise SqlGuardError(f"banned function: {fname}")

    # 6) force / clamp LIMIT
    n = max_rows
    limit_node = root.args.get("limit") if hasattr(root, "args") else None
    if limit_node is not None:
        try:
            cur = int(limit_node.expression.name)
            n = min(cur, max_rows)
        except Exception:
            n = max_rows
    root = root.limit(n)

    return root.sql(dialect="postgres")
