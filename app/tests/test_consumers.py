"""Tests that need no database: the schema becomes tables, both record
versions become the same row, and the board renders what it is given."""
import json
from pathlib import Path

import pytest

from record_consumers import board, records, schema

# samples/ of the repository; beside tests/ in the test image.
ROOT = next(p / "samples" for p in Path(__file__).resolve().parents if (p / "samples").is_dir())
SCHEMA = (ROOT / "harbour-buoy.schema.json").read_text(encoding="utf-8")
V1 = [json.loads(line) for line in (ROOT / "records-v1.jsonl").read_text(encoding="utf-8").splitlines()]
V2 = [json.loads(line) for line in (ROOT / "records-v2.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def messages():
    return schema.load(SCHEMA)


def test_every_message_of_the_schema_gets_a_table(messages):
    assert sorted(m.table for m in messages.values()) == ["buoy__position", "buoy__sea_state", "buoy__status"]


def test_column_types_follow_the_schema(messages):
    types = {f.name: f.sql_type for f in messages["BUOY/Status"].fields}
    assert types["uptime"] == "bigint"  # an integer field
    assert types["battery_voltage"] == "double precision"  # a scaled field
    assert types["lamp_on"] == "boolean"
    assert types["operating_mode"] == "text"  # a field with labels
    assert {f.name: f.unit for f in messages["BUOY/Sea State"].fields}["wind_speed"] == "m/s"


def test_ddl_creates_then_only_adds(messages):
    statements = schema.ddl(messages["BUOY/Position"])
    assert statements[0].startswith('CREATE TABLE IF NOT EXISTS "buoy__position"')
    assert 'ALTER TABLE "buoy__position" ADD COLUMN IF NOT EXISTS "latitude" double precision' in statements
    assert not any("DROP" in statement for statement in statements)


def test_names_that_are_not_identifiers_are_made_into_identifiers():
    assert schema.identifier("Sea State") == "sea_state"
    assert schema.identifier("CO2 (ppm)") == "co2_ppm"
    assert schema.identifier("3D Fix") == "n_3d_fix"
    with pytest.raises(ValueError):
        schema.identifier("--")


def test_a_schema_whose_names_collide_is_refused():
    one = {"type": "object", "properties": {}}
    with pytest.raises(ValueError, match="same table"):
        schema.load(json.dumps({"A/Sea State": one, "A/sea-state": one}))


def test_both_samples_hold_the_same_eighteen_records():
    assert len(V1) == len(V2) == 18
    assert {records.version(r) for r in V1} == {1}
    assert {records.version(r) for r in V2} == {2}


def test_a_version_1_record_and_a_version_2_record_give_the_same_values(messages):
    for text, typed in zip(V1, V2):
        one = records.read(text, messages, ("buoy_number",))
        two = records.read(typed, messages, ("buoy_number",))
        assert (one.version, two.version) == (1, 2)
        assert one.message.key == two.message.key
        assert one.captured_at == two.captured_at
        assert one.source == two.source
        assert one.values.keys() == two.values.keys()
        for name, value in two.values.items():
            if isinstance(value, float):
                assert one.values[name] == pytest.approx(value, rel=1e-9), name
            else:
                assert one.values[name] == value, name


def test_what_a_record_says_about_its_source(messages):
    reading = records.read(V1[0], messages, ("buoy_number",))
    assert reading.site == "harbour-3"
    assert reading.source == "198.51.100.10 buoy_number=7"
    assert reading.captured_at.isoformat() == "2025-06-15T15:06:40+00:00"
    assert records.read(V1[1], messages, ("buoy_number",)).source == "198.51.100.11 buoy_number=3"


def test_a_packet_that_was_not_decoded_is_not_an_error(messages):
    record = dict(V1[0], subsystem=None, message_type=None, message=None)
    assert records.read(record, messages) is None


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"message_type": "Mooring Log"}, "no schema for BUOY/Mooring Log"),
        ({"message": {"battery_voltage": "twelve"}}, "battery_voltage"),
        ({"message": {"unheard_of": 1}}, "unheard_of"),
        ({"timestamp": "noon"}, "timestamp"),
        ({"src_ip": [1, 2, 3]}, "src_ip"),
    ],
)
def test_a_record_the_schema_does_not_allow_is_refused_with_the_reason(messages, change, reason):
    with pytest.raises(records.Refused, match=reason):
        records.read(dict(V2[0], **change), messages)


def test_a_body_that_is_not_an_object_is_refused(messages):
    with pytest.raises(records.Refused):
        records.read(["not", "a", "record"], messages)


def entry(**changes):
    base = {
        "site": "harbour-3", "source": "198.51.100.10 buoy_number=7", "interface": "BUOY", "message": "Status",
        "last_heard": "2026-01-01T00:00:00+00:00", "captured_at": "2026-01-01T00:00:00+00:00",
        "age_seconds": 4.0, "stale": False, "records": 3, "record_version": 2,
        "fields": [{"name": "battery_voltage", "value": 12.6, "unit": "V"}, {"name": "lamp_on", "value": True, "unit": None}],
    }
    return dict(base, **changes)


def test_the_page_marks_stale_rows_in_words_not_only_colour():
    html = board.page([entry(), entry(source="<b>x</b>", stale=True, age_seconds=600)], 120, 15)
    assert '<tr class="fresh">' in html and '<td class="state">fresh</td>' in html
    assert '<tr class="stale">' in html and '<td class="state">stale</td>' in html
    assert "2 source and message pairs, 1 stale" in html
    assert "10 min ago" in html
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html  # values are escaped
    assert '<html lang="en">' in html and "<caption>" in html and 'scope="col"' in html and 'scope="row"' in html
    assert "prefers-color-scheme: dark" in html
    assert '<meta http-equiv="refresh" content="15">' in html
    assert "<script" not in html


def test_the_page_says_so_when_nothing_is_stored_and_can_stop_reloading():
    html = board.page([], 120, 0)
    assert "No record has been stored yet." in html
    assert "http-equiv" not in html


def test_ages_and_values_as_shown():
    assert [board.age(s) for s in (4, 119, 120, 7199, 7200)] == ["4 s ago", "119 s ago", "2 min ago", "119 min ago", "2 h ago"]
    assert [board.shown(v) for v in (None, True, 44.501234499999995, "Reporting", 7)] == ["—", "true", "44.5012345", "Reporting", "7"]
