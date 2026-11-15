# hello-galaxy-record-consumers

**first-bite decodes binary messages beside a tap and posts each record over
HTTP. What receives them? Five runnable steps: a receiver that makes its
tables from the dictionary, a latest-status board, both on Kubernetes, the
rules for who may post and who may read, and an AKS path.**

This is a repository of the **Hello Galaxy** series: small, self-contained,
runnable examples of best practice in one dimension. Like the rest of the
series, it is a short runbook per step plus one driver script that narrates
what happens. The source is simulated and the cluster is local; everything
else runs for real: the published
[first-bite](https://github.com/USAREUR-AF/first-bite) image, PostgreSQL, and
a Kubernetes cluster with its NetworkPolicy enforced. Where something here is
not what a deployment has, the step says so.

---

## The question this repository answers

A decoder sits beside the equipment. The people who want the data do not:
they want it in a database they can query and on a page that says, for every
source, when it was last heard and what it last said. That is a small service
in a cluster, and it has two properties worth getting right:

- **It knows nothing about the messages.** The receiver is given the JSON
  Schema that `bite schema <dictionary>` exports. It makes one table per
  message and one column per field from that file, and validates every record
  against it. A new message set is a new file, not new code.
- **Reading the data is something its owner grants.** A namespace may post
  only when the owner labels it; a namespace may open the board only when the
  owner labels it; the board reads the database with a role that cannot
  write; no password is in a file.

Read [`docs/00-which-consumer.md`](docs/00-which-consumer.md) to decide
whether a cluster consumer is what you need: a goat subscriber and the
Cursor-on-Target path take other parts of the same job.

## The five steps

| Step | What it shows | Runs | Ends by proving |
|---|---|---|---|
| [**1 receiver**](steps/1-receiver/) | tables made from the schema; records of both versions stored as the same row; a record the schema does not allow refused | Docker | 18 tests pass; 36 of 36 records stored; version 1 and version 2 give the same row; two bad records refused with the reason |
| [**2 board**](steps/2-board/) | the latest record per source and message type, stale sources marked; a database role that can only read | Docker | 6 rows, 3 stale; an insert by the board's role is refused |
| [**3 cluster**](steps/3-cluster/) | a kind cluster; the consumers from the Kustomize overlay; first-bite as the decoder, posting through its `rest` sink | Linux, kind | first-bite decoded 18 frames, the receiver stored 18, the board shows 6 rows |
| [**4 policy**](steps/4-policy/) | who may post and who may read, each tried from a namespace with and without the grant; Secret references; pod security | the cluster of step 3 | 17 checks: every request without a grant gets no answer; a pod that asks for root is refused |
| [**5 aks**](steps/5-aks/) | a Bicep file for a cluster, a registry and managed PostgreSQL, and the overlay for it | builds and renders only | the file builds; the overlay renders; neither holds a secret value |

## Run it

Prerequisites: Linux, `bash`, `curl` and Docker. kind, kubectl and bicep are
downloaded into `.run/bin` at the versions and checksums in
[`tools/pins`](tools/pins); nothing is installed on the host.

```bash
bin/hello-consumers build      # the consumer image, its test image, the decoder image
bin/hello-consumers all        # the five steps in order
```

`bin/hello-consumers <step>` runs one; `bin/hello-consumers list` names them;
`bin/hello-consumers clean` deletes the cluster, the containers, the images
and `.run/`. Step 4 uses the cluster step 3 leaves running.

| Measured on one machine (16 cores, Docker 29.6) | |
|---|---|
| `bin/hello-consumers build`, base images pulled | 44 s |
| `bin/hello-consumers all`, kind node image already pulled | 3 min 56 s and 5 min 5 s, two runs |

### What is verified where

| | In CI, on a GitHub-hosted runner | On a Linux host | Not run |
|---|---|---|---|
| Steps 1 to 5 | every push and pull request | yes | |
| The board in a browser, light and dark | | by eye | |
| `deploy/aks/main.bicep` deployed; the `aks` overlay applied | | | not deployed: there was no subscription to deploy to |
| macOS | | | not run. Steps 1 and 2 need only Docker; steps 3 to 5 download Linux binaries |
| A decoder outside the cluster on a live interface | | | not run here; [hello-galaxy-first-bite](https://github.com/USAREUR-AF/hello-galaxy-first-bite) step 2 runs first-bite on a live link |

## What is pinned

| What | Pin | Change it in |
|---|---|---|
| first-bite | the published image of release candidate `1.0.1-rc.1`, by digest | [`FIRST_BITE_IMAGE`](FIRST_BITE_IMAGE). Release 1.1.0 changes the record to typed values (version 2); the receiver already takes both, and step 3's last column then reads `record version 2` |
| Python and PostgreSQL images | `python:3.13-slim`, `postgres:17-alpine`, by digest | [`app/Dockerfile`](app/Dockerfile), `HC_POSTGRES_IMAGE` in [`lib/hello-consumers.sh`](lib/hello-consumers.sh), [`postgres.yaml`](deploy/overlays/local/postgres/postgres.yaml) |
| Python packages | by version and hash | [`app/requirements.txt`](app/requirements.txt), compiled from `requirements.in` |
| kind, kubectl, bicep; the kind node image | by SHA-256; by digest | [`tools/pins`](tools/pins), `HC_NODE_IMAGE` |
| GitHub Actions | by commit SHA | [`.github/workflows/`](.github/workflows) |

## What is deliberately simplified, and what to copy

The decoder is a Job that replays a capture, in a namespace of the same
cluster. In a deployment it is a machine beside the tap, and the receiver
admits its address, not a namespace; the `aks` overlay is written that way.

The receiver and the board do not authenticate a caller. A namespace or an
address is admitted by NetworkPolicy, and that is the whole of the grant. The
services speak HTTP inside the cluster. PostgreSQL in the local overlay is one
pod with no backup.

**Copy the schema-driven tables, the two database roles, the default-deny
NetworkPolicy with its two labels, the Secret reference pattern and the pod
security settings; replace the Job with your decoder, the local database with
one you back up, and add TLS at your ingress.**
[`docs/do-it-for-real.md`](docs/do-it-for-real.md) has the list.

## Repository layout

```
bin/hello-consumers       dispatcher: build, <step>, all, list, clean
lib/hello-consumers.sh    shared narration / assertion / container / cluster library
FIRST_BITE_IMAGE          the first-bite image the decoder is built from
app/                      the receiver and the board: record_consumers/, tests/, Dockerfile, requirements
edge/Dockerfile           the decoder: first-bite with this example's dictionary and capture
deploy/base/              Kustomize base: receiver, board, settings, schema, NetworkPolicies
deploy/overlays/local/    kind: the base, PostgreSQL in the cluster, the images built here
deploy/overlays/aks/      AKS: the base, a managed database and a decoder outside the cluster
deploy/aks/main.bicep     an AKS cluster, a registry and managed PostgreSQL, every name a parameter
deploy/edge/              the namespace that may post, and the decoder Job
deploy/probes/            a namespace granted the board and one granted nothing
dictionaries/harbour-buoy the dictionary, as hello-galaxy-first-bite builds it
examples/                 the sample capture: two simulated buoys, 18 datagrams
samples/                  the exported schema, and the records as version 1 and version 2
steps/                    1-receiver, 2-board, 3-cluster, 4-policy, 5-aks: README + run.sh each
tools/                    post-records.py, log-to-jsonl.py, make-sample-pcap.py, buoy.py, pins
docs/                     00-which-consumer, do-it-for-real
FINDINGS.md               behaviours of first-bite, kind and PostgreSQL a script driving them has to know
```

## How this maps to first-bite and goat

| Here | In first-bite | In goat |
|---|---|---|
| the decoder's sink | `flow/config/README.md`, the `rest` sink | |
| the record, versions 1 and 2 | `docs/record.md` | |
| the schema the receiver reads | `bite schema`, `docs/dictionary-format.md` | the same schema is what first-bite's `goat` sink declares at `attest/schema/<record key>` |
| the dictionary and the simulated buoy | | [hello-galaxy-first-bite](https://github.com/USAREUR-AF/hello-galaxy-first-bite) |
| `docs/00-which-consumer.md` | `docs/goat-integration.md` | goatcore `docs/design/zenoh-data-fabric.md` |

One of the Hello Galaxy series of runnable goat demonstrations.

## Acknowledgements

The receiver and the latest-status board follow a design by Scarlett Swerdlow,
who built the first services that consumed first-bite's records: a status
store with a board of every source's latest report, and a service that
delivered Cursor-on-Target to TAK servers. This repository rebuilds that
design so that it reads its tables from a dictionary's schema.

## Licence

`hello-galaxy-record-consumers` was written by U.S. Federal government employees. In the U.S. it is not subject to copyright and is in the public domain; in countries where copyright is recognized, it is released under the [Apache License 2.0](LICENSE). See [INTENT.md](INTENT.md).
