#!/usr/bin/env python3
"""
Test script for Git Hooks API endpoints
Tests the git hooks functionality via HTTP API calls.
"""

import requests
import json


def test_extract_ticket_endpoint():
    """Test the extract ticket endpoint."""
    
    print("=== Testing Extract Ticket Endpoint ===")
    
    base_url = "http://localhost:8000/api/v1/git/hooks/extract-ticket"
    
    test_cases = [
        ("feature/SCRUM-25", "SCRUM-25"),
        ("bugfix/SCRUM-123", "SCRUM-123"),
        ("SCRUM-456", "SCRUM-456"),
        ("hotfix/SCRUM-789", "SCRUM-789"),
        ("SCRUM-250", None),  # Should not match SCRUM-25
        ("feature/SCRUM-25-backup", "SCRUM-25"),
        ("SCRUM-25-feature", "SCRUM-25"),
        ("random-branch", None),
    ]
    
    for branch_name, expected in test_cases:
        try:
            response = requests.get(f"{base_url}?branch_name={branch_name}")
            if response.status_code == 200:
                data = response.json()
                result = data.get('ticket_key')
                status = "✓" if result == expected else "✗"
                print(f"{status} {branch_name:<25} -> {result} (expected: {expected})")
            else:
                print(f"✗ {branch_name:<25} -> Error: {response.status_code}")
        except Exception as e:
            print(f"✗ {branch_name:<25} -> Exception: {e}")


def test_trigger_hook_endpoint():
    """Test the trigger hook endpoint."""
    
    print("\n=== Testing Trigger Hook Endpoint ===")
    
    base_url = "http://localhost:8000/api/v1/git/hooks/trigger"
    
    test_events = [
        {
            "event_type": "push",
            "branch_name": "feature/SCRUM-25",
            "repository": "myorg/myrepo",
            "author": "john.doe",
            "commit_message": "Add new feature for user authentication"
        },
        {
            "event_type": "pull_request_opened",
            "branch_name": "feature/SCRUM-25",
            "repository": "myorg/myrepo",
            "author": "john.doe",
            "pr_number": 123
        },
        {
            "event_type": "pull_request_merged",
            "branch_name": "feature/SCRUM-25",
            "repository": "myorg/myrepo",
            "author": "jane.smith",
            "pr_number": 123
        }
    ]
    
    for event in test_events:
        try:
            response = requests.post(base_url, json=event)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ {event['event_type']:<20} -> {data.get('message', 'Success')}")
            else:
                print(f"✗ {event['event_type']:<20} -> Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"✗ {event['event_type']:<20} -> Exception: {e}")


def test_backend_health():
    """Test if the backend is running."""
    
    print("=== Testing Backend Health ===")
    
    try:
        response = requests.get("http://localhost:8000/api/v1/")
        if response.status_code == 200:
            print("✓ Backend is running and accessible")
            return True
        else:
            print(f"✗ Backend returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Backend is not accessible: {e}")
        return False


def main():
    """Main test function."""
    
    print("Git Hooks API Test")
    print("=" * 50)
    
    # Check if backend is running
    if not test_backend_health():
        print("\nPlease start the backend server first:")
        print("uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return
    
    # Run tests
    test_extract_ticket_endpoint()
    test_trigger_hook_endpoint()
    
    print("\n=== Test Complete ===")
    print("Note: Jira integration requires proper configuration in .env file")
    print("Set JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN for full functionality")


if __name__ == "__main__":
    main()

