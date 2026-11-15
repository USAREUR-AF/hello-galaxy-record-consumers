# Step 5 — the AKS path

**Checked, not deployed.** The Bicep file builds and the `aks` overlay
renders; nothing here has been applied to an Azure subscription, and the step
contacts none.

| File | Makes |
|---|---|
| [`deploy/aks/main.bicep`](../../deploy/aks/main.bicep) | a virtual network; an AKS cluster with a managed identity and NetworkPolicy enforced; a container registry the cluster may pull from; PostgreSQL Flexible Server with private access only, and the database `records` |
| [`deploy/overlays/aks/`](../../deploy/overlays/aks) | the base with the image in the registry, the database's host name and certificate verification, the receiver behind an internal load balancer, and NetworkPolicies by address: the decoder's range may post, the consumers may reach the database's subnet |

Every name in the Bicep file comes from the parameter `namePrefix`. The
database administrator's password is a `@secure()` parameter with no default:
it is passed at deployment time and is in no file. The addresses in the
overlay are documentation ranges, each marked `# yours`.

```bash
bin/hello-consumers 5-aks
```

## What you should see

```text
[1] Build the Bicep file
    $ bicep build deploy/aks/main.bicep --outfile .run/5-main.json
    │ resources:
    │   Microsoft.Network/virtualNetworks
    │   Microsoft.Network/privateDnsZones
    │   Microsoft.Network/privateDnsZones/virtualNetworkLinks
    │   Microsoft.DBforPostgreSQL/flexibleServers
    │   Microsoft.DBforPostgreSQL/flexibleServers/databases
    │   Microsoft.ContainerRegistry/registries
    │   Microsoft.ContainerService/managedClusters
    │   Microsoft.Authorization/roleAssignments
    │ parameters: 14 of which secure: postgresAdminPassword
    │ secure parameters with a default: 0
    │ required at deployment: namePrefix, postgresAdminPassword

[2] Render the aks overlay
    $ kubectl kustomize deploy/overlays/aks
    │       3 kind: ConfigMap
    │       2 kind: Deployment
    │       1 kind: Namespace
    │       6 kind: NetworkPolicy
    │       2 kind: Service
    │ cidr: 203.0.113.16/28
    │ externalTrafficPolicy: Local
    │ image: example.azurecr.io/hello-galaxy-record-consumers:0.1.0
    │ PGHOST: records.example.private.postgres.database.azure.com
    │ PGSSLMODE: verify-full
    │ service.beta.kubernetes.io/azure-load-balancer-internal: "true"
    │ type: LoadBalancer
```

## The order of a deployment

Not run from this repository. [`docs/do-it-for-real.md`](../../docs/do-it-for-real.md)
has each command.

1. Deploy `main.bicep` to a resource group, giving `namePrefix` and the administrator password.
2. Build the consumer image, push it to the registry the deployment made.
3. Connect to the database as the administrator once and create the roles `receiver` and `board` with the statements of [`init-roles.sh`](../../deploy/overlays/local/postgres/init-roles.sh).
4. Put the three outputs and the decoder's address range into `deploy/overlays/aks/`.
5. Create the Secret `record-consumers-db` with the keys `receiver-password` and `board-password` from your secret store.
6. `kubectl apply -k deploy/overlays/aks`, then run step 4's requests against it.
7. Point the decoder's `rest` sink at the load balancer's address.
