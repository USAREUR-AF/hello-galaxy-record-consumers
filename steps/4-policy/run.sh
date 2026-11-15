#!/usr/bin/env bash
# Step 4 — who may post, who may read: the NetworkPolicy, the Secret
# references and the pod security of the cluster step 3 left running, each
# shown by trying the thing that must be refused.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-consumers.sh"
RECEIVER=http://receiver.record-consumers.svc.cluster.local.:8080/records
BOARD=http://board.record-consumers.svc.cluster.local.:8080/api/latest

hc_banner "Step 4 — who may post, who may read" "Posting and reading are granted by the owner of the data, namespace by namespace. Everything else is refused."
hc_preflight
hc_require_cluster
hc_kubectl -n record-viewer wait --for=condition=Ready pod/probe --timeout=60s >/dev/null 2>&1 || hc_die "no probe pods: run bin/hello-consumers 3-cluster first"

hc_step "The grants are two namespace labels"
hc_cmd "kubectl get namespaces -L record-consumers/posts-records,record-consumers/reads-board"
hc_kubectl get namespaces -L record-consumers/posts-records,record-consumers/reads-board 2>&1 | grep -E '^NAME|^record-' | hc_show

hc_step "record-viewer was granted the board"
hc_cmd "(record-viewer) GET $BOARD"
VIEW_BOARD="$(hc_request record-viewer GET "$BOARD")"; printf '%s\n' "$VIEW_BOARD" | cut -c1-110 | hc_show
hc_cmd "(record-viewer) POST $RECEIVER"
VIEW_POST="$(hc_request record-viewer POST "$RECEIVER")"; printf '%s\n' "$VIEW_POST" | hc_show
hc_note "the grant to read is not a grant to post"

hc_step "record-stranger was granted nothing"
hc_cmd "(record-stranger) GET $BOARD"
STRANGE_BOARD="$(hc_request record-stranger GET "$BOARD")"; printf '%s\n' "$STRANGE_BOARD" | hc_show
hc_cmd "(record-stranger) POST $RECEIVER"
STRANGE_POST="$(hc_request record-stranger POST "$RECEIVER")"; printf '%s\n' "$STRANGE_POST" | hc_show
hc_cmd "(record-stranger) connect postgres.record-consumers.svc.cluster.local.:5432"
STRANGE_DB="$(hc_connect record-stranger probe postgres.record-consumers.svc.cluster.local. 5432)"; printf '%s\n' "$STRANGE_DB" | hc_show

hc_step "Granting is the owner's act: label the namespace, and the same request is answered"
hc_cmd "kubectl label namespace record-stranger record-consumers/reads-board=true"
hc_kubectl label namespace record-stranger record-consumers/reads-board=true 2>&1 | hc_show
GRANTED=""
for _ in 1 2 3 4 5 6; do GRANTED="$(hc_request record-stranger GET "$BOARD")"; case "$GRANTED" in 200*) break ;; esac; sleep 1; done
printf '%s\n' "$GRANTED" | cut -c1-110 | hc_show
hc_cmd "kubectl label namespace record-stranger record-consumers/reads-board-"
hc_kubectl label namespace record-stranger record-consumers/reads-board- 2>&1 | hc_show
WITHDRAWN=""
for _ in 1 2 3 4 5 6; do WITHDRAWN="$(hc_request record-stranger GET "$BOARD")"; case "$WITHDRAWN" in "no answer"*) break ;; esac; sleep 1; done
printf '%s\n' "$WITHDRAWN" | hc_show

hc_step "The consumers themselves reach the database and nothing else"
hc_cmd "(receiver) connect postgres:5432"
RECV_DB="$(hc_connect record-consumers deployment/receiver postgres 5432)"; printf '%s\n' "$RECV_DB" | hc_show
hc_cmd "(receiver) connect board:8080"
RECV_BOARD="$(hc_connect record-consumers deployment/receiver board 8080)"; printf '%s\n' "$RECV_BOARD" | hc_show
hc_cmd "(board) connect receiver:8080"
BOARD_RECV="$(hc_connect record-consumers deployment/board receiver 8080)"; printf '%s\n' "$BOARD_RECV" | hc_show

hc_step "No secret value is in the repository; the pods hold references"
hc_cmd "kubectl kustomize deploy/overlays/local | grep -c '^kind: Secret'"
RENDERED="$(hc_kubectl kustomize "$HC_ROOT/deploy/overlays/local" 2>&1)"
SECRETS_IN_RENDER="$(printf '%s\n' "$RENDERED" | grep -c '^kind: Secret')"
printf '%s\n' "$SECRETS_IN_RENDER" | hc_show
hc_cmd "kubectl -n record-consumers get deployment board -o jsonpath='{…env[?(@.name==\"PGPASSWORD\")]}'"
REFERENCE="$(hc_kubectl -n record-consumers get deployment board -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="PGPASSWORD")]}' 2>&1)"
printf '%s\n' "$REFERENCE" | hc_show
hc_cmd "kubectl -n record-consumers get secret record-consumers-db -o jsonpath='{.data}' | keys only"
# shellcheck disable=SC2016  # a Go template, not a shell expansion
KEYS="$(hc_kubectl -n record-consumers get secret record-consumers-db -o go-template='{{range $k, $v := .data}}{{$k}} {{end}}' 2>&1)"
printf '%s\n' "$KEYS" | hc_show

hc_step "Pods run as a numbered user that is not root, on a read-only root filesystem"
hc_cmd "kubectl -n record-consumers get pods -o custom-columns=…"
SECURITY="$(hc_kubectl -n record-consumers get pods -o custom-columns='POD:.metadata.labels.app\.kubernetes\.io/name,USER:.spec.securityContext.runAsUser,NON-ROOT:.spec.securityContext.runAsNonRoot,READ-ONLY-ROOT:.spec.containers[0].securityContext.readOnlyRootFilesystem,CAPABILITIES-DROPPED:.spec.containers[0].securityContext.capabilities.drop,CPU-LIMIT:.spec.containers[0].resources.limits.cpu,MEMORY-LIMIT:.spec.containers[0].resources.limits.memory' 2>&1)"
printf '%s\n' "$SECURITY" | hc_show
hc_cmd "kubectl -n record-consumers exec deployment/receiver -- touch /app/written"
READONLY="$(hc_kubectl -n record-consumers exec deployment/receiver -- touch /app/written 2>&1)"; printf '%s\n' "$READONLY" | head -n 1 | hc_show
hc_cmd "kubectl -n record-consumers run as-root --image=hello-galaxy-record-consumers:local --overrides='{…runAsUser: 0…}'"
ASROOT="$(hc_kubectl -n record-consumers run as-root --image="$HC_APP_IMAGE" --restart=Never \
  --overrides='{"spec":{"securityContext":{"runAsUser":0}}}' 2>&1)"
hc_kubectl -n record-consumers delete pod as-root --ignore-not-found >/dev/null 2>&1
printf '%s\n' "$ASROOT" | cut -c1-230 | hc_show

hc_step "Verify"
hc_assert_contains "the granted namespace reads the board" "$VIEW_BOARD" '200 {"stale_after_seconds"'
hc_assert_contains "the same namespace may not post" "$VIEW_POST" "no answer"
hc_assert_contains "a namespace with no grant gets no answer from the board" "$STRANGE_BOARD" "no answer"
hc_assert_contains "nor from the receiver" "$STRANGE_POST" "no answer"
hc_assert_contains "nor from the database" "$STRANGE_DB" "no answer"
hc_assert_contains "once labelled by the owner, it reads the board" "$GRANTED" '200 {"stale_after_seconds"'
hc_assert_contains "and when the label is removed, it no longer does" "$WITHDRAWN" "no answer"
hc_assert_contains "the receiver reaches the database" "$RECV_DB" "connected"
hc_assert_contains "the receiver reaches nothing else in the namespace" "$RECV_BOARD" "no answer"
hc_assert_contains "the board cannot post to the receiver" "$BOARD_RECV" "no answer"
hc_assert_ok "the rendered manifests contain no Secret" test "$SECRETS_IN_RENDER" -eq 0
hc_assert_contains "the board's password is a reference to a key of the Secret" "$REFERENCE" '"secretKeyRef":{"key":"board-password","name":"record-consumers-db"}'
hc_assert_contains "the Secret in the cluster holds the three keys" "$KEYS" "admin-password board-password receiver-password"
hc_assert_lacks "no pod runs as root" "$SECURITY" " 0 "
hc_assert_lacks "every pod has a read-only root filesystem" "$SECURITY" "<none>"
hc_assert_contains "a write to the root filesystem fails" "$READONLY" "Read-only file system"
hc_assert_contains "the namespace refuses a pod that asks to run as root" "$ASROOT" 'violates PodSecurity "restricted'
hc_done
