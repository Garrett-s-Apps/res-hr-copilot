@description('Azure region for all resources')
param location string

@description('Name prefix for all resources')
param environmentName string

@description('Resource ID of the user-assigned managed identity')
param managedIdentityId string

@description('Client ID of the user-assigned managed identity (for AZURE_CLIENT_ID env var)')
param managedIdentityClientId string

@description('Name of the storage account used as the Functions runtime backing store')
param storageAccountName string

@description('HTTPS endpoint of the Azure AI Search service')
param searchEndpoint string

@description('HTTPS endpoint of the Azure OpenAI account')
param openAiEndpoint string

@description('HTTPS endpoint of the Document Intelligence account')
param docIntelligenceEndpoint string

@description('URI of the Key Vault (used to build secret reference URIs)')
param keyVaultUri string

@description('Application Insights instrumentation key')
param appInsightsInstrumentationKey string

@description('Application Insights connection string')
param appInsightsConnectionString string

// Consumption plan (Y1) — pay-per-execution with automatic scale-out; no idle cost
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${environmentName}-plan'
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'functionapp'
  properties: {
    reserved: true  // required for Linux runtime
  }
}

// Existing storage account reference — AzureWebJobsStorage connection string resolved from name
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: '${environmentName}-func'
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      functionAppScaleLimit: 200
      minimumElasticInstanceCount: 0
      // Key Vault references use @Microsoft.KeyVault(SecretUri=...) syntax;
      // the managed identity must have Key Vault Secrets User on the vault
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          // SharedKey connection for the Functions host runtime internal use
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        // Explicitly set the client ID so the DefaultAzureCredential picks the right identity
        // when multiple user-assigned identities could theoretically be attached
        {
          name: 'AZURE_CLIENT_ID'
          value: managedIdentityClientId
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: searchEndpoint
        }
        {
          name: 'AZURE_SEARCH_INDEX_NAME'
          value: 'hr-knowledge-index'
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: openAiEndpoint
        }
        {
          name: 'OPENAI_EMBEDDING_DEPLOYMENT'
          value: 'text-embedding-3-small'
        }
        {
          name: 'OPENAI_CHAT_DEPLOYMENT'
          value: 'gpt-4o-mini'
        }
        {
          name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'
          value: docIntelligenceEndpoint
        }
        {
          name: 'SHAREPOINT_TENANT_ID'
          // Key Vault reference — resolved at runtime by the Functions host using the managed identity
          value: '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/SHAREPOINT-TENANT-ID/)'
        }
        {
          name: 'SHAREPOINT_CLIENT_ID'
          value: '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/SHAREPOINT-CLIENT-ID/)'
        }
        {
          name: 'SHAREPOINT_CLIENT_SECRET'
          value: '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/SHAREPOINT-CLIENT-SECRET/)'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsightsInstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'ApplicationInsightsAgent_EXTENSION_VERSION'
          value: '~3'
        }
      ]
    }
  }
}

@description('Resource ID of the Function App')
output functionAppId string = functionApp.id

@description('Default hostname of the Function App')
output functionAppHostname string = functionApp.properties.defaultHostName

@description('Name of the Function App')
output functionAppName string = functionApp.name
