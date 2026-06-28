#!/bin/bash
# Check that required SST secrets are set before deployment
# Usage: ./scripts/check-secrets.sh <stage>

set -e

STAGE=${1:-staging}
MISSING_SECRETS=()

echo "Checking required secrets for stage: $STAGE"

# List of required secrets
REQUIRED_SECRETS=(
    "SecretKey"
    "SlFirebaseCredentials"
)

# Optional secrets (warn if missing, don't fail)
OPTIONAL_SECRETS=(
    "SlSendgridApiKey"
    "GarminClientId"
    "GarminClientSecret"
    "FitbitClientId"
    "FitbitClientSecret"
)

# Get list of configured secrets (format: SecretName=value)
CONFIGURED_SECRETS=$(npx sst secret list --stage "$STAGE" 2>/dev/null | grep -E "^[A-Za-z]" | cut -d'=' -f1 || echo "")

check_secret() {
    local secret_name=$1
    if echo "$CONFIGURED_SECRETS" | grep -q "^${secret_name}$"; then
        return 0
    else
        return 1
    fi
}

# Check required secrets
echo ""
echo "Required secrets:"
for secret in "${REQUIRED_SECRETS[@]}"; do
    if check_secret "$secret"; then
        echo "  ✓ $secret"
    else
        echo "  ✗ $secret (MISSING)"
        MISSING_SECRETS+=("$secret")
    fi
done

# Check optional secrets
echo ""
echo "Optional secrets:"
for secret in "${OPTIONAL_SECRETS[@]}"; do
    if check_secret "$secret"; then
        echo "  ✓ $secret"
    else
        echo "  - $secret (not set)"
    fi
done

# Exit with error if required secrets are missing
if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo ""
    echo "ERROR: Missing required secrets. Set them with:"
    echo ""
    for secret in "${MISSING_SECRETS[@]}"; do
        case $secret in
            "SecretKey")
                echo "  npx sst secret set SecretKey \"\$(openssl rand -hex 32)\" --stage $STAGE"
                ;;
            "SlFirebaseCredentials")
                echo "  npx sst secret set SlFirebaseCredentials '\$(cat path/to/firebase-credentials.json)' --stage $STAGE"
                ;;
            *)
                echo "  npx sst secret set $secret \"<value>\" --stage $STAGE"
                ;;
        esac
    done
    echo ""
    exit 1
fi

echo ""
echo "All required secrets are configured!"
