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
    │     kubectl v1.37.0: downloaded, SHA-256 6129359f4e1f3848… verified
    │ NAME                                STATUS   ROLES           AGE   VERSION
    │ hc-record-consumers-control-plane   Ready    control-plane   34s   v1.37.0
    $ kind load docker-image hello-galaxy-record-consumers:local hello-galaxy-record-consumers-edge:local

[2] The Secret: made in the cluster, never written to a file
    Three passwords made up now. The manifests hold references to the Secret's keys and no value.
    │ namespace/record-consumers created
    $ kubectl -n record-consumers create secret generic record-consumers-db --from-literal=admin-password=… --from-literal=receiver-password=… --from-literal=board-password=…
    │ secret/record-consumers-db created

[3] Deploy the consumers
    $ kubectl apply -k deploy/overlays/local
    │ namespace/record-consumers configured
    │ configmap/postgres-init-h77c746k25 created
    │ configmap/record-consumers-database-ck4957gm2m created
    │ configmap/record-consumers-settings-9928mckth8 created
    │ configmap/record-schema-cf8fdd4557 created
    │ service/board created
    │ service/postgres created
    │ service/receiver created
    │ deployment.apps/board created
    │ deployment.apps/receiver created
    │ statefulset.apps/postgres created
    │ networkpolicy.networking.k8s.io/board-serves-readers created
    │ networkpolicy.networking.k8s.io/consumers-reach-database created
    │ networkpolicy.networking.k8s.io/database-accepts-consumers created
    │ networkpolicy.networking.k8s.io/default-deny created
    │ networkpolicy.networking.k8s.io/name-resolution created
    │ networkpolicy.networking.k8s.io/receiver-accepts-records created
    $ kubectl -n record-consumers rollout status statefulset/postgres deployment/receiver deployment/board
    │ partitioned roll out complete: 1 new pods have been updated...
    │ deployment "receiver" successfully rolled out
    │ deployment "board" successfully rolled out
    │ NAME                        READY   STATUS    RESTARTS   AGE
    │ board-75c6f648d7-rkvd8      1/1     Running   0          48s
    │ postgres-0                  1/1     Running   0          47s
    │ receiver-7b4cb56dfd-49vhb   1/1     Running   0          48s
    │ receiver: 3 message types from /schema/harbour-buoy.schema.json; tables: buoy__position, buoy__sea_state, buoy__status
    │ receiver: listening on 0.0.0.0:8080

[4] The decoder: first-bite replays the capture and posts each record
    first-bite's rest sink, configured in deploy/edge/subscribers.yml, posts to the receiver's Service.
    $ kubectl apply -k deploy/edge
    │ namespace/record-edge created
    │ configmap/decoder-sinks-7m65bk4kfd created
    │ job.batch/decoder created
    The Job ends with mind: complete when mind exits 0, failed when it exits 3 because records were not delivered.
    $ kubectl -n record-edge get job/decoder -o jsonpath='succeeded={.status.succeeded} failed={.status.failed}'
    │ succeeded=1 failed=; mind exited 0
    │ sink receiver: 18 delivered, 0 failed, 0 abandoned
    │ done: 18 frames, 18 records, 18 decoded, 0 not UDP or TCP, 0 malformed
    the receiver's log has 18 lines "POST /records 201"

[5] Read the board from a namespace that was granted it
    │ namespace/record-stranger created
    │ namespace/record-viewer created
    │ pod/probe created
    │ pod/probe created
    $ kubectl -n record-viewer exec probe -- curl http://board.record-consumers.svc.cluster.local.:8080/api/latest
    │ BUOY/Position | harbour-3 | 198.51.100.10 buoy_number=7 | 3 records | record version 2
    │ BUOY/Position | harbour-3 | 198.51.100.11 buoy_number=3 | 3 records | record version 2
    │ BUOY/Sea State | harbour-3 | 198.51.100.10 buoy_number=7 | 3 records | record version 2
    │ BUOY/Sea State | harbour-3 | 198.51.100.11 buoy_number=3 | 3 records | record version 2
    │ BUOY/Status | harbour-3 | 198.51.100.10 buoy_number=7 | 3 records | record version 2
    │ BUOY/Status | harbour-3 | 198.51.100.11 buoy_number=3 | 3 records | record version 2
    │ 6 entries

[6] Verify
    ✓ PostgreSQL, the receiver and the board rolled out
    ✓ the receiver made its tables from the schema in the ConfigMap
    ✓ the decoder decoded all 18 frames of the capture
    ✓ the decoder's sink delivered all 18 before mind exited
    ✓ the Job completed: mind exited 0
    ✓ the receiver stored 18 records posted by first-bite
    ✓ the board shows three message types from each of two buoys
    ✓ each with its three records, from the site the decoder named

✓ step complete — every assertion held.
```

The records are version 2, typed values, because the decoder is first-bite
1.1.0. The receiver stores version 1 and version 2 as the same row (step 1), so
`FIRST_BITE_RECORD_VERSION=1` in the Job's environment changes the last column
and nothing else in the cluster.

The Job's result is `mind`'s exit status. At the end of the capture `mind`
gives its sink up to `--drain-seconds` (30 by default) to deliver, logs
`sink receiver: <n> delivered, <n> failed, <n> abandoned`, and exits 3 when
records were abandoned or none was delivered; with `backoffLimit: 0` the Job
then fails. The step starts the Job once the receiver has rolled out.

To look at the board yourself while the cluster is up:

```bash
.run/bin/kubectl-v1.37.0 --kubeconfig .run/kubeconfig -n record-consumers port-forward service/board 8081:8080
# then open http://127.0.0.1:8081/
```

A port-forward reaches the pod from its own node, which a NetworkPolicy does
not stop; it needs the cluster's credentials, which is a grant of its own.
