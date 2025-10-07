#!/usr/bin/env python3
"""
Test script for Git Hooks Service
Demonstrates how branch names are matched with Jira tickets and how status updates work.
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.git_hooks_service import GitHooksService


async def test_branch_name_extraction():
    """Test the branch name extraction functionality."""
    
    print("=== Testing Branch Name Extraction ===")
    
    git_hooks = GitHooksService()
    
    test_cases = [
        ("feature/SCRUM-25", "SCRUM-25"),
        ("bugfix/SCRUM-123", "SCRUM-123"),
        ("SCRUM-456", "SCRUM-456"),
        ("hotfix/SCRUM-789", "SCRUM-789"),
        ("SCRUM-250", None),  # Should not match SCRUM-25
        ("feature/SCRUM-25-backup", "SCRUM-25"),
        ("SCRUM-25-feature", "SCRUM-25"),
        ("random-branch", None),
        ("feature/ABC-123", "ABC-123"),
        ("SCRUM-25", "SCRUM-25"),
    ]
    
    for branch_name, expected in test_cases:
        result = git_hooks.extract_jira_ticket_from_branch(branch_name)
        status = "✓" if result == expected else "✗"
        print(f"{status} {branch_name:<25} -> {result} (expected: {expected})")


async def test_git_event_processing():
    """Test git event processing (without actual Jira updates)."""
    
    print("\n=== Testing Git Event Processing ===")
    
    git_hooks = GitHooksService()
    
    # Test push event
    push_event = {
        'branch_name': 'feature/SCRUM-25',
        'repository': 'myorg/myrepo',
        'author': 'john.doe',
        'commit_message': 'Add new feature for user authentication'
    }
    
    print("Testing push event...")
    try:
        result = await git_hooks.process_git_event('push', push_event)
        print(f"Push event result: {result}")
    except Exception as e:
        print(f"Push event error (expected if Jira not configured): {e}")
    
    # Test PR opened event
    pr_opened_event = {
        'branch_name': 'feature/SCRUM-25',
        'repository': 'myorg/myrepo',
        'author': 'john.doe',
        'pr_number': 123
    }
    
    print("Testing PR opened event...")
    try:
        result = await git_hooks.process_git_event('pull_request_opened', pr_opened_event)
        print(f"PR opened event result: {result}")
    except Exception as e:
        print(f"PR opened event error (expected if Jira not configured): {e}")
    
    # Test PR merged event
    pr_merged_event = {
        'branch_name': 'feature/SCRUM-25',
        'repository': 'myorg/myrepo',
        'author': 'jane.smith',
        'pr_number': 123
    }
    
    print("Testing PR merged event...")
    try:
        result = await git_hooks.process_git_event('pull_request_merged', pr_merged_event)
        print(f"PR merged event result: {result}")
    except Exception as e:
        print(f"PR merged event error (expected if Jira not configured): {e}")


def print_usage_examples():
    """Print usage examples for the git hooks."""
    
    print("\n=== Git Hooks Usage Examples ===")
    print()
    print("1. Branch Naming Convention:")
    print("   ✓ feature/SCRUM-25    -> Updates SCRUM-25 ticket")
    print("   ✓ bugfix/SCRUM-123    -> Updates SCRUM-123 ticket")
    print("   ✓ SCRUM-456           -> Updates SCRUM-456 ticket")
    print("   ✓ hotfix/SCRUM-789    -> Updates SCRUM-789 ticket")
    print("   ✗ SCRUM-250           -> Does NOT match SCRUM-25")
    print()
    print("2. Automatic Status Updates:")
    print("   • Push to branch     -> Adds comment to Jira ticket")
    print("   • Create PR          -> Moves ticket to 'In Review'")
    print("   • Merge PR           -> Moves ticket to 'Done'")
    print("   • Close PR           -> Moves ticket back to 'To Do'")
    print()
    print("3. API Endpoints:")
    print("   • POST /api/v1/git/hooks/trigger")
    print("     - Manually trigger git hooks for testing")
    print("   • GET /api/v1/git/hooks/extract-ticket")
    print("     - Test branch name extraction")
    print()
    print("4. Webhook Integration:")
    print("   • GitHub webhooks automatically trigger git hooks")
    print("   • Configure webhook URL: /api/v1/git/webhook")
    print("   • Events: push, pull_request")


async def main():
    """Main test function."""
    
    print("Git Hooks Service Test")
    print("=" * 50)
    
    await test_branch_name_extraction()
    await test_git_event_processing()
    print_usage_examples()
    
    print("\n=== Test Complete ===")
    print("Note: Jira integration requires proper configuration in .env file")
    print("Set JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN for full functionality")


if __name__ == "__main__":
    asyncio.run(main())

