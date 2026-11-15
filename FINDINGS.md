# Findings — behaviours a script driving these tools has to know

Each one shaped a file here.

| # | What | How the demo handles it |
|---|---|---|
| 1 | `mind` replaying a capture file exits half a second after the last frame, with exit status 0, whether or not a sink has delivered. A `rest` sink that is still resolving a name or waiting to retry loses its records and nothing in the log says so. A decoder on a live interface keeps running and is not affected. | the decoder Job waits until the receiver accepts a connection before it starts `mind`; step 3 counts the receiver's `201` lines instead of trusting the Job's exit status |
| 2 | A Service name such as `receiver.record-consumers.svc.cluster.local` has four dots, so a pod's resolver first tries it under every search domain, including those the node inherited from its host. Where one of those is slow, every lookup takes seconds, which is longer than a file replay lasts. | names another namespace uses are written fully qualified, with a trailing dot |
| 3 | first-bite's `rest` sink `topics` match exactly; `BUOY/` matches nothing. `*` keeps everything. | `deploy/edge/subscribers.yml` uses `*` |
| 4 | A version 1 record carries scaled values as the text of a binary floating-point number (`"0.35000000000000003"`). Version 2 carries `0.35`. | the receiver stores what it is given; step 1 compares the two versions rounded |
| 5 | The published first-bite image runs as the named user `firstbite`. Kubernetes cannot check `runAsNonRoot` against a name. | the Job sets `runAsUser: 999`, that user's number |
| 6 | The PostgreSQL image, run as its own user 70 on a read-only root filesystem, needs `/var/run/postgresql` and `/tmp` writable. | two `emptyDir` volumes in `postgres.yaml` |
| 7 | kind's network plugin did not admit a pod that was still in its init containers through a NetworkPolicy that selects its namespace. Seen once on kind v0.33.0; not investigated further. | the wait for the receiver is in the decoder's main container, not an init container |
| 8 | `pytest` needs a writable temporary directory even with its cache off. | the test container is run with `--tmpfs /tmp` |
