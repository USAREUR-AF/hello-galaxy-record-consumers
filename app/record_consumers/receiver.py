"""The receiver: first-bite's `rest` sink posts each record here.

    POST /records    one record as JSON
    GET  /healthz    the process is up
    GET  /readyz     the tables exist and the database answers

Environment:
    SCHEMA_FILE     the output of `bite schema <dictionary>` (required)
    SOURCE_FIELDS   message fields that tell sources apart behind one address, comma-separated
    READER_ROLE     database role granted SELECT on every table the receiver makes
    PG*             the database, as libpq reads it
"""
from __future__ import annotations

import json
import os
import sys

import psycopg

from . import http, records, schema, store


def main() -> int:
    path = os.environ.get("SCHEMA_FILE", "")
    if not path:
        print("receiver: SCHEMA_FILE is not set", file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as file:
        messages = schema.load(file.read())
    source_fields = tuple(name for name in os.environ.get("SOURCE_FIELDS", "").split(",") if name)
    tables = store.migrate(messages, os.environ.get("READER_ROLE", ""))
    print(f"receiver: {len(messages)} message types from {path}; tables: {', '.join(tables)}", flush=True)

    def post_record(handler: http.Handler) -> tuple:
        if handler.headers.get_content_type() != "application/json":
            return http.reply_json(415, {"stored": False, "reason": "send the record as application/json"})
        body = handler.body()
        if body is None:
            return http.reply_json(413, {"stored": False, "reason": f"a body of at most {http.MAX_BODY_BYTES} bytes with a Content-Length is required"})
        try:
            record = json.loads(body)
        except (ValueError, RecursionError):
            return http.reply_json(400, {"stored": False, "reason": "the body is not JSON"})
        try:
            reading = records.read(record, messages, source_fields)
        except records.Refused as refusal:
            print(f"refused: {refusal}", flush=True)
            return http.reply_json(422, {"stored": False, "reason": str(refusal)})
        if reading is None:
            return http.reply_json(202, {"stored": False, "reason": "the packet was not decoded; nothing to store"})
        try:
            store.insert(reading)
        except psycopg.Error as error:
            print(f"error: database: {error}", file=sys.stderr, flush=True)
            return http.reply_json(503, {"stored": False, "reason": "the database did not accept the row"})
        return http.reply_json(201, {"stored": True, "table": reading.message.table, "record_version": reading.version})

    http.serve(
        {
            ("POST", "/records"): post_record,
            ("GET", "/healthz"): lambda _: (200, "text/plain", "ok\n"),
            ("GET", "/readyz"): lambda _: (200, "text/plain", "ready\n") if store.ping() else (503, "text/plain", "database unreachable\n"),
        },
        "receiver",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
