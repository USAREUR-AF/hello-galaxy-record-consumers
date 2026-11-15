#!/usr/bin/env python3
"""Turn the file `mind --output` writes into one record per line.

    tools/log-to-jsonl.py completelog_<time>.log > records.jsonl

`mind --output` writes each record pretty-printed, one after another. This
prints each as one line of compact JSON, which tools/post-records.py reads.
"""
import json
import sys

text = open(sys.argv[1], encoding="utf-8").read()
decoder, at = json.JSONDecoder(), 0
while at < len(text):
    if text[at].isspace():
        at += 1
        continue
    record, at = decoder.raw_decode(text, at)
    print(json.dumps(record, separators=(",", ":")))
