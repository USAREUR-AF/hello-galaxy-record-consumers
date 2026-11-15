# shellcheck shell=bash
# hello-consumers.sh — shared library for hello-galaxy-record-consumers.
#
# Sourced by every step driver: the images, the pinned tools, narration,
# assertions and clean-up. Adapted from hello-galaxy-first-bite's lib so the
# series reads the same way.
#
# Execution model: the receiver, the board, PostgreSQL and the decoder run in
# containers, first under Docker alone (steps 1 and 2) and then in a local
# Kubernetes cluster made by kind (steps 3 and 4). The host needs bash, curl
# and Docker; kind, kubectl and bicep are downloaded into .run/bin at the
# versions and checksums in tools/pins. State goes under .run/.

set -o pipefail

HC_LIB="${BASH_SOURCE[0]}"
HC_ROOT="$(cd "$(dirname "$HC_LIB")/.." && pwd)"
export HC_ROOT
HC_RUN="$HC_ROOT/.run"
mkdir -p "$HC_RUN/bin"

HC_ENGINE="${CONTAINER_ENGINE:-docker}"
HC_APP_IMAGE="hello-galaxy-record-consumers:local"
HC_TEST_IMAGE="hello-galaxy-record-consumers:local-test"
HC_EDGE_IMAGE="hello-galaxy-record-consumers-edge:local"
HC_FIRST_BITE_IMAGE="$(tr -d '[:space:]' < "$HC_ROOT/FIRST_BITE_IMAGE")"
HC_POSTGRES_IMAGE="postgres:17-alpine@sha256:a77aa70e641402a21411b92b721c58d10f23b50ae5fdd2333efd22d166e1e5f7"
HC_NODE_IMAGE="kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
HC_CLUSTER="hc-record-consumers"
HC_KUBECONFIG="$HC_RUN/kubeconfig"
HC_NET="hc-net"

# --- presentation -----------------------------------------------------------
if [ -t 1 ] && [ "${NO_COLOR:-}" = "" ]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_GREEN=$'\033[32m'; C_RED=$'\033[31m'; C_CYAN=$'\033[36m'; C_BLUE=$'\033[34m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_GREEN=""; C_RED=""; C_CYAN=""; C_BLUE=""
fi
HC_STEP=0
hc_banner() {
  printf '\n%s%s== %s ==%s\n' "$C_BOLD" "$C_BLUE" "$1" "$C_RESET"
  [ -n "${2:-}" ] && printf '%s%s%s\n' "$C_DIM" "$2" "$C_RESET"
}
hc_step() { HC_STEP=$((HC_STEP + 1)); printf '\n%s%s[%d] %s%s\n' "$C_BOLD" "$C_CYAN" "$HC_STEP" "$1" "$C_RESET"; }
hc_say()  { printf '    %s\n' "$1"; }
hc_note() { printf '    %s%s%s\n' "$C_DIM" "$1" "$C_RESET"; }
hc_cmd()  { printf '    %s$ %s%s\n' "$C_GREEN" "$1" "$C_RESET"; }
hc_show() { sed 's/^/    │ /'; }
hc_die()  { printf '%s%s%s\n' "$C_RED" "$1" "$C_RESET" >&2; exit 1; }

# --- preflight --------------------------------------------------------------
hc_preflight() {
  command -v "$HC_ENGINE" >/dev/null 2>&1 || hc_die "$HC_ENGINE is not installed. See README, Prerequisites."
  "$HC_ENGINE" info >/dev/null 2>&1 || hc_die "the $HC_ENGINE daemon is not reachable."
  "$HC_ENGINE" image inspect "$HC_APP_IMAGE" >/dev/null 2>&1 || hc_die "no images yet: bin/hello-consumers build"
  "$HC_ENGINE" image inspect "$HC_EDGE_IMAGE" >/dev/null 2>&1 || hc_die "no images yet: bin/hello-consumers build"
}

# hc_tool <name>: the path of a pinned tool, downloaded and verified on first use.
hc_tool() {
  local name="$1" arch version sum url path
  case "$(uname -m)" in x86_64) arch=amd64 ;; aarch64|arm64) arch=arm64 ;; *) hc_die "no pinned $name for $(uname -m)" ;; esac
  read -r version sum url < <(awk -v n="$name" -v a="$arch" '$1 == n && $3 == a { print $2, $4, $5 }' "$HC_ROOT/tools/pins")
  [ -n "${url:-}" ] || hc_die "tools/pins has no $name for $arch"
  path="$HC_RUN/bin/$name-$version"
  if [ ! -x "$path" ] || ! echo "$sum  $path" | sha256sum -c --status 2>/dev/null; then
    [ "$(uname -s)" = Linux ] || hc_die "the pinned $name is a Linux binary; this step runs on Linux."
    curl -fsSL --retry 3 -o "$path.part" "$url" || hc_die "could not download $url"
    echo "$sum  $path.part" | sha256sum -c --status || { rm -f "$path.part"; hc_die "$url does not have the SHA-256 in tools/pins"; }
    mv "$path.part" "$path"; chmod +x "$path"
    printf '    %s%s %s: downloaded, SHA-256 %s… verified%s\n' "$C_DIM" "$name" "$version" "${sum:0:16}" "$C_RESET" >&2
  fi
  echo "$path"
}
hc_kind()    { "$(hc_tool kind)" "$@"; }
hc_kubectl() { "$(hc_tool kubectl)" --kubeconfig "$HC_KUBECONFIG" "$@"; }

# --- containers and networks this run started --------------------------------
HC_CONTAINERS=()
HC_NETWORKS=()
hc_start() {  # hc_start <name> <docker run arguments...>
  local name="$1"; shift
  "$HC_ENGINE" rm -f "$name" >/dev/null 2>&1 || true
  "$HC_ENGINE" run -d --name "$name" "$@" >/dev/null || hc_die "could not start $name"
  HC_CONTAINERS+=("$name")
}
hc_wait_log() {  # hc_wait_log <container> <fixed text> <seconds>
  local name="$1" text="$2" secs="${3:-20}" i=0
  while [ "$i" -lt $((secs * 5)) ]; do
    "$HC_ENGINE" logs "$name" 2>&1 | grep -qF -- "$text" && return 0
    sleep 0.2; i=$((i + 1))
  done
  "$HC_ENGINE" logs "$name" 2>&1 | tail -n 20 >&2
  return 1
}
hc_cleanup() {
  local name
  for name in ${HC_CONTAINERS[@]+"${HC_CONTAINERS[@]}"}; do "$HC_ENGINE" rm -f "$name" >/dev/null 2>&1 || true; done
  for name in ${HC_NETWORKS[@]+"${HC_NETWORKS[@]}"}; do "$HC_ENGINE" network rm "$name" >/dev/null 2>&1 || true; done
}
trap hc_cleanup EXIT

# --- the Docker-only stack of steps 1 and 2 ----------------------------------
# A private network with PostgreSQL, the receiver and, when asked, the board.
# Passwords are made up for the run and passed in the environment; nothing is
# written to the repository.
hc_password() { head -c 18 /dev/urandom | base64 | tr -d '/+=' | cut -c1-20; }
hc_stack_up() {  # hc_stack_up [board <stale seconds>]
  HC_ADMIN_PW="$(hc_password)"; HC_RECEIVER_PW="$(hc_password)"; HC_BOARD_PW="$(hc_password)"
  "$HC_ENGINE" network rm "$HC_NET" >/dev/null 2>&1 || true
  "$HC_ENGINE" network create --internal "$HC_NET" >/dev/null || hc_die "could not create the network $HC_NET"
  HC_NETWORKS+=("$HC_NET")
  "$HC_ENGINE" image inspect "$HC_POSTGRES_IMAGE" >/dev/null 2>&1 || "$HC_ENGINE" pull -q "$HC_POSTGRES_IMAGE" >/dev/null ||
    hc_die "could not pull $HC_POSTGRES_IMAGE"
  hc_start hc-postgres --network "$HC_NET" --network-alias postgres \
    -e POSTGRES_PASSWORD="$HC_ADMIN_PW" -e POSTGRES_DB=records \
    -e RECEIVER_PASSWORD="$HC_RECEIVER_PW" -e BOARD_PASSWORD="$HC_BOARD_PW" \
    -v "$HC_ROOT/deploy/overlays/local/postgres/init-roles.sh:/docker-entrypoint-initdb.d/init-roles.sh:ro" \
    --tmpfs /var/lib/postgresql/data "$HC_POSTGRES_IMAGE"
  hc_wait_log hc-postgres "PostgreSQL init process complete" 60 || hc_die "PostgreSQL did not initialise"
  hc_start hc-receiver --network "$HC_NET" --network-alias receiver --read-only --user 10001:10001 \
    -e PGHOST=postgres -e PGDATABASE=records -e PGUSER=receiver -e PGPASSWORD="$HC_RECEIVER_PW" \
    -e SCHEMA_FILE=/schema/harbour-buoy.schema.json -e SOURCE_FIELDS=buoy_number -e READER_ROLE=board \
    -v "$HC_ROOT/samples/harbour-buoy.schema.json:/schema/harbour-buoy.schema.json:ro" \
    "$HC_APP_IMAGE" python -m record_consumers.receiver
  hc_wait_log hc-receiver "receiver: listening" 60 || hc_die "the receiver did not start"
  if [ "${1:-}" = board ]; then
    hc_start hc-board --network "$HC_NET" --network-alias board --read-only --user 10001:10001 \
      -e PGHOST=postgres -e PGDATABASE=records -e PGUSER=board -e PGPASSWORD="$HC_BOARD_PW" \
      -e SCHEMA_FILE=/schema/harbour-buoy.schema.json -e STALE_AFTER_SECONDS="${2:-120}" \
      -v "$HC_ROOT/samples/harbour-buoy.schema.json:/schema/harbour-buoy.schema.json:ro" \
      "$HC_APP_IMAGE" python -m record_consumers.board
    hc_wait_log hc-board "board: listening" 30 || hc_die "the board did not start"
  fi
}
# hc_client <command...>: a throwaway container on the stack's network, with the repository at /repo.
hc_client() {
  "$HC_ENGINE" run --rm --network "$HC_NET" --read-only --user 10001:10001 -v "$HC_ROOT:/repo:ro" -w /repo "$HC_APP_IMAGE" "$@"
}
# hc_sql <role> <password> <statement>: one statement, output as aligned text.
hc_sql() {
  "$HC_ENGINE" exec -e PGPASSWORD="$2" hc-postgres psql -h 127.0.0.1 -U "$1" -d records -X -P pager=off -c "$3" 2>&1
}

# --- assertions -------------------------------------------------------------
HC_FAILS=0
hc_assert_contains() {
  local what="$1" hay="$2" needle="$3"
  if printf '%s' "$hay" | grep -qF -- "$needle"; then printf '    %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$what"
  else printf '    %s✗%s %s (expected: %s)\n' "$C_RED" "$C_RESET" "$what" "$needle" >&2; HC_FAILS=$((HC_FAILS + 1)); fi
}
hc_assert_lacks() {
  local what="$1" hay="$2" needle="$3"
  if printf '%s' "$hay" | grep -qF -- "$needle"; then printf '    %s✗%s %s (did NOT expect: %s)\n' "$C_RED" "$C_RESET" "$what" "$needle" >&2; HC_FAILS=$((HC_FAILS + 1))
  else printf '    %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$what"; fi
}
hc_assert_ok() {  # hc_assert_ok <what> <command...>
  local what="$1"; shift
  if "$@" >/dev/null 2>&1; then printf '    %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$what"
  else printf '    %s✗%s %s\n' "$C_RED" "$C_RESET" "$what" >&2; HC_FAILS=$((HC_FAILS + 1)); fi
}
hc_done() {
  if [ "$HC_FAILS" -eq 0 ]; then printf '\n%s%s✓ step complete — every assertion held.%s\n' "$C_BOLD" "$C_GREEN" "$C_RESET"; return 0; fi
  printf '\n%s%s✗ %d assertion(s) failed.%s\n' "$C_BOLD" "$C_RED" "$HC_FAILS" "$C_RESET" >&2; return 1
}

# --- the cluster of steps 3 and 4 ---------------------------------------------
hc_cluster_exists() { hc_kind get clusters 2>/dev/null | grep -qx "$HC_CLUSTER"; }
hc_require_cluster() {
  [ "$(uname -s)" = Linux ] || hc_die "this step runs on Linux."
  hc_cluster_exists && [ -f "$HC_KUBECONFIG" ] || hc_die "no cluster yet: bin/hello-consumers 3-cluster"
}
# hc_request <namespace> <GET|POST> <url>: one HTTP request from the probe pod
# of a namespace. Prints the status and the start of the body, or `no answer`
# when nothing came back within four seconds, which is what a NetworkPolicy
# that drops the packets looks like from inside.
hc_request() {
  hc_kubectl exec -n "$1" probe -- python -c '
import sys, urllib.error, urllib.request
method, url = sys.argv[1], sys.argv[2]
body = b"{}" if method == "POST" else None
request = urllib.request.Request(url, body, {"Content-Type": "application/json"}, method=method)
try:
    with urllib.request.urlopen(request, timeout=4) as response:
        print(response.status, response.read(120).decode("utf-8", "replace").strip())
except urllib.error.HTTPError as error:
    print(error.code, error.read(120).decode("utf-8", "replace").strip())
except OSError as error:
    print("no answer:", getattr(error, "reason", error))
' "$2" "$3" 2>&1
}
# hc_connect <namespace/pod or deploy> <host> <port>: a TCP connection from a pod.
hc_connect() {
  local namespace="$1" target="$2"; shift 2
  hc_kubectl exec -n "$namespace" "$target" -- python -c '
import socket, sys
try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=4).close()
    print("connected")
except OSError as error:
    print("no answer:", error)
' "$1" "$2" 2>&1
}
