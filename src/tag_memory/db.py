"""Tag-based Memory System — DB connection pool & migrations."""

from __future__ import annotations

import pymysql
from pymysql.cursors import DictCursor

from .schema import SCHEMA_SQL


def create_pool(
    host: str = "localhost",
    port: int = 3306,
    user: str = "root",
    password: str = "",
    database: str = "tag_memory",
    autocommit: bool = True,
) -> pymysql.Connection:
    """Create a MySQL connection and run migrations."""
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        cursorclass=DictCursor,
        autocommit=autocommit,
        charset="utf8mb4",
    )
    _migrate(conn)
    return conn


def _migrate(conn: pymysql.Connection) -> None:
    """Idempotent schema migration."""
    with conn.cursor() as cur:
        for statement in _split_statements(SCHEMA_SQL):
            cur.execute(statement)


def _split_statements(sql: str) -> list[str]:
    """Split multi-statement SQL string by semicolons."""
    statements = []
    for stmt in sql.split(";"):
        stripped = stmt.strip()
        if stripped and not stripped.startswith("--"):
            statements.append(stripped)
    return statements
