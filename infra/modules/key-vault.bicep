@description('Azure region for all resources')
param location string

@description('Name prefix for all resources')
param environmentName string

@description('AAD tenant ID for the Key Vault')
param tenantId string

// The Key Vault Secrets User role assignment for the managed identity lives in
// managed-identity.bicep alongside all other role assignments. Keeping it there
// avoids a circular dependency: key-vault <- managed-identity <- key-vault.
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${environmentName}-kv'
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    // Pure RBAC model — no legacy access policies — aligns with SOC 2 AC-2
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

@description('Resource ID of the Key Vault')
output keyVaultId string = keyVault.id

@description('URI of the Key Vault (used to build secret reference URIs)')
output keyVaultUri string = keyVault.properties.vaultUri

@description('Name of the Key Vault')
output keyVaultName string = keyVault.name
