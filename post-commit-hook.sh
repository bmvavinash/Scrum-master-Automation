#!/bin/bash

# Git post-commit hook to automatically update Jira card status
# Install this script as .git/hooks/post-commit

# Configuration - adjust these values as needed
API_BASE_URL="${SCRUM_API_URL:-http://localhost:8000/api/v1}"
PROJECT_KEY="${SCRUM_PROJECT_KEY:-SCRUM}"

# Get current branch name
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

# Skip if on detached HEAD or in the middle of a rebase/merge
if [ "$BRANCH_NAME" = "HEAD" ] || [ -f ".git/MERGE_HEAD" ] || [ -f ".git/rebase-apply/applying" ]; then
    exit 0
fi

# Extract Jira key from branch name using regex
# This matches patterns like: SCRUM-25, feature/SCRUM-25, bugfix/SCRUM-123
JIRA_KEY=$(echo "$BRANCH_NAME" | grep -oE "${PROJECT_KEY}-[0-9]+")

if [ -z "$JIRA_KEY" ]; then
    # No Jira key found, skip silently
    exit 0
fi

echo "Git Hook: Updating Jira card ${JIRA_KEY} for branch '${BRANCH_NAME}'"

# Call the API to update Jira card status
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    "${API_BASE_URL}/git-hooks/update-from-branch" \
    -H "Content-Type: application/json" \
    -d "{\"branch_name\": \"${BRANCH_NAME}\", \"git_action\": \"commit\"}" \
    --connect-timeout 5 --max-time 10)

# Extract HTTP status code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✓ Successfully updated Jira card ${JIRA_KEY}"
else
    echo "✗ Failed to update Jira card ${JIRA_KEY} (HTTP ${HTTP_CODE})"
    echo "Response: $RESPONSE_BODY"
fi

exit 0

