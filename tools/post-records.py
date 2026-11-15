#!/usr/bin/env python3
"""Post recorded first-bite records to a receiver, one per line of a file.

    tools/post-records.py http://127.0.0.1:8080/records samples/records-v1.jsonl

Stands in for the decoder when you have none running. Prints the HTTP status
of each record and a count; exit status 1 if any was not 201 or 202.
"""
import sys
import urllib.error
import urllib.request

url, path = sys.argv[1], sys.argv[2]
statuses = []
for line in open(path, encoding="utf-8"):
    request = urllib.request.Request(url, line.encode("utf-8"), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            statuses.append(response.status)
    except urllib.error.HTTPError as error:
        statuses.append(error.code)
        print(f"{error.code} {error.read().decode('utf-8', 'replace').strip()}")
print(f"{len(statuses)} posted: " + ", ".join(f"{statuses.count(s)} x {s}" for s in sorted(set(statuses))))
sys.exit(0 if all(status in (201, 202) for status in statuses) else 1)
