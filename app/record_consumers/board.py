"""The board: per source and message type, when it was last heard and what it
last said. It reads the database with a role that can only read.

    GET /             the board as a page
    GET /api/latest   the same as JSON
    GET /healthz, /readyz

Environment:
    SCHEMA_FILE           the output of `bite schema <dictionary>` (required)
    STALE_AFTER_SECONDS   a source not heard for longer is marked stale (default 120)
    REFRESH_SECONDS       the page reloads itself this often; 0 turns it off (default 15)
    PG*                   the database, as libpq reads it
"""
from __future__ import annotations

import os
import sys
from datetime import timezone
from html import escape

import psycopg

from . import http, schema, store

STYLE = """
:root { color-scheme: light dark; --bg: #ffffff; --fg: #1a1a1a; --muted: #595959; --line: #c8c8c8;
        --head: #f0f0f0; --stale-bg: #fff1d6; --stale-fg: #6b3d00; --fresh: #0b6b2f; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #121417; --fg: #e8e8e8; --muted: #a8a8a8; --line: #454a52;
          --head: #1e2227; --stale-bg: #3d2c00; --stale-fg: #ffd58a; --fresh: #7fd99b; } }
* { box-sizing: border-box; }
body { margin: 0; padding: 1rem; background: var(--bg); color: var(--fg);
       font: 1rem/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 72rem; margin: 0 auto; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
h2 { font-size: 1.15rem; margin: 2rem 0 .5rem; }
p { margin: .25rem 0; color: var(--muted); }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
caption { text-align: left; color: var(--muted); padding: .25rem 0; }
th, td { border: 1px solid var(--line); padding: .35rem .6rem; text-align: left; vertical-align: top; white-space: nowrap; }
thead th { background: var(--head); }
tr.stale td, tr.stale th { background: var(--stale-bg); color: var(--stale-fg); }
.state { font-weight: 600; }
tr.fresh .state { color: var(--fresh); }
.unit { color: var(--muted); font-weight: 400; }
tr.stale .unit { color: inherit; }
"""


def entries(messages: dict[str, schema.Message], stale_after: float) -> list[dict]:
    result = []
    for item in store.latest(messages):
        message, row = item["message"], item["row"]
        result.append(
            {
                "site": row["rec_site"],
                "source": row["rec_source"],
                "interface": message.interface,
                "message": message.name,
                "last_heard": row["rec_received_at"].astimezone(timezone.utc).isoformat(timespec="seconds"),
                "captured_at": row["rec_captured_at"].astimezone(timezone.utc).isoformat(timespec="seconds"),
                "age_seconds": round(row["rec_age"], 1),
                "stale": row["rec_age"] > stale_after,
                "records": row["rec_count"],
                "record_version": row["rec_version"],
                "fields": [{"name": f.name, "value": row[f.column], "unit": f.unit} for f in message.fields],
            }
        )
    result.sort(key=lambda e: (e["interface"], e["message"], e["site"], e["source"]))
    return result


def age(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 120:
        return f"{seconds} s ago"
    if seconds < 7200:
        return f"{seconds // 60} min ago"
    return f"{seconds // 3600} h ago"


def shown(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.9g}"
    return str(value)


def page(found: list[dict], stale_after: float, refresh: int) -> str:
    stale = sum(1 for entry in found if entry["stale"])
    parts = [
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<meta http-equiv="refresh" content="{refresh}">' if refresh > 0 else "",
        f"<title>Latest status: {len(found)} rows, {stale} stale</title>",
        f"<style>{STYLE}</style>\n</head>\n<body>\n<main>",
        "<h1>Latest status</h1>",
        f"<p>{len(found)} source and message pairs, {stale} stale. "
        f"Stale means not heard for more than {int(stale_after)} s.</p>",
    ]
    if not found:
        parts.append("<p>No record has been stored yet.</p>")
    groups: dict = {}
    for entry in found:
        groups.setdefault((entry["interface"], entry["message"]), []).append(entry)
    for (interface, message), group in groups.items():
        fields = group[0]["fields"]
        parts.append(f"<h2>{escape(interface)} / {escape(message)}</h2>")
        parts.append('<div class="scroll" role="region" tabindex="0" '
                     f'aria-label="{escape(interface)} {escape(message)}, scrollable">')
        parts.append(f"<table>\n<caption>Newest {escape(message)} record from each source</caption>\n<thead><tr>")
        for heading in ("Site", "Source", "State", "Last heard"):
            parts.append(f'<th scope="col">{heading}</th>')
        for field in fields:
            unit = f' <span class="unit">({escape(field["unit"])})</span>' if field["unit"] and field["unit"] != "1" else ""
            parts.append(f'<th scope="col">{escape(field["name"])}{unit}</th>')
        parts.append("</tr></thead>\n<tbody>")
        for entry in group:
            state = "stale" if entry["stale"] else "fresh"
            parts.append(
                f'<tr class="{state}"><td>{escape(entry["site"])}</td><th scope="row">{escape(entry["source"])}</th>'
                f'<td class="state">{state}</td>'
                f'<td><time datetime="{escape(entry["last_heard"])}">{escape(age(entry["age_seconds"]))}</time></td>'
            )
            for field in entry["fields"]:
                parts.append(f"<td>{escape(shown(field['value']))}</td>")
            parts.append("</tr>")
        parts.append("</tbody>\n</table>\n</div>")
    parts.append("</main>\n</body>\n</html>\n")
    return "\n".join(part for part in parts if part)


def main() -> int:
    path = os.environ.get("SCHEMA_FILE", "")
    if not path:
        print("board: SCHEMA_FILE is not set", file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as file:
        messages = schema.load(file.read())
    stale_after = float(os.environ.get("STALE_AFTER_SECONDS", "120"))
    refresh = int(os.environ.get("REFRESH_SECONDS", "15"))

    def guarded(render):
        def route(_):
            try:
                return render(entries(messages, stale_after))
            except psycopg.Error as error:
                print(f"error: database: {error}", file=sys.stderr, flush=True)
                return 503, "text/plain", "the database did not answer\n"
        return route

    http.serve(
        {
            ("GET", "/"): guarded(lambda found: (200, "text/html", page(found, stale_after, refresh))),
            ("GET", "/api/latest"): guarded(lambda found: http.reply_json(200, {"stale_after_seconds": stale_after, "entries": found})),
            ("GET", "/healthz"): lambda _: (200, "text/plain", "ok\n"),
            ("GET", "/readyz"): lambda _: (200, "text/plain", "ready\n") if store.ping() else (503, "text/plain", "database unreachable\n"),
        },
        "board",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
