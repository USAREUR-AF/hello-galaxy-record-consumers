# Which consumer?

first-bite decodes once and publishes a record per message. What reads the
records is a separate choice, and more than one can run at once. Reading the
data is something its owner grants in every case; what differs is the unit of
the grant and what enforces it.

| You want | Use | The grant is | Shown in |
|---|---|---|---|
| records in a database of your own, and a status page, inside one organisation's cluster | a cluster consumer: first-bite's `rest` sink posting to a receiver | a namespace label or an address range, a database role, a Secret; enforced by NetworkPolicy and PostgreSQL | this repository |
| records available to other organisations, each under its own identity, with no service of yours in the read path | a goat subscriber: first-bite's `goat` sink publishing on a goatnet | a certificate the goatnet issues and the router's access rules, per key prefix | [hello-galaxy-first-bite, step 4](https://github.com/USAREUR-AF/hello-galaxy-first-bite/tree/main/steps/4-fabric) |
| positions on a map display | Cursor-on-Target from first-bite's `cot` transform, forwarded to a TAK server | whatever the TAK server enforces | [hello-galaxy-first-bite, step 5](https://github.com/USAREUR-AF/hello-galaxy-first-bite/tree/main/steps/5-cot) |
| records kept as files | first-bite's object-storage or local-file sink | the bucket's or the file system's access rules | first-bite [`flow/config/README.md`](https://github.com/USAREUR-AF/first-bite/blob/main/flow/config/README.md) |

## Cluster consumer or goat subscriber

| | Cluster consumer (here) | Goat subscriber |
|---|---|---|
| The decoder sends to | one URL, over HTTP | a Zenoh router, over mutual TLS |
| A consumer is | a service you run that the decoder is configured to post to | any holder of a certificate that subscribes to a key |
| Adding a consumer | another sink in the decoder's configuration, or a reader of the same database | nothing changes at the decoder |
| Who the caller is | not known to the receiver: a namespace or an address is admitted | the certificate's common name, on every write |
| Schema travels | as a file you give the receiver | declared on the fabric beside the data |
| Fits | one team, one cluster, data that stays there | data shared across teams and organisations |

## The same receiver on a goat fabric

Not built here. The receiver's storing half
([`records.py`](../app/record_consumers/records.py),
[`store.py`](../app/record_consumers/store.py)) takes a record as a Python
object and does not care how it arrived. A goat subscriber would replace the
HTTP half with a Zenoh subscription on
`<prefix>/telemetry/<format>/<site>/**` under a certificate the goatnet
issued, and could read the schema from `attest/schema/<record key>` instead of
a file. hello-galaxy-first-bite step 4 shows the publishing side and a
subscriber receiving the records.
