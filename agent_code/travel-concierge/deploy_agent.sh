#!/bin/bash

# Exit immediately if a command exits with a non-zero status,
# unless the command is part of a conditional test in an if statement.
set -e

# --- Configuration ---
# The path to your deployment script relative to the project root
DEPLOY_SCRIPT_PATH="deployment/deploy.py"

# --- Script Start ---
echo "Starting agent deployment process..."
echo

# 1. Install dependencies using Poetry, including the 'deployment' group.
#    PYTHON_KEYRING_BACKEND is set to bypass potential system keyring issues.
echo "[Step 1/4] Installing dependencies (including 'deployment' group)..."
if PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry install -v --with deployment; then
    echo "Dependencies installed successfully."
else
    echo "ERROR: Poetry install failed. Please check the output above."
    exit 1
fi
echo

# 2. Get input from the user for resource_id.
echo "[Step 2/4] Getting deployment parameters..."
read -r -p "Please enter the resource_id for deployment (leave blank to skip and attempt creation directly): " resource_id
echo

# 3. Attempt to deploy/test with the provided resource_id (if any).
if [[ -n "$resource_id" ]]; then
    echo "[Step 3/4] Attempting to deploy/test with provided resource_id: ${resource_id}..."
    if PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry run python "${DEPLOY_SCRIPT_PATH}" --quicktest --resource_id="${resource_id}"; then
        echo "Deployment/test with provided resource_id successful."
        echo
        echo "Agent deployment process finished."
        exit 0 # Successful completion
    else
        echo "WARNING: Deployment/test with provided resource_id (${resource_id}) failed."
        echo "Proceeding to create a new resource as a fallback..."
        # No exit here, will proceed to the creation step.
    fi
else
    echo "[Step 3/4] No resource_id provided. Proceeding directly to create a new resource..."
fi
echo

# 4. Create a new resource (either as a fallback or if no resource_id was provided).
echo "[Step 4/4] Creating new resource..."
if PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry run python "${DEPLOY_SCRIPT_PATH}" --create; then
    echo "Resource creation successful."
    echo "INFO: A new resource was created by 'python ${DEPLOY_SCRIPT_PATH} --create'."
    echo "You may need to identify and use the new resource_id from its output for future commands or configurations."
else
    echo "ERROR: Resource creation also failed. Please check the output above."
    exit 1
fi

echo
echo "Agent deployment process finished."
