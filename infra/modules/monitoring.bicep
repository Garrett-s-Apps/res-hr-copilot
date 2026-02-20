@description('Azure region for all resources')
param location string

@description('Name prefix for all resources')
param environmentName string

// Log Analytics workspace — central sink for diagnostics from all resources
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${environmentName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    // 30-day retention balances cost with SOC 2 audit trail requirements
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// Application Insights workspace-based instance — telemetry from the Function App
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${environmentName}-appinsights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    // Workspace-based mode sends telemetry into Log Analytics for unified querying
    WorkspaceResourceId: logAnalyticsWorkspace.id
    RetentionInDays: 30
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

@description('Resource ID of the Log Analytics workspace')
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id

@description('Resource ID of the Application Insights instance')
output appInsightsId string = appInsights.id

@description('Instrumentation key for the Application Insights instance')
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey

@description('Connection string for the Application Insights instance')
output appInsightsConnectionString string = appInsights.properties.ConnectionString
