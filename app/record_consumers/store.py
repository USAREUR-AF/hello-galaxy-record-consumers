"""PostgreSQL: tables made from the schema, rows written, the latest row read.

The connection settings are libpq's own environment variables (PGHOST, PGPORT,
PGDATABASE, PGUSER, PGPASSWORD, PGSSLMODE), so no credential passes through
this code. One connection is opened per request, which is enough for a
demonstration and is what to replace with a pool under load.
"""
from __future__ import annotations

import time

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from . import schema
from .records import Reading


def connect(attempts: int = 1) -> psycopg.Connection:
    for attempt in range(attempts):
        try:
            return psycopg.connect("", autocommit=True, connect_timeout=5)
        except psycopg.OperationalError:
            if attempt + 1 == attempts:
                raise
            time.sleep(2)
    raise AssertionError("unreachable")


def migrate(messages: dict[str, schema.Message], reader_role: str = "") -> list[str]:
    """Create or extend one table per message; grant reading to `reader_role`.
    Returns the table names."""
    with connect(attempts=30) as connection:
        for message in messages.values():
            for statement in schema.ddl(message):
                connection.execute(statement)
            if reader_role:
                connection.execute(
                    sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(message.table), sql.Identifier(reader_role))
                )
    return sorted(message.table for message in messages.values())


def insert(reading: Reading) -> None:
    fields = [field for field in reading.message.fields if field.name in reading.values]
    columns = ["rec_captured_at", "rec_site", "rec_source", "rec_version"] + [field.column for field in fields]
    values = [reading.captured_at, reading.site, reading.source, reading.version]
    for field in fields:
        value = reading.values[field.name]
        # A text column holds a label or, for a value with no label, the number.
        values.append(str(value) if field.sql_type == "text" and value is not None and not isinstance(value, str) else value)
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(reading.message.table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    with connect() as connection:
        connection.execute(statement, values)


def latest(messages: dict[str, schema.Message]) -> list[dict]:
    """The newest row of every message type from every source, with the
    database's own clock so that age does not depend on this host's."""
    rows = []
    with connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
        for message in messages.values():
            cursor.execute(
                sql.SQL(
                    "SELECT DISTINCT ON (rec_site, rec_source) *, "
                    "EXTRACT(EPOCH FROM now() - rec_received_at)::double precision AS rec_age, "
                    "(SELECT count(*) FROM {table} c WHERE c.rec_site = t.rec_site AND c.rec_source = t.rec_source) AS rec_count "
                    "FROM {table} t ORDER BY rec_site, rec_source, rec_received_at DESC, rec_id DESC"
                ).format(table=sql.Identifier(message.table))
            )
            for row in cursor.fetchall():
                rows.append({"message": message, "row": row})
    return rows


def ping() -> bool:
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False
