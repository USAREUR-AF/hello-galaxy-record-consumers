"""Reading one first-bite record: both record versions, one result.

The record is described in first-bite's docs/record.md. Version 2 carries
typed values, numeric ports and `data_model_version` "2.0.0". Version 1
carries every value and both ports as text and no model version.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from . import schema


class Refused(Exception):
    """The record cannot be stored; the text says why."""


@dataclass(frozen=True)
class Reading:
    message: schema.Message
    values: dict  # typed, valid against the schema
    captured_at: datetime
    site: str
    source: str
    version: int  # 1 or 2


def version(record: dict) -> int:
    model = record.get("data_model_version")
    if isinstance(model, str) and model.split(".")[0].isdigit() and int(model.split(".")[0]) >= 2:
        return 2
    return 1


def _address(value) -> str:
    if isinstance(value, list) and len(value) == 4 and all(isinstance(b, int) and 0 <= b <= 255 for b in value):
        return ".".join(str(b) for b in value)
    if isinstance(value, list) and len(value) == 16 and all(isinstance(b, int) and 0 <= b <= 255 for b in value):
        return ":".join(f"{value[i] << 8 | value[i + 1]:x}" for i in range(0, 16, 2))
    raise Refused("src_ip is not an address of 4 or 16 bytes")


def read(record, messages: dict[str, schema.Message], source_fields: tuple = ()) -> Reading | None:
    """A record as something to store, `None` for a packet first-bite did not
    decode, or `Refused`. `source_fields` names message fields that tell one
    source from another behind the same address, such as a unit number."""
    if not isinstance(record, dict):
        raise Refused("the body is not a JSON object")
    interface, name, values = record.get("subsystem"), record.get("message_type"), record.get("message")
    if interface is None or values is None:
        return None
    if not isinstance(interface, str) or not isinstance(name, str) or not isinstance(values, dict):
        raise Refused("subsystem and message_type must be text and message an object")
    message = messages.get(f"{interface}/{name}")
    if message is None:
        raise Refused(f"no schema for {interface}/{name}")
    stamp = record.get("timestamp")
    try:
        captured_at = datetime.fromtimestamp(
            int(stamp["secs_since_epoch"]) + int(stamp["nanos_since_epoch"]) / 1e9, tz=timezone.utc
        )
    except (TypeError, KeyError, ValueError, OverflowError, OSError):
        raise Refused("timestamp is not {secs_since_epoch, nanos_since_epoch}") from None
    values = schema.typed(message, values)
    found = schema.problems(message, values)
    if found:
        raise Refused("; ".join(found[:5]))
    source = _address(record.get("src_ip"))
    for field in source_fields:
        if values.get(field) is not None:
            source += f" {field}={values[field]}"
    site = record.get("data_source_geo_location")
    return Reading(message, values, captured_at, site if isinstance(site, str) and site else "unknown", source, version(record))
