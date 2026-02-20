#!/usr/bin/env bash
# deploy.sh — Full deployment script for RES HR Copilot infrastructure and functions
# Usage: ./scripts/deploy.sh [--resource-group <name>] [--location <region>] [--env <dev|prod>]
set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults (override with flags or environment variables)
# ---------------------------------------------------------------------------
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-res-hr-copilot}"
LOCATION="${LOCATION:-eastus2}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
FUNCTION_APP_NAME="${FUNCTION_APP_NAME:-func-res-hr-${ENVIRONMENT}}"
BICEP_FILE="infra/main.bicep"
PYTHON_VERSION="3.11"

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
    --location)       LOCATION="$2";       shift 2 ;;
    --env)            ENVIRONMENT="$2";    shift 2 ;;
    *) warn "Unknown argument: $1"; shift ;;
  esac
done

echo ""
echo "=================================================================="
echo "  RES HR Copilot — Deployment"
echo "  Resource Group : ${RESOURCE_GROUP}"
echo "  Location       : ${LOCATION}"
echo "  Environment    : ${ENVIRONMENT}"
echo "=================================================================="
echo ""

# ---------------------------------------------------------------------------
# Step 1: Check prerequisites
# ---------------------------------------------------------------------------
info "Checking prerequisites..."

check_command() {
  local cmd="$1"
  local install_hint="$2"
  if ! command -v "$cmd" &>/dev/null; then
    error "'$cmd' not found. $install_hint"
  fi
  success "$cmd found: $(command -v "$cmd")"
}

check_command az        "Install Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli"
check_command func      "Install Azure Functions Core Tools: npm install -g azure-functions-core-tools@4"
check_command python3   "Install Python 3.11+: https://www.python.org/downloads/"

# Verify Python version
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11 ]]; then
  error "Python 3.11+ required. Found: $(python3 --version)"
fi
success "Python version OK: $(python3 --version)"

# Verify Azure CLI is logged in
if ! az account show &>/dev/null; then
  error "Not logged in to Azure CLI. Run: az login"
fi
SUBSCRIPTION=$(az account show --query name -o tsv)
success "Azure CLI authenticated: subscription '${SUBSCRIPTION}'"

# ---------------------------------------------------------------------------
# Step 2: Ensure resource group exists
# ---------------------------------------------------------------------------
info "Ensuring resource group '${RESOURCE_GROUP}' exists in '${LOCATION}'..."
az group create \
  --name "${RESOURCE_GROUP}" \
  --location "${LOCATION}" \
  --output none
success "Resource group ready."

# ---------------------------------------------------------------------------
# Step 3: Deploy Bicep infrastructure
# ---------------------------------------------------------------------------
if [[ -f "${BICEP_FILE}" ]]; then
  info "Deploying Bicep infrastructure from ${BICEP_FILE}..."
  DEPLOY_OUTPUT=$(az deployment group create \
    --resource-group "${RESOURCE_GROUP}" \
    --template-file "${BICEP_FILE}" \
    --parameters \
      environment="${ENVIRONMENT}" \
      location="${LOCATION}" \
    --output json)

  SEARCH_ENDPOINT=$(echo "${DEPLOY_OUTPUT}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['properties']['outputs'].get('searchEndpoint',{}).get('value',''))" 2>/dev/null || echo "")
  OPENAI_ENDPOINT=$(echo "${DEPLOY_OUTPUT}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['properties']['outputs'].get('openaiEndpoint',{}).get('value',''))" 2>/dev/null || echo "")
  FUNCTION_APP_NAME=$(echo "${DEPLOY_OUTPUT}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['properties']['outputs'].get('functionAppName',{}).get('value','${FUNCTION_APP_NAME}'))" 2>/dev/null || echo "${FUNCTION_APP_NAME}")

  success "Bicep deployment complete."
  [[ -n "${SEARCH_ENDPOINT}" ]] && info "  Search endpoint : ${SEARCH_ENDPOINT}"
  [[ -n "${OPENAI_ENDPOINT}" ]] && info "  OpenAI endpoint : ${OPENAI_ENDPOINT}"
  [[ -n "${FUNCTION_APP_NAME}" ]] && info "  Function App    : ${FUNCTION_APP_NAME}"
else
  warn "Bicep file '${BICEP_FILE}' not found — skipping infrastructure deployment."
  warn "Run this step manually or create infra/main.bicep before deploying."
fi

# ---------------------------------------------------------------------------
# Step 4: Install Python dependencies
# ---------------------------------------------------------------------------
info "Installing Python dependencies for scripts..."
if [[ -f "requirements.txt" ]]; then
  python3 -m pip install -q -r requirements.txt
  success "Python dependencies installed."
else
  warn "No requirements.txt found — skipping pip install."
fi

# ---------------------------------------------------------------------------
# Step 5: Create Azure AI Search index
# ---------------------------------------------------------------------------
info "Creating/updating Azure AI Search index..."
if python3 scripts/create-search-index.py; then
  success "Search index created/updated."
else
  error "Search index creation failed. Check scripts/create-search-index.py output above."
fi

# ---------------------------------------------------------------------------
# Step 6: Deploy Azure Functions
# ---------------------------------------------------------------------------
if command -v func &>/dev/null && [[ -f "host.json" ]]; then
  info "Deploying Azure Functions to '${FUNCTION_APP_NAME}'..."
  func azure functionapp publish "${FUNCTION_APP_NAME}" \
    --python \
    --build remote
  success "Azure Functions deployed."
else
  warn "No host.json found or func CLI missing — skipping Functions deployment."
fi

# ---------------------------------------------------------------------------
# Post-deployment checklist
# ---------------------------------------------------------------------------
echo ""
echo "=================================================================="
echo -e "${GREEN}  Deployment Complete${NC}"
echo "=================================================================="
echo ""
echo "Post-deployment checklist:"
echo ""
echo "  [ ] 1. Verify Azure AI Search indexer has run:"
echo "         az search indexer run --name hr-indexer --service-name <search-service> -g ${RESOURCE_GROUP}"
echo ""
echo "  [ ] 2. Validate security trimming:"
echo "         python3 scripts/validate-permissions.py --user <user-oid> --expected-docs 'Employee Handbook'"
echo ""
echo "  [ ] 3. Open Copilot Studio and connect the knowledge source:"
echo "         https://copilotstudio.microsoft.com"
echo "         See copilot/README.md for full setup instructions."
echo ""
echo "  [ ] 4. Import Copilot topics from copilot/topics/*.yaml"
echo ""
echo "  [ ] 5. Publish the agent to Microsoft Teams"
echo ""
echo "  [ ] 6. Send a test message: 'What is our PTO policy?'"
echo ""
echo "  [ ] 7. Confirm Application Insights is receiving hr_copilot_feedback events"
echo ""
echo "  [ ] 8. Run the full test suite:"
echo "         pytest tests/ -v"
echo ""
