@description('Azure region for all resources')
param location string

@description('Name prefix for all resources')
param environmentName string

// Storage account name must be globally unique, lowercase, 3-24 chars
var storageAccountName = 'st${replace(toLower(environmentName), '-', '')}func'

// Standard LRS storage account used as the Azure Functions runtime backing store
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: length(storageAccountName) > 24 ? substring(storageAccountName, 0, 24) : storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    // Require HTTPS for all traffic — SOC 2 CC6.1
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true  // Functions runtime requires shared key for AzureWebJobsStorage
    accessTier: 'Hot'
    encryption: {
      services: {
        blob: { enabled: true }
        file: { enabled: true }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

@description('Resource ID of the storage account')
output storageAccountId string = storageAccount.id

@description('Name of the storage account')
output storageAccountName string = storageAccount.name
