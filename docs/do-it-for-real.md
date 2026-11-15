# Doing it for real

The steps run on one machine with a simulated source and a local cluster.
This page is what changes in a deployment. None of it was run from this
repository.

| Here | For real |
|---|---|
| the decoder is a Job replaying a capture | first-bite beside the tap, as a service: first-bite [deployment.md](https://github.com/USAREUR-AF/first-bite/blob/main/docs/deployment.md), [tap.md](https://github.com/USAREUR-AF/first-bite/blob/main/docs/tap.md) |
| the dictionary is the invented harbour buoy | your dictionary; give the receiver `bite schema <your dictionary>` as the ConfigMap `record-schema` and set `SOURCE_FIELDS` |
| a kind cluster | your cluster; first confirm its network plugin enforces NetworkPolicy by running step 4's requests |
| PostgreSQL in the cluster on a 1 GiB volume, no backup | a managed server, or one you back up |
| the Secret made with `kubectl` from random values | the Secret filled from your secret store |
| HTTP between the decoder and the receiver | HTTPS: put the receiver behind your ingress with a certificate; first-bite's `rest` sink verifies it when `endpoint_url` starts `https://` |
| one replica of each service | more receivers behind the Service are safe: each request is one insert. Start one first so that a new table is made once |

## A dictionary restates its interface document

The schema file, the tables made from it and the rows are as sensitive as the
document the dictionary was transcribed from. Keep the schema ConfigMap, the
database and its backups where that document may be kept. The dictionary and
samples here are invented so that they can be published.

## AKS, in commands

```bash
az group create --name <group> --location <location>
az deployment group create --resource-group <group> --template-file deploy/aks/main.bicep \
  --parameters namePrefix=<prefix> postgresAdminPassword=<from your secret store>
az acr login --name <registry>
docker build -f app/Dockerfile -t <registryLoginServer>/hello-galaxy-record-consumers:<tag> .
docker push <registryLoginServer>/hello-galaxy-record-consumers:<tag>
az aks get-credentials --name <clusterName> --resource-group <group>
# as the database administrator, from a machine inside the virtual network: the statements of
# deploy/overlays/local/postgres/init-roles.sh, with a password each for receiver and board
kubectl apply -f deploy/base/namespace.yaml
kubectl -n record-consumers create secret generic record-consumers-db \
  --from-literal=receiver-password=<…> --from-literal=board-password=<…>
kubectl apply -k deploy/overlays/aks
```

Then run the requests of step 4 against the cluster, and point the decoder's
`rest` sink at the receiver's load-balancer address.
