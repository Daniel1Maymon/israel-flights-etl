"""
Regression: schema DDL must never run while serving a request.

Production incident (2026-07-25):

    psycopg.errors.DeadlockDetected: deadlock detected
    Process 52181 waits for AccessExclusiveLock on relation 30223; blocked by 52182.
    Process 52182 waits for AccessExclusiveLock on relation 30223; blocked by 52181.

Cause: admin.py called ensure_events_table() on every request. That block runs
`CREATE INDEX IF NOT EXISTS` (ShareLock) and then `ALTER TABLE ... ADD COLUMN IF NOT
EXISTS` (AccessExclusiveLock). Two gunicorn workers serving the dashboard's /metrics and
/events calls concurrently both held ShareLock and both tried to upgrade -- a
lock-upgrade deadlock.

The fix is structural: DDL happens once at startup, serialised by a Postgres advisory
lock. These tests assert the structure, because the deadlock itself needs two real
Postgres backends to reproduce and cannot be triggered against SQLite.
"""
import pytest


class TestRequestHandlersDoNotRunDDL:

    def test_admin_endpoints_do_not_call_ensure_events_table(self, client, monkeypatch):
        """The exact call that caused the incident."""
        calls = []
        import app.services.analytics as analytics
        monkeypatch.setattr(
            analytics, "ensure_events_table", lambda *a, **k: calls.append("ddl")
        )

        # 401 is fine -- the point is that no DDL ran while handling the request.
        client.get("/api/v1/admin/metrics")
        client.get("/api/v1/admin/events")

        assert calls == [], "admin endpoints ran schema DDL on the request path"

    def test_admin_module_no_longer_imports_the_ddl_helper(self):
        """A stale import is how this quietly comes back."""
        import app.api.admin as admin

        assert not hasattr(admin, "ensure_events_table"), (
            "admin.py imports ensure_events_table again -- DDL belongs at startup"
        )

    def test_ai_search_module_no_longer_imports_ddl_helpers(self):
        import app.api.ai_search as ai_search

        for name in ("ensure_tables", "ensure_events_table", "_ensure_ready"):
            assert not hasattr(ai_search, name), (
                f"ai_search.py still exposes {name} -- DDL belongs at startup"
            )

    def test_no_api_module_calls_a_ddl_helper(self):
        """Sweep the whole api package, so a new endpoint cannot reintroduce this."""
        import pathlib

        api_dir = pathlib.Path(__file__).parent.parent / "app" / "api"
        offenders = []
        for path in api_dir.glob("*.py"):
            src = path.read_text(encoding="utf-8")
            for call in ("ensure_events_table(", "ensure_tables(", "run_ddl("):
                if call in src:
                    offenders.append(f"{path.name}: {call}")

        assert not offenders, (
            "DDL called from the api layer: %s. It must run in app.main's lifespan."
            % offenders
        )


class TestDdlIsSerialised:

    def test_run_ddl_takes_an_advisory_lock_on_postgres(self):
        """
        Startup is not enough on its own: four gunicorn workers boot at once and would
        race the same way. The advisory lock makes them queue.
        """
        from app.services import schema_init

        executed = []

        class FakeConn:
            class dialect:
                name = "postgresql"

            def execute(self, stmt, params=None):
                executed.append(("execute", str(stmt), params))

            def exec_driver_sql(self, sql):
                executed.append(("ddl", sql, None))

        class FakeEngine:
            def begin(self):
                conn = FakeConn()
                class Ctx:
                    def __enter__(self): return conn
                    def __exit__(self, *a): return False
                return Ctx()

        schema_init.run_ddl(FakeEngine(), "CREATE TABLE IF NOT EXISTS x (id INT);", label="t")

        assert executed, "no statements executed"
        kind, sql, params = executed[0]
        assert kind == "execute" and "pg_advisory_xact_lock" in sql, (
            "the advisory lock must be taken BEFORE any DDL, or workers can still deadlock"
        )

    def test_run_ddl_skips_the_advisory_lock_on_sqlite(self):
        """pg_advisory_xact_lock does not exist outside Postgres."""
        from app.services import schema_init

        executed = []

        class FakeConn:
            class dialect:
                name = "sqlite"

            def execute(self, stmt, params=None):
                executed.append(("execute", str(stmt)))

            def exec_driver_sql(self, sql):
                executed.append(("ddl", sql))

        class FakeEngine:
            def begin(self):
                conn = FakeConn()
                class Ctx:
                    def __enter__(self): return conn
                    def __exit__(self, *a): return False
                return Ctx()

        schema_init.run_ddl(FakeEngine(), "CREATE TABLE IF NOT EXISTS x (id INT);", label="t")

        assert all(k != "execute" for k, _ in executed)
        assert any(k == "ddl" for k, _ in executed)
