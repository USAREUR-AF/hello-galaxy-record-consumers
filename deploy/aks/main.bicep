// An AKS cluster, a container registry and a managed PostgreSQL server for
// hello-galaxy-record-consumers. Every name is derived from a parameter;
// nothing here names a real deployment. This file has been built with
// `bicep build` and has not been deployed.
//
//   az group create --name <group> --location <location>
//   az deployment group create --resource-group <group> --template-file deploy/aks/main.bicep \
//     --parameters namePrefix=<prefix> postgresAdminPassword=<from your secret store>
//
// What it makes:
//   * a virtual network with one subnet for the cluster and one delegated to PostgreSQL;
//   * PostgreSQL Flexible Server with private access only (no public endpoint), and the database `records`;
//   * a container registry with the admin user off, which the cluster's kubelet identity may pull from;
//   * an AKS cluster with a managed identity and NetworkPolicy enforced (Azure CNI overlay with Cilium).

@description('Region for every resource.')
param location string = resourceGroup().location

@description('Lower-case letters and digits; the start of every resource name.')
@minLength(3)
@maxLength(12)
param namePrefix string

@description('Kubernetes version; empty takes the region default.')
param kubernetesVersion string = ''

@description('Number of nodes in the one node pool.')
@minValue(1)
@maxValue(10)
param nodeCount int = 2

@description('Virtual machine size of the nodes.')
param nodeVmSize string = 'Standard_D2s_v5'

@description('Address space of the virtual network.')
param virtualNetworkPrefix string = '10.20.0.0/16' // opsec-allow: a private range chosen as a default; it names no network

@description('Subnet of the cluster nodes.')
param clusterSubnetPrefix string = '10.20.0.0/22' // opsec-allow: a private range chosen as a default; it names no network

@description('Subnet delegated to PostgreSQL. The aks overlay allows egress to this range on port 5432.')
param postgresSubnetPrefix string = '10.20.4.0/24' // opsec-allow: a private range chosen as a default; it names no network

@description('PostgreSQL major version.')
param postgresVersion string = '17'

@description('PostgreSQL compute size.')
param postgresSkuName string = 'Standard_B1ms'

@description('PostgreSQL compute tier.')
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param postgresSkuTier string = 'Burstable'

@description('PostgreSQL storage in GiB.')
param postgresStorageGb int = 32

@description('Administrator login of the PostgreSQL server. Used once, to create the roles receiver and board.')
param postgresAdminLogin string = 'recordsadmin'

@description('Administrator password. Pass it at deployment time from a secret store; it has no default and is never written to a file.')
@secure()
param postgresAdminPassword string

var suffix = uniqueString(resourceGroup().id, namePrefix)
var registryName = '${namePrefix}${suffix}'
var postgresName = '${namePrefix}-pg-${suffix}'
var privateZoneName = '${namePrefix}.private.postgres.database.azure.com'
// The built-in role AcrPull.
var acrPullRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource network 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${namePrefix}-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [virtualNetworkPrefix]
    }
    subnets: [
      {
        name: 'cluster'
        properties: {
          addressPrefix: clusterSubnetPrefix
        }
      }
      {
        name: 'postgres'
        properties: {
          addressPrefix: postgresSubnetPrefix
          delegations: [
            {
              name: 'postgres'
              properties: {
                serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers'
              }
            }
          ]
        }
      }
    ]
  }
}

resource privateZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateZoneName
  location: 'global'
}

resource privateZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateZone
  name: '${namePrefix}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: network.id
    }
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresName
  location: location
  sku: {
    name: postgresSkuName
    tier: postgresSkuTier
  }
  properties: {
    version: postgresVersion
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    storage: {
      storageSizeGB: postgresStorageGb
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    network: {
      delegatedSubnetResourceId: network.properties.subnets[1].id
      privateDnsZoneArmResourceId: privateZone.id
      publicNetworkAccess: 'Disabled'
    }
  }
  dependsOn: [
    privateZoneLink
  ]
}

resource recordsDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: 'records'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource cluster 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: '${namePrefix}-aks'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: namePrefix
    kubernetesVersion: empty(kubernetesVersion) ? null : kubernetesVersion
    enableRBAC: true
    disableLocalAccounts: true
    aadProfile: {
      managed: true
      enableAzureRBAC: true
    }
    agentPoolProfiles: [
      {
        name: 'system'
        mode: 'System'
        count: nodeCount
        vmSize: nodeVmSize
        osType: 'Linux'
        osSKU: 'AzureLinux'
        vnetSubnetID: network.properties.subnets[0].id
      }
    ]
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      networkDataplane: 'cilium'
      networkPolicy: 'cilium'
      podCidr: '10.244.0.0/16' // opsec-allow: a private range chosen as a default; it names no network
      serviceCidr: '10.96.0.0/16' // opsec-allow: a private range chosen as a default; it names no network
      dnsServiceIP: '10.96.0.10' // opsec-allow: a private range chosen as a default; it names no network
    }
  }
}

resource kubeletMayPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, cluster.id, acrPullRoleId)
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: cluster.properties.identityProfile.kubeletidentity.objectId
    principalType: 'ServicePrincipal'
  }
}

@description('Push the image here: az acr login, docker tag, docker push.')
output registryLoginServer string = registry.properties.loginServer

@description('PGHOST for deploy/overlays/aks/kustomization.yaml.')
output postgresHost string = postgres.properties.fullyQualifiedDomainName

@description('az aks get-credentials --name <this> --resource-group <group>')
output clusterName string = cluster.name

@description('The range the aks overlay allows the consumers to reach on port 5432.')
output postgresSubnet string = postgresSubnetPrefix
