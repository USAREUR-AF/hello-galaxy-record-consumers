# Step 3 — on Kubernetes

**The decoder at the edge posts records; the receiver, the database and the
board run in a cluster.** A local cluster made by
[kind](https://kind.sigs.k8s.io), on Linux.

```text
 namespace record-edge                 namespace record-consumers
 ┌───────────────────────┐  HTTP POST  ┌──────────┐   rows   ┌────────────┐
 │ Job decoder           │ ──────────▶ │ receiver │ ───────▶ │ postgres   │
 │ first-bite: mind      │  /records   └──────────┘          └────────────┘
 │ replays the capture,  │                                          ▲ reads
 │ rest sink             │             ┌──────────┐                 │
 └───────────────────────┘             │ board    │ ────────────────┘
 namespace record-viewer   HTTP GET    └──────────┘
 │ pod probe             │ ──────────▶      ▲
```

In a deployment the decoder is a machine beside the tap, outside the cluster.
Here it is a Job in a namespace of its own, so that the whole path runs on
one machine and the cluster's rules about who may post apply to it as they
would to an address. The decoder is the published first-bite image with this
example's dictionary and capture added ([`edge/Dockerfile`](../../edge/Dockerfile));
its sink is nine lines of configuration
([`deploy/edge/subscribers.yml`](../../deploy/edge/subscribers.yml)).

```bash
bin/hello-consumers 3-cluster      # leaves the cluster running for step 4
```

## What is applied

| Path | Holds |
|---|---|
| [`deploy/base/`](../../deploy/base) | the receiver and the board: a Deployment and a Service each, their settings, the schema as a ConfigMap, the NetworkPolicies |
| [`deploy/overlays/local/`](../../deploy/overlays/local) | the base, PostgreSQL as a StatefulSet, the images this repository builds |
| [`deploy/edge/`](../../deploy/edge) | the namespace that may post, and the decoder Job |
| [`deploy/probes/`](../../deploy/probes) | a namespace granted the board and one granted nothing, each with an idle pod to look from |

Every container has CPU and memory requests and limits, runs as a numbered
user that is not root on a read-only root filesystem with every capability
dropped, and has a start-up, a readiness and a liveness probe. The namespaces
enforce Kubernetes' `restricted` pod security standard.

The Secret `record-consumers-db` is in no file. The step makes three
passwords and creates it with `kubectl create secret`; the manifests refer to
its keys.

## What you should see

```text
[1] A local cluster
    $ kind create cluster --name hc-record-consumers --image kindest/node:v1.37.0@sha256:a1ed…
    │ NAME                                STATUS   ROLES           AGE   VERSION
    │ hc-record-consumers-control-plane   Ready    control-plane   28s   v1.37.0

[2] The Secret: made in the cluster, never written to a file
    │ namespace/record-consumers created
    $ kubectl -n record-consumers create secret generic record-consumers-db --from-literal=admin-password=… --from-literal=receiver-password=… --from-literal=board-password=…
    │ secret/record-consumers-db created

[3] Deploy the consumers
    $ kubectl apply -k deploy/overlays/local
    │ …
    │ deployment.apps/board created
    │ deployment.apps/receiver created
    │ statefulset.apps/postgres created
    │ networkpolicy.networking.k8s.io/board-serves-readers created
    │ networkpolicy.networking.k8s.io/consumers-reach-database created
    │ networkpolicy.networking.k8s.io/database-accepts-consumers created
    │ networkpolicy.networking.k8s.io/default-deny created
    │ networkpolicy.networking.k8s.io/name-resolution created
    │ networkpolicy.networking.k8s.io/receiver-accepts-records created
    │ deployment "receiver" successfully rolled out
    │ deployment "board" successfully rolled out
    │ receiver: 3 message types from /schema/harbour-buoy.schema.json; tables: buoy__position, buoy__sea_state, buoy__status

[4] The decoder: first-bite replays the capture and posts each record
    $ kubectl apply -k deploy/edge
    │ namespace/record-edge created
    │ job.batch/decoder created
    │ job.batch/decoder condition met
    │ done: 18 frames, 18 records, 18 decoded, 0 not UDP or TCP, 0 malformed
    the receiver's log has 18 lines "POST /records 201"

[5] Read the board from a namespace that was granted it
    $ kubectl -n record-viewer exec probe -- curl http://board.record-consumers.svc.cluster.local.:8080/api/latest
    │ BUOY/Position | harbour-3 | 198.51.100.10 buoy_number=7 | 3 records | record version 1
    │ BUOY/Position | harbour-3 | 198.51.100.11 buoy_number=3 | 3 records | record version 1
    │ BUOY/Sea State | harbour-3 | 198.51.100.10 buoy_number=7 | 3 records | record version 1
    │ BUOY/Sea State | harbour-3 | 198.51.100.11 buoy_number=3 | 3 records | record version 1
    │ BUOY/Status | harbour-3 | 198.51.100.10 buoy_number=7 | 3 records | record version 1
    │ BUOY/Status | harbour-3 | 198.51.100.11 buoy_number=3 | 3 records | record version 1
    │ 6 entries
```

The records are version 1 because the decoder is first-bite 1.0.1-rc.1. Move
the pin in [`FIRST_BITE_IMAGE`](../../FIRST_BITE_IMAGE) to release 1.1.0 and
they arrive as version 2; nothing in the cluster changes.

To look at the board yourself while the cluster is up:

```bash
.run/bin/kubectl-v1.37.0 --kubeconfig .run/kubeconfig -n record-consumers port-forward service/board 8081:8080
# then open http://127.0.0.1:8081/
```

A port-forward reaches the pod from its own node, which a NetworkPolicy does
not stop; it needs the cluster's credentials, which is a grant of its own.
