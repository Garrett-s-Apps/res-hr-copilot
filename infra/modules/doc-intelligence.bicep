@description('Azure region for all resources')
param location string

@description('Name prefix for all resources')
param environmentName string

@description('Resource ID of the user-assigned managed identity')
param managedIdentityId string

// Azure AI Document Intelligence (formerly Form Recognizer) — extracts structured
// content from HR documents (PDFs, Word, scanned forms) for indexing
resource docIntelligence 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: '${environmentName}-docintel'
  location: location
  // FormRecognizer kind targets the Document Intelligence API surface
  kind: 'FormRecognizer'
  sku: {
    // S0 is the standard paid tier; F0 (free) is limited to 500 pages/month
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
    // Disable key-based auth — managed identity enforces least-privilege (SOC 2 IA-2)
    disableLocalAuth: true
    customSubDomainName: '${environmentName}-docintel'
  }
}

@description('Resource ID of the Document Intelligence account')
output docIntelligenceId string = docIntelligence.id

@description('Name of the Document Intelligence account')
output docIntelligenceName string = docIntelligence.name

@description('HTTPS endpoint of the Document Intelligence account')
output docIntelligenceEndpoint string = docIntelligence.properties.endpoint
