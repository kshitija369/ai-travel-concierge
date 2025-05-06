#!/bin/bash

# Exit immediately if a command exits with a non-zero status,
# unless the command is part of a conditional test in an if statement.
set -e

# --- Configuration ---
# Path to your deployment script relative to the project root
DEPLOY_SCRIPT_PATH="deployment/deploy.py"
# The python interpreter poetry run should use (poetry usually figures this out, 'python' is fine)
PYTHON_CMD="python3"

# --- Script Start ---
echo "Agent Resource Deletion Script"
echo "------------------------------"
echo

# 1. Prompt the user for the RESOURCE_ID
read -r -p "Please enter the RESOURCE_ID of the agent resource to delete: " resource_id

# Check if the input is empty
if [[ -z "$resource_id" ]]; then
    echo "ERROR: No RESOURCE_ID entered. Aborting deletion."
    exit 1
fi

echo
echo "You are about to delete the resource with ID: ${resource_id}"
read -r -p "Are you sure you want to continue? (yes/no): " confirmation

if [[ "$confirmation" != "yes" ]]; then
    echo "Deletion aborted by user."
    exit 0
fi

echo
echo "Proceeding with deletion of resource: ${resource_id}..."

# 2. Execute the delete command
#    - Using 'poetry run' to ensure the script executes in the correct Poetry environment.
#    - Setting 'PYTHON_KEYRING_BACKEND' to prevent potential keyring hangs.
if PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring poetry run "${PYTHON_CMD}" "${DEPLOY_SCRIPT_PATH}" --delete --resource_id="${resource_id}"; then
    echo "Deletion command for resource '${resource_id}' executed successfully."
    echo "Please check the output from the script above for specific details."
else
    echo "ERROR: Deletion command failed for resource '${resource_id}'."
    echo "Please check the output from the script above for error details."
    exit 1
fi

echo
echo "Resource deletion process finished."
