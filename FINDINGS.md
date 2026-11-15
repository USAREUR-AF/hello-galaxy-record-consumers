# Findings — behaviours a script driving these tools has to know

Each one shaped a file here.

| # | What | How the demo handles it |
|---|---|---|
| 1 | `mind` replaying a capture file gives its sinks up to `--drain-seconds` (30 by default) after the last frame, logs `sink <name>: <n> delivered, <n> failed, <n> abandoned`, and exits 3 when a sink abandoned records or delivered none. The `rest` sink retries a failed connection three times, waiting 2, 4 and 8 s. | the decoder Job runs `mind` directly, so its result is `mind`'s; step 3 starts it after the receiver has rolled out, checks the sink's line and the exit status, and counts the receiver's `201` lines |
| 2 | A Service name such as `receiver.record-consumers.svc.cluster.local` has four dots, so a pod's resolver first tries it under every search domain, including those the node inherited from its host. Where one of those is slow, every lookup takes seconds, which is longer than a file replay lasts. | names another namespace uses are written fully qualified, with a trailing dot |
| 3 | first-bite's `rest` sink `topics` match exactly; `BUOY/` matches nothing. `*` keeps everything. | `deploy/edge/subscribers.yml` uses `*` |
| 4 | A version 1 record carries scaled values as the text of a binary floating-point number (`"0.35000000000000003"`). Version 2 carries `0.35`. | the receiver stores what it is given; step 1 compares the two versions rounded |
| 5 | The published first-bite image declares `USER 10001:10001`. | the Job sets `runAsUser` and `runAsGroup` to 10001, so `runAsNonRoot` is checked against the same number |
| 6 | The PostgreSQL image, run as its own user 70 on a read-only root filesystem, needs `/var/run/postgresql` and `/tmp` writable. | two `emptyDir` volumes in `postgres.yaml` |
| 7 | kind's network plugin did not admit a pod that was still in its init containers through a NetworkPolicy that selects its namespace. Seen once on kind v0.33.0; not investigated further. | the decoder has no init container |
| 8 | `pytest` needs a writable temporary directory even with its cache off. | the test container is run with `--tmpfs /tmp` |
