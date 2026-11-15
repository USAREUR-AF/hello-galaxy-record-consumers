#!/usr/bin/env bash
# Step 5 — the AKS path, checked and not deployed: the Bicep file builds, the
# aks overlay renders, and neither holds a secret value. No Azure
# subscription is contacted.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-consumers.sh"

hc_banner "Step 5 — the AKS path" "Checked, not deployed: nothing here contacts Azure."
hc_preflight
[ "$(uname -s)" = Linux ] || hc_die "this step runs on Linux."
BICEP="$(hc_tool bicep)"; KUBECTL="$(hc_tool kubectl)"

hc_step "Build the Bicep file"
hc_cmd "bicep build deploy/aks/main.bicep --outfile .run/5-main.json"
BUILD_LOG="$("$BICEP" build "$HC_ROOT/deploy/aks/main.bicep" --outfile "$HC_RUN/5-main.json" 2>&1)"; BUILD_RC=$?
[ -n "$BUILD_LOG" ] && printf '%s\n' "$BUILD_LOG" | hc_show
SUMMARY="$("$HC_ENGINE" run --rm --network none -v "$HC_RUN:/work:ro" "$HC_APP_IMAGE" python -c '
import json
t = json.load(open("/work/5-main.json"))
print("resources:"); [print(" ", r["type"]) for r in t["resources"]] if isinstance(t["resources"], list) else [print(" ", r["type"]) for r in t["resources"].values()]
secure = [n for n, p in t["parameters"].items() if p["type"].startswith("secure")]
print("parameters:", len(t["parameters"]), "of which secure:", ", ".join(secure))
print("secure parameters with a default:", sum(1 for n in secure if "defaultValue" in t["parameters"][n]))
print("required at deployment:", ", ".join(n for n, p in t["parameters"].items() if "defaultValue" not in p))' 2>&1)"
printf '%s\n' "$SUMMARY" | hc_show

hc_step "Render the aks overlay"
hc_cmd "kubectl kustomize deploy/overlays/aks"
RENDER="$("$KUBECTL" kustomize "$HC_ROOT/deploy/overlays/aks" 2>&1)"; RENDER_RC=$?
printf '%s\n' "$RENDER" | grep -E '^kind:' | sort | uniq -c | hc_show
printf '%s\n' "$RENDER" | grep -E 'image:|PGHOST|PGSSLMODE|cidr: 203|azure-load-balancer|externalTrafficPolicy|type: LoadBalancer' | sed 's/^ *//' | sort -u | hc_show

hc_step "Verify"
hc_assert_ok "the Bicep file builds" test "$BUILD_RC" -eq 0
hc_assert_lacks "with no error or warning" "$BUILD_LOG" "arning"
hc_assert_contains "it declares the cluster" "$SUMMARY" "Microsoft.ContainerService/managedClusters"
hc_assert_contains "the registry" "$SUMMARY" "Microsoft.ContainerRegistry/registries"
hc_assert_contains "and the managed PostgreSQL server" "$SUMMARY" "Microsoft.DBforPostgreSQL/flexibleServers"
hc_assert_contains "the database password is a secure parameter with no default" "$SUMMARY" "secure parameters with a default: 0"
hc_assert_contains "only the name prefix and that password must be given" "$SUMMARY" "required at deployment: namePrefix, postgresAdminPassword"
hc_assert_ok "the aks overlay renders" test "$RENDER_RC" -eq 0
hc_assert_lacks "it contains no Secret" "$RENDER" "kind: Secret"
hc_assert_contains "the database connection verifies the server's certificate" "$RENDER" "PGSSLMODE: verify-full"
hc_assert_contains "the receiver is reached through an internal load balancer" "$RENDER" 'service.beta.kubernetes.io/azure-load-balancer-internal: "true"'
hc_assert_contains "only the decoder's address range may post" "$RENDER" "cidr: 203.0.113.16/28"
hc_note "not run: az deployment group create, and anything on a real AKS cluster"
hc_done
