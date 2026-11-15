"""What the receiver knows about a message set, all of it read from the JSON
Schema that `bite schema <dictionary>` prints: which messages exist, the
table and columns of each, how to read a version 1 record's text values, and
whether a record's `message` is valid.

Nothing in this module names a message or a field. A new dictionary means a
new schema file and no change here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from jsonschema import Draft202012Validator

# Columns every message table has, before the message's own fields.
COMMON_COLUMNS = (
    ("rec_id", "bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY"),
    ("rec_received_at", "timestamptz NOT NULL DEFAULT now()"),
    ("rec_captured_at", "timestamptz NOT NULL"),
    ("rec_site", "text NOT NULL"),
    ("rec_source", "text NOT NULL"),
    ("rec_version", "smallint NOT NULL"),
)


def identifier(text: str) -> str:
    """A PostgreSQL identifier made from a dictionary name: lower case, with
    every run of other characters one underscore. `Sea State` is `sea_state`."""
    name = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if not name:
        raise ValueError(f"{text!r} has no letter or digit to make a name from")
    return name if name[0].isalpha() else f"n_{name}"


@dataclass(frozen=True)
class Field:
    name: str  # as in the record
    column: str  # as in the table
    sql_type: str
    json_types: frozenset  # of "integer", "number", "boolean", "string"
    labels: frozenset  # the labels of an enumerated field
    unit: str | None


@dataclass(frozen=True)
class Message:
    key: str  # "<interface>/<message>", as `bite schema` keys it
    interface: str
    name: str
    table: str
    fields: tuple
    validator: Draft202012Validator


def _field(name: str, definition: dict) -> Field:
    json_types, labels = set(), set()
    for branch in definition.get("anyOf", [definition]):
        if "enum" in branch:
            labels.update(value for value in branch["enum"] if isinstance(value, str))
        kind = branch.get("type")
        if kind in ("integer", "number", "boolean", "string"):
            json_types.add(kind)
    # A field with labels holds a label or, for a value with none, the number:
    # text holds both. Otherwise the column takes the field's own type.
    if labels or "string" in json_types or len(json_types) != 1:
        sql_type = "text"
    else:
        sql_type = {"integer": "bigint", "number": "double precision", "boolean": "boolean"}[next(iter(json_types))]
    column = identifier(name)
    if column.startswith("rec_"):
        column = f"f_{column}"
    return Field(name, column, sql_type, frozenset(json_types), frozenset(labels), definition.get("x-unit"))


def load(text: str) -> dict[str, Message]:
    """The messages of a schema file, by `<interface>/<message>`."""
    messages = {}
    for key, definition in json.loads(text).items():
        interface, _, name = key.partition("/")
        Draft202012Validator.check_schema(definition)
        fields = tuple(_field(n, d) for n, d in sorted(definition.get("properties", {}).items()))
        columns = [field.column for field in fields]
        if len(set(columns)) != len(columns):
            raise ValueError(f"{key}: two fields give the same column name")
        messages[key] = Message(
            key, interface, name, f"{identifier(interface)}__{identifier(name)}", fields, Draft202012Validator(definition)
        )
    tables = [message.table for message in messages.values()]
    if len(set(tables)) != len(tables):
        raise ValueError("two messages give the same table name")
    return messages


def ddl(message: Message) -> list[str]:
    """Statements that create the message's table, or add to an existing one
    the columns of fields a newer dictionary added. Nothing is dropped."""
    columns = ",\n  ".join(f'"{name}" {kind}' for name, kind in COMMON_COLUMNS)
    statements = [f'CREATE TABLE IF NOT EXISTS "{message.table}" (\n  {columns}\n)']
    for field in message.fields:
        statements.append(f'ALTER TABLE "{message.table}" ADD COLUMN IF NOT EXISTS "{field.column}" {field.sql_type}')
    statements.append(
        f'CREATE INDEX IF NOT EXISTS "{message.table}_source_time" '
        f'ON "{message.table}" ("rec_site", "rec_source", "rec_captured_at" DESC)'
    )
    return statements


def typed(message: Message, values: dict) -> dict:
    """The `message` object with typed values. A version 2 record already has
    them and comes back unchanged. A version 1 record carries every value as
    text; each is read as the type the schema gives its field. A label stays
    a label, and text that is not what the schema expects is left as it is,
    for validation to refuse."""
    by_name = {field.name: field for field in message.fields}
    result = {}
    for name, value in values.items():
        field = by_name.get(name)
        if field is None or not isinstance(value, str) or value in field.labels:
            result[name] = value
        elif "boolean" in field.json_types and value in ("true", "false"):
            result[name] = value == "true"
        elif "integer" in field.json_types and re.fullmatch(r"-?[0-9]+", value):
            result[name] = int(value)
        elif "number" in field.json_types:
            try:
                result[name] = float(value)
            except ValueError:
                result[name] = value
        else:
            result[name] = value
    return result


def problems(message: Message, values: dict) -> list[str]:
    """Why `values` is not a valid `message` of this type; empty when it is."""
    return [
        f"{'/'.join(str(part) for part in error.path) or 'message'}: {error.message}"
        for error in sorted(message.validator.iter_errors(values), key=lambda e: list(e.path))
    ]
