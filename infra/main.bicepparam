using 'main.bicep'

// Azure region — eastus has the broadest Azure OpenAI model availability
param location = 'eastus'

// Used as prefix for every resource name (e.g., res-hr-prod-search, res-hr-prod-kv).
// Must be 3–20 characters, lowercase alphanumeric and hyphens only.
param environmentName = 'res-hr-prod'

// AAD tenant ID for the target subscription.
// Find it: az account show --query tenantId -o tsv
param tenantId = '' // TODO: fill in before deploying
