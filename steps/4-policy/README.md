# Step 4 — who may post, who may read

**Posting records and reading them are each granted by the owner of the
data. This step tries what must be refused and shows it refused.** It uses
the cluster step 3 left running.

| Grant | How the owner gives it | Enforced by |
|---|---|---|
| post records to the receiver | the label `record-consumers/posts-records: "true"` on a namespace (on AKS: an address range) | NetworkPolicy `receiver-accepts-records` |
| open the board | the label `record-consumers/reads-board: "true"` on a namespace | NetworkPolicy `board-serves-readers` |
| read the database | a database role with `SELECT`, and its password as a key of the Secret | PostgreSQL; NetworkPolicy `database-accepts-consumers` admits the receiver and the board only |
| write the database | the role `receiver` | PostgreSQL |

Everything not granted is refused: `default-deny` selects every pod of the
namespace for ingress and egress, and the other policies open exactly the
paths in the table, plus name resolution.

```bash
bin/hello-consumers 4-policy       # after 3-cluster
```

## What you should see

```text
[1] The grants are two namespace labels
    │ NAME                 STATUS   AGE    POSTS-RECORDS   READS-BOARD
    │ record-consumers     Active   63s
    │ record-edge          Active   12s    true
    │ record-stranger      Active   4s
    │ record-viewer        Active   4s                     true

[2] record-viewer was granted the board
    $ (record-viewer) GET http://board.record-consumers.svc.cluster.local.:8080/api/latest
    │ 200 {"stale_after_seconds":120.0,"entries":[{"site":"harbour-3","source":"198.51.100.10 buoy_number=7",…
    $ (record-viewer) POST http://receiver.record-consumers.svc.cluster.local.:8080/records
    │ no answer: timed out

[3] record-stranger was granted nothing
    $ (record-stranger) GET http://board.record-consumers.svc.cluster.local.:8080/api/latest
    │ no answer: timed out
    $ (record-stranger) POST http://receiver.record-consumers.svc.cluster.local.:8080/records
    │ no answer: timed out
    $ (record-stranger) connect postgres.record-consumers.svc.cluster.local.:5432
    │ no answer: timed out

[4] Granting is the owner's act: label the namespace, and the same request is answered
    $ kubectl label namespace record-stranger record-consumers/reads-board=true
    │ 200 {"stale_after_seconds":120.0,"entries":[…
    $ kubectl label namespace record-stranger record-consumers/reads-board-
    │ no answer: timed out

[5] The consumers themselves reach the database and nothing else
    $ (receiver) connect postgres:5432
    │ connected
    $ (receiver) connect board:8080
    │ no answer: timed out
    $ (board) connect receiver:8080
    │ no answer: timed out

[6] No secret value is in the repository; the pods hold references
    $ kubectl kustomize deploy/overlays/local | grep -c '^kind: Secret'
    │ 0
    │ {"name":"PGPASSWORD","valueFrom":{"secretKeyRef":{"key":"board-password","name":"record-consumers-db"}}}
    │ admin-password board-password receiver-password

[7] Pods run as a numbered user that is not root, on a read-only root filesystem
    │ POD        USER    NON-ROOT   READ-ONLY-ROOT   CAPABILITIES-DROPPED   CPU-LIMIT   MEMORY-LIMIT
    │ board      10001   true       true             [ALL]                  500m        192Mi
    │ postgres   70      true       true             [ALL]                  1           512Mi
    │ receiver   10001   true       true             [ALL]                  500m        192Mi
    $ kubectl -n record-consumers exec deployment/receiver -- touch /app/written
    │ touch: cannot touch '/app/written': Read-only file system
    $ kubectl -n record-consumers run as-root --image=hello-galaxy-record-consumers:local --overrides='{…runAsUser: 0…}'
    │ Error from server (Forbidden): pods "as-root" is forbidden: violates PodSecurity "restricted:latest": …
```

"No answer" is what a refused packet looks like from inside: the policy drops
it and nothing comes back.

## What this does and does not show

| Shown | Not shown |
|---|---|
| a NetworkPolicy is enforced in this cluster: kind's network plugin implements it | that your cluster enforces one. A cluster whose network plugin ignores NetworkPolicy accepts these manifests and enforces nothing; run this step's requests there |
| who may open a connection | who is asking. The receiver and the board do not authenticate a caller; a namespace or an address is the unit of the grant. Per-caller identity is what a goat fabric adds: see [`docs/00-which-consumer.md`](../../docs/00-which-consumer.md) |
| the Secret is referenced, never committed | a secret store. The step makes the Secret with `kubectl`; a deployment fills it from its own store |
| traffic inside the cluster | encryption of it. The services speak HTTP inside the cluster; the AKS overlay verifies the database's certificate |
