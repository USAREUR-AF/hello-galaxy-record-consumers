# Step 2 — the latest-status board

**Per source and per message type: when it was last heard, what it last said,
and whether it has gone quiet.** Docker only, no cluster.

The board ([`app/record_consumers/board.py`](../../app/record_consumers/board.py))
reads the tables the receiver made, with a database role that can only read.
It serves one page at `/` and the same content as JSON at `/api/latest`.

| | |
|---|---|
| One row is | the newest record of one message type from one source at one site |
| Last heard | when the receiver stored that record, by the database's clock |
| Stale | not heard for longer than `STALE_AFTER_SECONDS` (default 120) |
| The page | rendered by the server; no script, and a Content-Security-Policy that allows none; reloads itself every `REFRESH_SECONDS` |
| Accessibility | a caption and header cells on every table, `stale` and `fresh` written as words as well as coloured, colours for light and dark taken from the reader's setting, wide tables scroll inside a focusable region |

```bash
bin/hello-consumers 2-board
```

The step posts buoy 3's records, waits past the stale limit (20 s for the
step), posts buoy 7's, and reads the board.

## What you should see

```text
[1] Start PostgreSQL, the receiver and the board
    $ STALE_AFTER_SECONDS=20 python -m record_consumers.board        (database role: board)
    stale after 20 s here, so that the step can show a stale source; the default is 120 s

[2] Buoy 3 reports, then falls silent
    $ tools/post-records.py http://receiver:8080/records .run/2-buoy3.jsonl
    │ 9 posted: 9 x 201
    waiting 22 s

[3] Buoy 7 reports
    $ tools/post-records.py http://receiver:8080/records .run/2-buoy7.jsonl
    │ 9 posted: 9 x 201

[4] The board as JSON
    $ curl http://board:8080/api/latest
    │ BUOY/Position | harbour-3 | 198.51.100.10 buoy_number=7 | fresh | 3 records | antenna_height=-1.3, drift_course=135, drift_speed=0.45, latitude=44.5009345, longitude=-30.253901, satellites_i
    │ BUOY/Position | harbour-3 | 198.51.100.11 buoy_number=3 | stale | 3 records | antenna_height=-1.1, drift_course=135, drift_speed=0.55, latitude=44.5006345, longitude=-30.253481, satellites_i
    │ BUOY/Sea State | harbour-3 | 198.51.100.10 buoy_number=7 | fresh | 3 records | air_pressure=1002.4, sequence_number=114, significant_wave_height=2.49, water_temperature=-0.45, wave_period=9.
    │ BUOY/Sea State | harbour-3 | 198.51.100.11 buoy_number=3 | stale | 3 records | air_pressure=1001.6, sequence_number=115, significant_wave_height=2.63, water_temperature=0.35, wave_period=10.
    │ BUOY/Status | harbour-3 | 198.51.100.10 buoy_number=7 | fresh | 3 records | battery_voltage=12.54, lamp_on=False, mooring_alarm=True, operating_mode=Reporting, position_fix=True, sequence_nu
    │ BUOY/Status | harbour-3 | 198.51.100.11 buoy_number=3 | stale | 3 records | battery_voltage=12.48, lamp_on=False, mooring_alarm=False, operating_mode=Reporting, position_fix=True, sequence_n

[5] The board as a page
    $ curl http://board:8080/
    │ <title>Latest status: 6 rows, 3 stale</title>
    │ <p>6 source and message pairs, 3 stale. Stale means not heard for more than 20 s.</p>
    │ <h2>BUOY / Position</h2>
    │ <tr class="fresh"><td>harbour-3</td><th scope="row">198.51.100.10 buoy_number=7</th><td class="state">fresh</td><td><time datetime="2026-11-15T19:49:42+00:00">3 s ago</time></td>
    │ <tr class="stale"><td>harbour-3</td><th scope="row">198.51.100.11 buoy_number=3</th><td class="state">stale</td><td><time datetime="2026-11-15T19:49:18+00:00">27 s ago</time></td>
    │ <h2>BUOY / Sea State</h2>
    │ <tr class="fresh"><td>harbour-3</td><th scope="row">198.51.100.10 buoy_number=7</th><td class="state">fresh</td><td><time datetime="2026-11-15T19:49:42+00:00">3 s ago</time></td>
    │ <tr class="stale"><td>harbour-3</td><th scope="row">198.51.100.11 buoy_number=3</th><td class="state">stale</td><td><time datetime="2026-11-15T19:49:18+00:00">27 s ago</time></td>
    │ <h2>BUOY / Status</h2>
    │ <tr class="fresh"><td>harbour-3</td><th scope="row">198.51.100.10 buoy_number=7</th><td class="state">fresh</td><td><time datetime="2026-11-15T19:49:42+00:00">3 s ago</time></td>
    │ <tr class="stale"><td>harbour-3</td><th scope="row">198.51.100.11 buoy_number=3</th><td class="state">stale</td><td><time datetime="2026-11-15T19:49:18+00:00">27 s ago</time></td>
    the whole page is in .run/2-board.html; open it in a browser to see it in light and dark

[6] The board's database role can read and nothing else
    $ psql -U board -c "INSERT INTO buoy__status (rec_captured_at, rec_site, rec_source, rec_version) VALUES (now(), 'x', 'x', 2)"
    │ ERROR:  permission denied for table buoy__status
    $ psql -U board -c 'CREATE TABLE mine (x int)'
    │ ERROR:  permission denied for schema public

[7] Verify
    ✓ six rows: three message types from each of two sources
    ✓ buoy 3, silent for longer than the limit, is stale
    ✓ buoy 7, just heard, is fresh
    ✓ the row is the newest record: buoy 7's third Status
    ✓ the page says stale in words, not only in colour
    ✓ the page declares its language and follows the reader's light or dark setting
    ✓ the page allows no script
    ✓ the board's role may not write a row
    ✓ nor create a table

✓ step complete — every assertion held.
```

The whole page is written to `.run/2-board.html`; open it in a browser to see
it, and switch the system between light and dark to see both.

## Two roles

| Role | May | Made by |
|---|---|---|
| `receiver` | create tables in the `records` database and write rows | [`init-roles.sh`](../../deploy/overlays/local/postgres/init-roles.sh), once, when the database is first made |
| `board` | read the tables the receiver granted it | the same script; the receiver runs `GRANT SELECT` on each table it makes |

The board cannot change what it shows. A third reader of the data would get a
role of its own, granted by whoever owns the data, the same way.
