@description('Azure region for all resources')
param location string

@description('Name prefix for all resources')
param environmentName string

@description('Resource ID of the user-assigned managed identity')
param managedIdentityId string

@description('Resource ID of the Log Analytics workspace for diagnostics')
param logAnalyticsWorkspaceId string

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: '${environmentName}-openai'
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    // Disable local (key-based) auth — all callers must use managed identity (SOC 2 IA-2)
    disableLocalAuth: true
    customSubDomainName: '${environmentName}-openai'
  }
}

// text-embedding-3-small: efficient embedding model for document chunking and query encoding
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAiAccount
  name: 'text-embedding-3-small'
  sku: {
    name: 'Standard'
    // 120K TPM handles concurrent document ingestion and real-time query embedding
    capacity: 120
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

// gpt-4o-mini: cost-effective chat model for HR Q&A — strong reasoning at lower token cost
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAiAccount
  name: 'gpt-4o-mini'
  // Deployments must be created sequentially — capacity pool is shared
  dependsOn: [embeddingDeployment]
  sku: {
    name: 'Standard'
    // 200K TPM supports concurrent HR Copilot sessions without throttling
    capacity: 200
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

resource openAiDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${environmentName}-openai-diag'
  scope: openAiAccount
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'Audit'
        enabled: true
      }
      {
        category: 'RequestResponse'
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

@description('Resource ID of the Azure OpenAI account')
output openAiAccountId string = openAiAccount.id

@description('Name of the Azure OpenAI account')
output openAiAccountName string = openAiAccount.name

@description('HTTPS endpoint of the Azure OpenAI account')
output openAiEndpoint string = openAiAccount.properties.endpoint
