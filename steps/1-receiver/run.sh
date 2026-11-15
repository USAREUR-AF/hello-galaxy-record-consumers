#!/usr/bin/env bash
# Step 1 — the receiver: tables made from the dictionary's schema, records of
# both versions stored, a record the schema does not allow refused. Docker only.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-consumers.sh"

hc_banner "Step 1 — the receiver" "A JSON Schema from the dictionary becomes tables; first-bite's records become rows."
hc_preflight

hc_step "The tests: no database, no network"
hc_cmd "docker run --rm --network none hello-galaxy-record-consumers:local-test"
TESTS="$("$HC_ENGINE" run --rm --network none --read-only --tmpfs /tmp "$HC_TEST_IMAGE" 2>&1)"
printf '%s\n' "$TESTS" | tail -n 2 | hc_show

hc_step "The schema file is what the dictionary exports"
hc_cmd "bite schema dictionaries/harbour-buoy | diff - samples/harbour-buoy.schema.json"
"$HC_ENGINE" run --rm --network none --entrypoint bite "$HC_EDGE_IMAGE" schema /dictionary >"$HC_RUN/1-schema.json" 2>&1
SCHEMA_DIFF="$(diff "$HC_RUN/1-schema.json" "$HC_ROOT/samples/harbour-buoy.schema.json" 2>&1 && diff "$HC_RUN/1-schema.json" "$HC_ROOT/deploy/base/harbour-buoy.schema.json" 2>&1 && echo "no difference: 3 messages, $(wc -c <"$HC_RUN/1-schema.json" | tr -d ' ') bytes")"
printf '%s\n' "$SCHEMA_DIFF" | head -n 5 | hc_show

hc_step "Start PostgreSQL and the receiver"
hc_say "The receiver is given one file about the message set: what \`bite schema dictionaries/harbour-buoy\` printed."
hc_cmd "SCHEMA_FILE=samples/harbour-buoy.schema.json python -m record_consumers.receiver"
hc_stack_up
"$HC_ENGINE" logs hc-receiver 2>&1 | grep '^receiver:' | hc_show

hc_step "The tables it made"
hc_cmd "psql -c '\\d buoy__status'"
TABLE="$(hc_sql receiver "$HC_RECEIVER_PW" '\d buoy__status')"
printf '%s\n' "$TABLE" | sed -n '1,22p' | hc_show

hc_step "Post the version 1 sample: every value is text"
hc_cmd "tools/post-records.py http://receiver:8080/records samples/records-v1.jsonl"
POST1="$(hc_client python tools/post-records.py http://receiver:8080/records samples/records-v1.jsonl 2>&1)"
printf '%s\n' "$POST1" | hc_show

hc_step "Post the version 2 sample: values keep their type"
hc_cmd "tools/post-records.py http://receiver:8080/records samples/records-v2.jsonl"
POST2="$(hc_client python tools/post-records.py http://receiver:8080/records samples/records-v2.jsonl 2>&1)"
printf '%s\n' "$POST2" | hc_show

hc_step "The same row from either version"
hc_cmd "psql -c 'SELECT rec_version, rec_source, latitude, longitude, drift_speed, antenna_height FROM buoy__position …'"
ROWS="$(hc_sql receiver "$HC_RECEIVER_PW" "SELECT rec_version, rec_site, rec_source, round(latitude::numeric, 7) AS latitude, round(longitude::numeric, 7) AS longitude, round(drift_speed::numeric, 2) AS drift_speed, antenna_height FROM buoy__position WHERE sequence_number = 104 ORDER BY rec_version")"
printf '%s\n' "$ROWS" | hc_show
COUNTS="$(hc_sql receiver "$HC_RECEIVER_PW" "SELECT 'status' AS message, count(*), count(DISTINCT rec_source) AS sources FROM buoy__status UNION ALL SELECT 'sea_state', count(*), count(DISTINCT rec_source) FROM buoy__sea_state UNION ALL SELECT 'position', count(*), count(DISTINCT rec_source) FROM buoy__position ORDER BY 1")"
printf '%s\n' "$COUNTS" | hc_show

hc_step "Records the receiver does not store"
hc_say "A value the schema does not allow, a message the dictionary does not define, and a packet that was not decoded."
printf '%s\n' \
  "$(sed -n 1p "$HC_ROOT/samples/records-v2.jsonl" | sed 's/"battery_voltage":[0-9.]*/"battery_voltage":"flat"/')" \
  "$(sed -n 1p "$HC_ROOT/samples/records-v2.jsonl" | sed 's/"message_type":"Status"/"message_type":"Mooring Log"/')" \
  "$(sed -n 1p "$HC_ROOT/samples/records-v2.jsonl" | sed 's/"subsystem":"BUOY"/"subsystem":null/; s/"message":{[^}]*}/"message":null/')" \
  >"$HC_RUN/1-refused.jsonl"
hc_cmd "tools/post-records.py http://receiver:8080/records .run/1-refused.jsonl"
REFUSED="$("$HC_ENGINE" run --rm --network "$HC_NET" --read-only --user 10001:10001 -v "$HC_ROOT:/repo:ro" -v "$HC_RUN:/work:ro" -w /repo "$HC_APP_IMAGE" python tools/post-records.py http://receiver:8080/records /work/1-refused.jsonl 2>&1)"
printf '%s\n' "$REFUSED" | hc_show

hc_step "Verify"
hc_assert_contains "the tests pass" "$TESTS" " passed"
hc_assert_lacks "none fails" "$TESTS" "failed"
hc_assert_contains "the schema in samples/ and in deploy/base/ is what bite schema prints" "$SCHEMA_DIFF" "no difference"
hc_assert_contains "a scaled field became a double precision column" "$TABLE" "battery_voltage | double precision"
hc_assert_contains "a labelled field became a text column" "$TABLE" "operating_mode  | text"
hc_assert_contains "a flag became a boolean column" "$TABLE" "lamp_on         | boolean"
hc_assert_contains "all 18 version 1 records were stored" "$POST1" "18 posted: 18 x 201"
hc_assert_contains "all 18 version 2 records were stored" "$POST2" "18 posted: 18 x 201"
hc_assert_contains "the version 1 row holds the typed position" "$ROWS" "1 | harbour-3 | 198.51.100.10 buoy_number=7 | 44.5012345 | -30.2543210 |        0.35 |           -1.5"
hc_assert_contains "the version 2 row holds the same" "$ROWS" "2 | harbour-3 | 198.51.100.10 buoy_number=7 | 44.5012345 | -30.2543210 |        0.35 |           -1.5"
hc_assert_contains "each table holds 12 rows from 2 sources" "$COUNTS" "position  |    12 |       2"
hc_assert_contains "a value of the wrong type is refused, naming the field" "$REFUSED" "422 {\"stored\":false,\"reason\":\"battery_voltage:"
hc_assert_contains "a message with no schema is refused" "$REFUSED" "no schema for BUOY/Mooring Log"
hc_assert_contains "an undecoded packet is accepted and not stored" "$REFUSED" "3 posted: 1 x 202, 2 x 422"
hc_done
