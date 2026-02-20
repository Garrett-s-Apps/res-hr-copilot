@description('Azure region for all resources')
param location string

@description('Name prefix for all resources')
param environmentName string

@description('Resource ID of the user-assigned managed identity')
param managedIdentityId string

@description('Resource ID of the Log Analytics workspace for diagnostics')
param logAnalyticsWorkspaceId string

resource searchService 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name: '${environmentName}-search'
  location: location
  sku: {
    // S1 provides up to 50 indexes and 25 GB storage per partition — appropriate for HR knowledge base
    name: 'standard'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    // Semantic ranker enables LLM-quality relevance ranking at no extra infrastructure cost on S1+
    semanticSearch: 'standard'
    authOptions: {
      // Require AAD (managed identity) auth; disable API key auth for SOC 2 AC-3
      aadOrApiKey: {
        aadAuthFailureMode: 'http403'
      }
    }
  }
}

// Route all Search diagnostic logs and metrics to the central Log Analytics workspace
resource searchDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${environmentName}-search-diag'
  scope: searchService
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'OperationLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

@description('Resource ID of the Azure AI Search service')
output searchServiceId string = searchService.id

@description('Name of the Azure AI Search service')
output searchServiceName string = searchService.name

@description('HTTPS endpoint of the Azure AI Search service')
output searchEndpoint string = 'https://${searchService.name}.search.windows.net'
