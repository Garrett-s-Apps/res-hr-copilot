targetScope = 'resourceGroup'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name used as a prefix for all resource names')
@minLength(3)
@maxLength(20)
param environmentName string

@description('AAD tenant ID — required for Key Vault configuration')
param tenantId string

// ── Storage ───────────────────────────────────────────────────────────────────
// No dependencies — deployed first. Provides the Functions runtime backing store
// and a resource ID for the managed identity Storage Blob Data Contributor assignment.
module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    environmentName: environmentName
  }
}

// ── Key Vault ─────────────────────────────────────────────────────────────────
// No dependencies — deployed independently. The Key Vault Secrets User role
// assignment for the managed identity is made inside managed-identity.bicep
// (after both the vault and identity exist), avoiding a circular reference.
module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault'
  params: {
    location: location
    environmentName: environmentName
    tenantId: tenantId
  }
}

// ── Monitoring ────────────────────────────────────────────────────────────────
// No dependencies — Log Analytics workspace and App Insights deployed early so
// Search and OpenAI can reference the workspace ID for diagnostic settings.
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    environmentName: environmentName
  }
}

// ── Search ────────────────────────────────────────────────────────────────────
// Depends on: managedIdentity (identity attachment), monitoring (diagnostics)
module search 'modules/search.bicep' = {
  name: 'search'
  params: {
    location: location
    environmentName: environmentName
    managedIdentityId: managedIdentity.outputs.identityId
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
  }
}

// ── Azure OpenAI ──────────────────────────────────────────────────────────────
// Depends on: managedIdentity (identity attachment), monitoring (diagnostics)
module openAi 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    location: location
    environmentName: environmentName
    managedIdentityId: managedIdentity.outputs.identityId
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
  }
}

// ── Document Intelligence ─────────────────────────────────────────────────────
// Depends on: managedIdentity (identity attachment)
module docIntelligence 'modules/doc-intelligence.bicep' = {
  name: 'doc-intelligence'
  params: {
    location: location
    environmentName: environmentName
    managedIdentityId: managedIdentity.outputs.identityId
  }
}

// ── Managed Identity + Role Assignments ──────────────────────────────────────
// Depends on: storage, keyVault (resource IDs for scoped role assignments).
// Search and OpenAI resource IDs are also needed for their role assignments —
// Bicep sees those as forward references and deploys managed-identity after them.
// Circular risk is eliminated because keyVault no longer takes a principalId param.
module managedIdentity 'modules/managed-identity.bicep' = {
  name: 'managed-identity'
  params: {
    location: location
    environmentName: environmentName
    searchServiceId: search.outputs.searchServiceId
    openAiAccountId: openAi.outputs.openAiAccountId
    keyVaultId: keyVault.outputs.keyVaultId
    storageAccountId: storage.outputs.storageAccountId
  }
}

// ── Function App ──────────────────────────────────────────────────────────────
// Last in the graph — depends on every other module's outputs.
module functionApp 'modules/function-app.bicep' = {
  name: 'function-app'
  params: {
    location: location
    environmentName: environmentName
    managedIdentityId: managedIdentity.outputs.identityId
    managedIdentityClientId: managedIdentity.outputs.clientId
    storageAccountName: storage.outputs.storageAccountName
    searchEndpoint: search.outputs.searchEndpoint
    openAiEndpoint: openAi.outputs.openAiEndpoint
    docIntelligenceEndpoint: docIntelligence.outputs.docIntelligenceEndpoint
    keyVaultUri: keyVault.outputs.keyVaultUri
    appInsightsInstrumentationKey: monitoring.outputs.appInsightsInstrumentationKey
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
  }
}

// ── Stack Outputs ─────────────────────────────────────────────────────────────

@description('HTTPS endpoint of the Azure AI Search service')
output searchEndpoint string = search.outputs.searchEndpoint

@description('HTTPS endpoint of the Azure OpenAI account')
output openAiEndpoint string = openAi.outputs.openAiEndpoint

@description('HTTPS endpoint of the Document Intelligence account')
output docIntelligenceEndpoint string = docIntelligence.outputs.docIntelligenceEndpoint

@description('URI of the Key Vault')
output keyVaultUri string = keyVault.outputs.keyVaultUri

@description('Default hostname of the Function App')
output functionAppHostname string = functionApp.outputs.functionAppHostname

@description('Client ID of the user-assigned managed identity')
output managedIdentityClientId string = managedIdentity.outputs.clientId

@description('Application Insights connection string')
output appInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
