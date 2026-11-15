# Samples

Everything here is synthetic: two simulated harbour buoys, the interface of
which is the invented document in
[hello-galaxy-first-bite](https://github.com/USAREUR-AF/hello-galaxy-first-bite/blob/main/icd/HB-ICD-001-A.md).

| File | What | Made by |
|---|---|---|
| [`../examples/harbour-buoys.pcap`](../examples/harbour-buoys.pcap) | 18 UDP datagrams: buoy 7 from 198.51.100.10 and buoy 3 from 198.51.100.11, three rounds of Status, Sea State and Position each | `tools/make-sample-pcap.py examples/harbour-buoys.pcap`; the same bytes every time |
| `harbour-buoy.schema.json` | the JSON Schema of each message | `bite schema dictionaries/harbour-buoy`, first-bite 1.0.1-rc.1, unchanged in 1.1.0; step 1 checks it is still what that command prints |
| `records-v1.jsonl` | the 18 records as version 1 (text values) | `mind --pcap-file examples/harbour-buoys.pcap --dictionary dictionaries/harbour-buoy --output` with `DATA_SOURCE_GEO_LOCATION=harbour-3`, first-bite 1.0.1-rc.1, then `tools/log-to-jsonl.py` |
| `records-v2.jsonl` | the same 18 as version 2 (typed values) | the same command with first-bite 1.1.0 |
