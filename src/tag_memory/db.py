"""Tag-based Memory System — DB connection pool & migrations."""

from __future__ import annotations

import pymysql
from pymysql.cursors import DictCursor

from .config import MySQLConfig
from .schema import SCHEMA_SQL


def create_pool(
    host: str = "",
    port: int = 0,
    user: str = "",
    password: str = "",
    database: str = "",
    autocommit: bool = True,
) -> pymysql.Connection:
    """Create a MySQL connection and run migrations.

    All params default to TAG_MEMORY_MYSQL_* env vars or .env values.
    """
    cfg = MySQLConfig.from_env()

    conn = pymysql.connect(
        host=host or cfg.host,
        port=port or cfg.port,
        user=user or cfg.user,
        password=password if password else cfg.password,
        database=database or cfg.database,
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
