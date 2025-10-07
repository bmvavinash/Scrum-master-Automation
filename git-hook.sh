#!/bin/bash

# Git hook script to update Jira card status based on branch name
# This script can be used as a post-commit hook or called manually

# Configuration
API_BASE_URL="http://localhost:8000/api/v1"
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
GIT_ACTION="push"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Git Hook: Updating Jira card for branch '${BRANCH_NAME}'${NC}"

# Extract Jira key from branch name
# Pattern: PROJECT-NUMBER (e.g., SCRUM-25)
JIRA_KEY=$(echo "$BRANCH_NAME" | grep -oE '[A-Z]+-[0-9]+')

if [ -z "$JIRA_KEY" ]; then
    echo -e "${YELLOW}No Jira key found in branch name '${BRANCH_NAME}'${NC}"
    echo "Branch name should contain a Jira key like SCRUM-25"
    echo "Examples: feature/SCRUM-25, bugfix/SCRUM-123, SCRUM-456"
    exit 0
fi

echo -e "${YELLOW}Found Jira key: ${JIRA_KEY}${NC}"

# Call the API to update Jira card status
RESPONSE=$(curl -s -X POST \
    "${API_BASE_URL}/git-hooks/update-from-branch" \
    -H "Content-Type: application/json" \
    -d "{\"branch_name\": \"${BRANCH_NAME}\", \"git_action\": \"${GIT_ACTION}\"}")

# Check if the API call was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Successfully updated Jira card ${JIRA_KEY}${NC}"
    echo "Response: $RESPONSE"
else
    echo -e "${RED}Failed to update Jira card ${JIRA_KEY}${NC}"
    echo "Make sure the backend server is running on ${API_BASE_URL}"
fi

exit 0

