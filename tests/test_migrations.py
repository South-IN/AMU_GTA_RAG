from pathlib import Path
import tempfile
import unittest

from amu_admissions_rag.storage import Migration, apply_migrations, discover_migrations

PROJECT_SQL = Path(__file__).resolve().parents[1] / "sql"


class _Result:
    def __init__(self, rows: list[tuple[str, str]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[str, str]]:
        return self._rows


class _Transaction:
    def __init__(self, connection: "_FakeConnection") -> None:
        self.connection = connection

    def __enter__(self) -> None:
        self.connection.statements.append("BEGIN")

    def __exit__(self, *exc_info: object) -> None:
        self.connection.statements.append("COMMIT" if exc_info[0] is None else "ROLLBACK")


class _FakeConnection:
    def __init__(self, applied: dict[str, str] | None = None) -> None:
        self.applied = dict(applied or {})
        self.statements: list[str] = []

    def execute(self, sql: str, params: tuple = ()) -> _Result:
        self.statements.append(" ".join(sql.split()))
        if sql.startswith("SELECT version, checksum"):
            return _Result(list(self.applied.items()))
        if sql.startswith("INSERT INTO schema_migrations"):
            self.applied[params[0]] = params[2]
        return _Result([])

    def transaction(self) -> _Transaction:
        return _Transaction(self)


class MigrationTests(unittest.TestCase):
    def test_project_migrations_are_ordered_and_runner_owns_transactions(self) -> None:
        migrations = discover_migrations(PROJECT_SQL)

        self.assertEqual([m.version for m in migrations][:2], ["001", "002"])
        for migration in migrations:
            statements = {line.strip().upper() for line in migration.sql.splitlines()}
            self.assertNotIn("BEGIN;", statements, migration.name)
            self.assertNotIn("COMMIT;", statements, migration.name)

    def test_pending_migrations_apply_once_in_order_under_lock(self) -> None:
        migrations = [
            Migration("001", "001_a.sql", "CREATE TABLE a ();"),
            Migration("002", "002_b.sql", "CREATE TABLE b ();"),
        ]
        connection = _FakeConnection(applied={"001": migrations[0].checksum})

        applied = apply_migrations(connection, migrations)

        self.assertEqual(applied, ["002_b.sql"])
        self.assertEqual(connection.statements[0], "SELECT pg_advisory_lock(%s)")
        self.assertEqual(connection.statements[-1], "SELECT pg_advisory_unlock(%s)")
        begin = connection.statements.index("BEGIN")
        self.assertEqual(connection.statements[begin + 1], "CREATE TABLE b ();")
        self.assertTrue(connection.statements[begin + 2].startswith("INSERT INTO schema_migrations"))
        self.assertEqual(connection.statements[begin + 3], "COMMIT")
        self.assertNotIn("CREATE TABLE a ();", connection.statements)
        self.assertEqual(apply_migrations(connection, migrations), [])

    def test_modified_applied_migration_is_rejected(self) -> None:
        migration = Migration("001", "001_a.sql", "CREATE TABLE a ();")
        connection = _FakeConnection(applied={"001": "0" * 64})

        with self.assertRaisesRegex(RuntimeError, "has been modified"):
            apply_migrations(connection, [migration])
        self.assertEqual(connection.statements[-1], "SELECT pg_advisory_unlock(%s)")

    def test_badly_named_migration_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "schema.sql").write_text("SELECT 1;", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "001_name.sql"):
                discover_migrations(Path(directory))


if __name__ == "__main__":
    unittest.main()
