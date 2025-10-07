#!/bin/bash

# Setup script to install git hooks for Jira integration

set -e

echo "Setting up Git hooks for Jira integration..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "Error: Not in a git repository. Please run this script from the root of your git repository."
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p .git/hooks

# Copy the post-commit hook
cp post-commit-hook.sh .git/hooks/post-commit

# Make it executable
chmod +x .git/hooks/post-commit

echo "✓ Git hook installed successfully!"
echo ""
echo "The hook will now automatically update Jira card status when you commit."
echo "Make sure your branch names contain Jira keys like:"
echo "  - feature/SCRUM-25"
echo "  - bugfix/SCRUM-123"
echo "  - SCRUM-456"
echo ""
echo "To test the hook manually, run:"
echo "  ./git-hook.sh"
echo ""
echo "To configure the API URL, set the environment variable:"
echo "  export SCRUM_API_URL=http://your-server:8000/api/v1"
echo "  export SCRUM_PROJECT_KEY=SCRUM"

