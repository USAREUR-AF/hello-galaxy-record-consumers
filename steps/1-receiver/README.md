# Step 1 — the receiver

**A JSON Schema exported from the dictionary becomes tables; first-bite's
records become rows.** Docker only, no cluster.

first-bite's `rest` sink posts each record as JSON to one URL. The receiver
([`app/record_consumers/receiver.py`](../../app/record_consumers/receiver.py))
is what listens there. It is given one file about the message set, the output
of `bite schema <dictionary>`, and from it:

| It derives | How |
|---|---|
| one table per message | `<interface>__<message>`, lower case: `BUOY/Sea State` is `buoy__sea_state` |
| one column per field | `integer` is `bigint`, `number` is `double precision`, `boolean` is `boolean`; a field with labels is `text` |
| whether a record is valid | the record's `message` is validated against the message's schema; a failure is refused with the field named |
| how to read a version 1 record | version 1 carries every value as text; each is read as the type the schema gives its field |

No message or field name appears in the code. A new dictionary is a new
schema file; a field added to a message is a column added at the next start.
Nothing is ever dropped.

```bash
bin/hello-consumers build
bin/hello-consumers 1-receiver
```

## The two record versions

| | Version 1 | Version 2 |
|---|---|---|
| Written by | first-bite 1.0.x, and later with `FIRST_BITE_RECORD_VERSION=1` | first-bite from release 1.1.0, by default |
| `message` values and ports | text: `"battery_voltage":"12.6"`, `"lamp_on":"false"` | typed: `12.6`, `false` |
| `data_model_version` | null | `"2.0.0"` |
| Sample here | [`samples/records-v1.jsonl`](../../samples/records-v1.jsonl) | [`samples/records-v2.jsonl`](../../samples/records-v2.jsonl) |

The receiver takes both and stores which one a row came from in `rec_version`.
[`samples/README.md`](../../samples/README.md) says how each sample was
recorded. `tools/post-records.py` posts a sample without a decoder; first-bite
is adding `tools/replay-records.py` for the same purpose.

## What you should see

```text
[1] The tests: no database, no network
    $ docker run --rm --network none hello-galaxy-record-consumers:local-test
    │ ..................                                                       [100%]
    │ 18 passed in 2.18s

[2] The schema file is what the dictionary exports
    $ bite schema dictionaries/harbour-buoy | diff - samples/harbour-buoy.schema.json
    │ no difference: 3 messages, 11561 bytes

[3] Start PostgreSQL and the receiver
    The receiver is given one file about the message set: what `bite schema dictionaries/harbour-buoy` printed.
    $ SCHEMA_FILE=samples/harbour-buoy.schema.json python -m record_consumers.receiver
    │ receiver: 3 message types from /schema/harbour-buoy.schema.json; tables: buoy__position, buoy__sea_state, buoy__status
    │ receiver: listening on 0.0.0.0:8080

[4] The tables it made
    $ psql -c '\d buoy__status'
    │                                    Table "public.buoy__status"
    │      Column      |           Type           | Collation | Nullable |           Default
    │ -----------------+--------------------------+-----------+----------+------------------------------
    │  rec_id          | bigint                   |           | not null | generated always as identity
    │  rec_received_at | timestamp with time zone |           | not null | now()
    │  rec_captured_at | timestamp with time zone |           | not null |
    │  rec_site        | text                     |           | not null |
    │  rec_source      | text                     |           | not null |
    │  rec_version     | smallint                 |           | not null |
    │  battery_voltage | double precision         |           |          |
    │  buoy_number     | bigint                   |           |          |
    │  lamp_on         | boolean                  |           |          |
    │  message_id      | bigint                   |           |          |
    │  message_length  | bigint                   |           |          |
    │  mooring_alarm   | boolean                  |           |          |
    │  operating_mode  | text                     |           |          |
    │  position_fix    | boolean                  |           |          |
    │  sequence_number | bigint                   |           |          |
    │  uptime          | bigint                   |           |          |
    │ Indexes:
    │     "buoy__status_pkey" PRIMARY KEY, btree (rec_id)
    │     "buoy__status_source_time" btree (rec_site, rec_source, rec_captured_at DESC)

[5] Post the version 1 sample: every value is text
    $ tools/post-records.py http://receiver:8080/records samples/records-v1.jsonl
    │ 18 posted: 18 x 201

[6] Post the version 2 sample: values keep their type
    $ tools/post-records.py http://receiver:8080/records samples/records-v2.jsonl
    │ 18 posted: 18 x 201

[7] The same row from either version
    $ psql -c 'SELECT rec_version, rec_source, latitude, longitude, drift_speed, antenna_height FROM buoy__position …'
    │  rec_version | rec_site  |         rec_source          |  latitude  |  longitude  | drift_speed | antenna_height
    │ -------------+-----------+-----------------------------+------------+-------------+-------------+----------------
    │            1 | harbour-3 | 198.51.100.10 buoy_number=7 | 44.5012345 | -30.2543210 |        0.35 |           -1.5
    │            2 | harbour-3 | 198.51.100.10 buoy_number=7 | 44.5012345 | -30.2543210 |        0.35 |           -1.5
    │ (2 rows)
    │   message  | count | sources
    │ -----------+-------+---------
    │  position  |    12 |       2
    │  sea_state |    12 |       2
    │  status    |    12 |       2
    │ (3 rows)

[8] Records the receiver does not store
    A value the schema does not allow, a message the dictionary does not define, and a packet that was not decoded.
    $ tools/post-records.py http://receiver:8080/records .run/1-refused.jsonl
    │ 422 {"stored":false,"reason":"battery_voltage: 'flat' is not valid under any of the given schemas"}
    │ 422 {"stored":false,"reason":"no schema for BUOY/Mooring Log"}
    │ 3 posted: 1 x 202, 2 x 422

[9] Verify
    ✓ the tests pass
    ✓ none fails
    ✓ the schema in samples/ and in deploy/base/ is what bite schema prints
    ✓ a scaled field became a double precision column
    ✓ a labelled field became a text column
    ✓ a flag became a boolean column
    ✓ all 18 version 1 records were stored
    ✓ all 18 version 2 records were stored
    ✓ the version 1 row holds the typed position
    ✓ the version 2 row holds the same
    ✓ each table holds 12 rows from 2 sources
    ✓ a value of the wrong type is refused, naming the field
    ✓ a message with no schema is refused
    ✓ an undecoded packet is accepted and not stored

✓ step complete — every assertion held.
```

`rec_site` is the record's `data_source_geo_location`, which the decoder's
deployment sets. `rec_source` is the packet's source address followed by the
message fields named in `SOURCE_FIELDS` (here `buoy_number`), for sources that
share an address.

| Answer | Means |
|---|---|
| 201 | stored |
| 202 | a packet first-bite did not decode; nothing to store |
| 422 | the schema does not allow it; the body says which field |
| 400, 413, 415 | not JSON, over 1 MiB, or not `application/json` |
| 503 | the database did not accept the row; first-bite's sink retries a server error three times |

## Why Python

The receiver is about 300 lines of which the HTTP server is the standard
library's; the two packages it adds are `jsonschema` and `psycopg`, installed
with hashes checked. A reader who operates a cluster and has never written
Rust can read all of it. It handles one request per thread and opens one
database connection per request, which is what to replace first under load.
