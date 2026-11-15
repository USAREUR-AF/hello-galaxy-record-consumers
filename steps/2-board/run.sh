#!/usr/bin/env bash
# Step 2 — the latest-status board: per source and message type, when it was
# last heard and what it last said, with stale sources marked. Docker only.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-consumers.sh"
STALE=20

hc_banner "Step 2 — the latest-status board" "One page, read from the database with a role that can only read."
hc_preflight

hc_step "Start PostgreSQL, the receiver and the board"
hc_cmd "STALE_AFTER_SECONDS=$STALE python -m record_consumers.board        (database role: board)"
hc_stack_up board "$STALE"
hc_note "stale after $STALE s here, so that the step can show a stale source; the default is 120 s"

hc_step "Buoy 3 reports, then falls silent"
grep '"src_ip":\[198,51,100,11\]' "$HC_ROOT/samples/records-v2.jsonl" >"$HC_RUN/2-buoy3.jsonl"
grep '"src_ip":\[198,51,100,10\]' "$HC_ROOT/samples/records-v2.jsonl" >"$HC_RUN/2-buoy7.jsonl"
post() { "$HC_ENGINE" run --rm --network "$HC_NET" --read-only --user 10001:10001 -v "$HC_ROOT:/repo:ro" -v "$HC_RUN:/work:ro" -w /repo "$HC_APP_IMAGE" python tools/post-records.py http://receiver:8080/records "$1" 2>&1; }
hc_cmd "tools/post-records.py http://receiver:8080/records .run/2-buoy3.jsonl"
post /work/2-buoy3.jsonl | hc_show
hc_note "waiting $((STALE + 2)) s"
sleep $((STALE + 2))

hc_step "Buoy 7 reports"
hc_cmd "tools/post-records.py http://receiver:8080/records .run/2-buoy7.jsonl"
post /work/2-buoy7.jsonl | hc_show

hc_step "The board as JSON"
hc_cmd "curl http://board:8080/api/latest"
hc_client python -c '
import json, urllib.request
latest = json.load(urllib.request.urlopen("http://board:8080/api/latest", timeout=10))
for e in latest["entries"]:
    state = "stale" if e["stale"] else "fresh"
    shown = ", ".join("{}={}".format(f["name"], f["value"]) for f in e["fields"] if f["name"] not in ("message_id", "message_length", "buoy_number"))
    print("{interface}/{message} | {site} | {source} | {state} | {records} records | ".format(state=state, **e) + shown)
' >"$HC_RUN/2-latest.txt" 2>&1
cut -c1-190 "$HC_RUN/2-latest.txt" | hc_show
LATEST="$(cat "$HC_RUN/2-latest.txt")"

hc_step "The board as a page"
hc_cmd "curl http://board:8080/"
hc_client python -c '
import urllib.request
response = urllib.request.urlopen("http://board:8080/", timeout=10)
print(response.headers["Content-Type"]); print(response.headers["Content-Security-Policy"])
print(response.read().decode())' >"$HC_RUN/2-board.html" 2>&1
PAGE="$(cat "$HC_RUN/2-board.html")"
grep -E '<title>|<p>|<h2>|<tr class' "$HC_RUN/2-board.html" | cut -c1-200 | hc_show
hc_note "the whole page is in .run/2-board.html; open it in a browser to see it in light and dark"

hc_step "The board's database role can read and nothing else"
hc_cmd "psql -U board -c \"INSERT INTO buoy__status (rec_captured_at, rec_site, rec_source, rec_version) VALUES (now(), 'x', 'x', 2)\""
DENIED="$(hc_sql board "$HC_BOARD_PW" "INSERT INTO buoy__status (rec_captured_at, rec_site, rec_source, rec_version) VALUES (now(), 'x', 'x', 2)")"
printf '%s\n' "$DENIED" | hc_show
hc_cmd "psql -U board -c 'CREATE TABLE mine (x int)'"
DENIED2="$(hc_sql board "$HC_BOARD_PW" "CREATE TABLE mine (x int)")"
printf '%s\n' "$DENIED2" | head -n 1 | hc_show

hc_step "Verify"
hc_assert_contains "six rows: three message types from each of two sources" "$PAGE" "6 source and message pairs, 3 stale"
hc_assert_contains "buoy 3, silent for longer than the limit, is stale" "$LATEST" "BUOY/Status | harbour-3 | 198.51.100.11 buoy_number=3 | stale | 3 records"
hc_assert_contains "buoy 7, just heard, is fresh" "$LATEST" "BUOY/Status | harbour-3 | 198.51.100.10 buoy_number=7 | fresh | 3 records"
hc_assert_contains "the row is the newest record: buoy 7's third Status" "$LATEST" "battery_voltage=12.54, lamp_on=False, mooring_alarm=True, operating_mode=Reporting"
hc_assert_contains "the page says stale in words, not only in colour" "$PAGE" '<td class="state">stale</td>'
hc_assert_contains "the page declares its language and follows the reader's light or dark setting" "$PAGE" "prefers-color-scheme: dark"
hc_assert_contains "the page allows no script" "$PAGE" "default-src 'none'; style-src 'unsafe-inline'"
hc_assert_contains "the board's role may not write a row" "$DENIED" "permission denied for table buoy__status"
hc_assert_contains "nor create a table" "$DENIED2" "permission denied for schema public"
hc_done
