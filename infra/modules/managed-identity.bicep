@description('Azure region for all resources')
param location string

@description('Name prefix for all resources')
param environmentName string

@description('Resource ID of the Azure AI Search service')
param searchServiceId string

@description('Resource ID of the Azure OpenAI account')
param openAiAccountId string

@description('Resource ID of the Key Vault')
param keyVaultId string

@description('Resource ID of the Storage Account')
param storageAccountId string

// User-assigned managed identity
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${environmentName}-identity'
  location: location
}

// ── Role Definition IDs (built-in) ────────────────────────────────────────────
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var cognitiveServicesOpenAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

// ── Search Index Data Contributor ─────────────────────────────────────────────
resource searchIndexDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchServiceId, managedIdentity.id, searchIndexDataContributorRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Allows the managed identity to read/write Search indexes'
  }
}

// ── Cognitive Services OpenAI User ────────────────────────────────────────────
resource openAiUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccountId, managedIdentity.id, cognitiveServicesOpenAiUserRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Allows the managed identity to call OpenAI APIs'
  }
}

// ── Cognitive Services User (Document Intelligence) ───────────────────────────
resource cognitiveServicesUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccountId, managedIdentity.id, cognitiveServicesUserRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Allows the managed identity to use Cognitive Services (Document Intelligence)'
  }
}

// ── Key Vault Secrets User ────────────────────────────────────────────────────
resource keyVaultSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultId, managedIdentity.id, keyVaultSecretsUserRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Allows the managed identity to read Key Vault secrets'
  }
}

// ── Storage Blob Data Contributor ─────────────────────────────────────────────
resource storageBlobDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, managedIdentity.id, storageBlobDataContributorRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Allows the managed identity to read/write blobs for document ingestion'
  }
}

@description('Resource ID of the user-assigned managed identity')
output identityId string = managedIdentity.id

@description('Principal ID of the user-assigned managed identity (for role assignments)')
output principalId string = managedIdentity.properties.principalId

@description('Client ID of the user-assigned managed identity (for SDK auth)')
output clientId string = managedIdentity.properties.clientId
