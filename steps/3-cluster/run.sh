#!/usr/bin/env bash
# Step 3 — on Kubernetes: a local cluster, the consumers deployed from the
# Kustomize overlay, the decoder posting from its own namespace, the board
# read from a namespace that was granted it. The cluster is left running for
# step 4; bin/hello-consumers clean deletes it.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-consumers.sh"

hc_banner "Step 3 — on Kubernetes" "The decoder at the edge posts records; the receiver, the database and the board run in the cluster."
hc_preflight
[ "$(uname -s)" = Linux ] || hc_die "this step runs on Linux."

hc_step "A local cluster"
hc_cluster_exists && hc_kind delete cluster --name "$HC_CLUSTER" >/dev/null 2>&1
hc_cmd "kind create cluster --name $HC_CLUSTER --image kindest/node:v1.37.0@sha256:a1ed…"
hc_kind create cluster --name "$HC_CLUSTER" --image "$HC_NODE_IMAGE" --kubeconfig "$HC_KUBECONFIG" --wait 180s >"$HC_RUN/3-kind.log" 2>&1 ||
  { tail -n 20 "$HC_RUN/3-kind.log" >&2; hc_die "kind could not create the cluster"; }
hc_kubectl get nodes 2>&1 | hc_show
hc_cmd "kind load docker-image hello-galaxy-record-consumers:local hello-galaxy-record-consumers-edge:local"
hc_kind load docker-image "$HC_APP_IMAGE" "$HC_EDGE_IMAGE" --name "$HC_CLUSTER" >>"$HC_RUN/3-kind.log" 2>&1 ||
  { tail -n 20 "$HC_RUN/3-kind.log" >&2; hc_die "kind could not load the images"; }

hc_step "The Secret: made in the cluster, never written to a file"
hc_say "Three passwords made up now. The manifests hold references to the Secret's keys and no value."
hc_kubectl apply -f "$HC_ROOT/deploy/base/namespace.yaml" 2>&1 | hc_show
hc_cmd "kubectl -n record-consumers create secret generic record-consumers-db --from-literal=admin-password=… --from-literal=receiver-password=… --from-literal=board-password=…"
hc_kubectl -n record-consumers create secret generic record-consumers-db \
  --from-literal=admin-password="$(hc_password)" --from-literal=receiver-password="$(hc_password)" \
  --from-literal=board-password="$(hc_password)" 2>&1 | hc_show

hc_step "Deploy the consumers"
hc_cmd "kubectl apply -k deploy/overlays/local"
hc_kubectl apply -k "$HC_ROOT/deploy/overlays/local" 2>&1 | hc_show
hc_cmd "kubectl -n record-consumers rollout status statefulset/postgres deployment/receiver deployment/board"
ROLLOUT=""
for workload in statefulset/postgres deployment/receiver deployment/board; do
  ROLLOUT+="$(hc_kubectl -n record-consumers rollout status "$workload" --timeout=240s 2>&1 | tail -n 1)"$'\n'
done
printf '%s' "$ROLLOUT" | hc_show
hc_kubectl -n record-consumers get pods 2>&1 | hc_show
hc_kubectl -n record-consumers logs deployment/receiver 2>&1 | grep '^receiver:' | hc_show

hc_step "The decoder: first-bite replays the capture and posts each record"
hc_say "first-bite's rest sink, configured in deploy/edge/subscribers.yml, posts to the receiver's Service."
hc_cmd "kubectl apply -k deploy/edge"
hc_kubectl apply -k "$HC_ROOT/deploy/edge" 2>&1 | hc_show
hc_say "The Job ends with mind: complete when mind exits 0, failed when it exits 3 because records were not delivered."
hc_cmd "kubectl -n record-edge get job/decoder -o jsonpath='succeeded={.status.succeeded} failed={.status.failed}'"
JOB=""
for _ in $(seq 1 180); do
  JOB="$(hc_kubectl -n record-edge get job/decoder -o jsonpath='succeeded={.status.succeeded} failed={.status.failed}' 2>&1)"
  case "$JOB" in *"succeeded=1"*|*"failed=1"*) break ;; esac
  sleep 1
done
EXIT_CODE="$(hc_kubectl -n record-edge get pods -l job-name=decoder -o jsonpath='{.items[0].status.containerStatuses[0].state.terminated.exitCode}' 2>&1)"
printf '%s; mind exited %s\n' "$JOB" "$EXIT_CODE" | hc_show
DECODER="$(hc_kubectl -n record-edge logs job/decoder 2>&1)"
printf '%s\n' "$DECODER" | grep -o 'done: .*\|sink receiver: .*\|rest.*' | cut -c1-160 | hc_show
sleep 2
RECEIVED="$(hc_kubectl -n record-consumers logs deployment/receiver 2>&1 | grep -c '^POST /records 201')"
hc_note "the receiver's log has $RECEIVED lines \"POST /records 201\""

hc_step "Read the board from a namespace that was granted it"
hc_kubectl apply -k "$HC_ROOT/deploy/probes" 2>&1 | hc_show
hc_kubectl -n record-viewer wait --for=condition=Ready pod/probe --timeout=120s >/dev/null 2>&1
hc_kubectl -n record-stranger wait --for=condition=Ready pod/probe --timeout=120s >/dev/null 2>&1
hc_cmd "kubectl -n record-viewer exec probe -- curl http://board.record-consumers.svc.cluster.local.:8080/api/latest"
LATEST="$(hc_kubectl -n record-viewer exec probe -- python -c '
import json, urllib.request
latest = json.load(urllib.request.urlopen("http://board.record-consumers.svc.cluster.local.:8080/api/latest", timeout=10))
for e in latest["entries"]:
    print("{interface}/{message} | {site} | {source} | {records} records | record version {record_version}".format(**e))
print(len(latest["entries"]), "entries")' 2>&1)"
printf '%s\n' "$LATEST" | hc_show

hc_step "Verify"
hc_assert_contains "PostgreSQL, the receiver and the board rolled out" "$ROLLOUT" 'deployment "board" successfully rolled out'
hc_assert_contains "the receiver made its tables from the schema in the ConfigMap" "$(hc_kubectl -n record-consumers logs deployment/receiver 2>&1)" "tables: buoy__position, buoy__sea_state, buoy__status"
hc_assert_contains "the decoder decoded all 18 frames of the capture" "$DECODER" "done: 18 frames, 18 records, 18 decoded"
hc_assert_contains "the decoder's sink delivered all 18 before mind exited" "$DECODER" "sink receiver: 18 delivered, 0 failed, 0 abandoned"
hc_assert_contains "the Job completed: mind exited 0" "$JOB; $EXIT_CODE" "succeeded=1 failed=; 0"
hc_assert_ok "the receiver stored 18 records posted by first-bite" test "$RECEIVED" -eq 18
hc_assert_contains "the board shows three message types from each of two buoys" "$LATEST" "6 entries"
hc_assert_contains "each with its three records, from the site the decoder named" "$LATEST" "BUOY/Sea State | harbour-3 | 198.51.100.11 buoy_number=3 | 3 records"
hc_done
