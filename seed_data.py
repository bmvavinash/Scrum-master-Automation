#!/usr/bin/env python3
"""Seed MongoDB with sample data for Scrum Automation."""

import asyncio
import sys
from datetime import datetime, timedelta, date
from app.database import connect_to_mongo, get_database, close_mongo_connection
from app.config import get_settings

async def seed_data():
    """Seed the database with sample data."""
    
    print("🌱 Seeding MongoDB with sample data...")
    
    try:
        # Connect to MongoDB
        await connect_to_mongo()
        db = get_database()
        
        # Clear existing data
        print("🧹 Clearing existing data...")
        collections = ['sprints', 'meetings', 'velocity_metrics', 'jira_tickets', 'git_commits', 'pull_requests', 'chat_messages']
        for collection_name in collections:
            await db[collection_name].drop()
            print(f"   ✅ Cleared {collection_name}")
        
        # Seed Sprints
        print("\n📅 Seeding sprints...")
        from datetime import date
        sprints = [
            {
                "name": "Sprint 1",
                "start_date": (date.today() - timedelta(days=21)).isoformat(),
                "end_date": (date.today() - timedelta(days=7)).isoformat(),
                "status": "completed",
                "team_members": ["alice", "bob", "charlie"],
                "total_story_points": 40,
                "completed_story_points": 35,
                "created_at": datetime.utcnow() - timedelta(days=21),
                "updated_at": datetime.utcnow() - timedelta(days=7)
            },
            {
                "name": "Sprint 2", 
                "start_date": (date.today() - timedelta(days=7)).isoformat(),
                "end_date": (date.today() + timedelta(days=7)).isoformat(),
                "status": "active",
                "team_members": ["alice", "bob", "charlie", "diana"],
                "total_story_points": 45,
                "completed_story_points": 20,
                "created_at": datetime.utcnow() - timedelta(days=7),
                "updated_at": datetime.utcnow()
            }
        ]
        
        sprint_results = await db.sprints.insert_many(sprints)
        sprint_ids = [str(id) for id in sprint_results.inserted_ids]
        print(f"   ✅ Created {len(sprints)} sprints")
        
        # Seed Velocity Metrics
        print("\n📊 Seeding velocity metrics...")
        velocity_metrics = [
            {
                "sprint_id": sprint_ids[0],
                "sprint_name": "Sprint 1",
                "team_id": "team_alpha",
                "planned_story_points": 40,
                "completed_story_points": 35,
                "velocity": 35,
                "average_cycle_time": 3.2,
                "average_lead_time": 5.1,
                "blockers_count": 2,
                "bugs_count": 3,
                "technical_debt_hours": 12,
                "burndown_data": [
                    {"date": "2024-01-01", "remaining_points": 40, "completed_points": 0},
                    {"date": "2024-01-02", "remaining_points": 35, "completed_points": 5},
                    {"date": "2024-01-03", "remaining_points": 30, "completed_points": 10},
                    {"date": "2024-01-04", "remaining_points": 25, "completed_points": 15},
                    {"date": "2024-01-05", "remaining_points": 20, "completed_points": 20},
                    {"date": "2024-01-06", "remaining_points": 15, "completed_points": 25},
                    {"date": "2024-01-07", "remaining_points": 10, "completed_points": 30},
                    {"date": "2024-01-08", "remaining_points": 5, "completed_points": 35}
                ],
                "calculated_at": datetime.utcnow() - timedelta(days=7)
            },
            {
                "sprint_id": sprint_ids[1],
                "sprint_name": "Sprint 2",
                "team_id": "team_alpha", 
                "planned_story_points": 45,
                "completed_story_points": 20,
                "velocity": 20,
                "average_cycle_time": 2.8,
                "average_lead_time": 4.5,
                "blockers_count": 1,
                "bugs_count": 2,
                "technical_debt_hours": 8,
                "burndown_data": [
                    {"date": "2024-01-08", "remaining_points": 45, "completed_points": 0},
                    {"date": "2024-01-09", "remaining_points": 40, "completed_points": 5},
                    {"date": "2024-01-10", "remaining_points": 35, "completed_points": 10},
                    {"date": "2024-01-11", "remaining_points": 30, "completed_points": 15},
                    {"date": "2024-01-12", "remaining_points": 25, "completed_points": 20}
                ],
                "calculated_at": datetime.utcnow()
            }
        ]
        
        await db.velocity_metrics.insert_many(velocity_metrics)
        print(f"   ✅ Created {len(velocity_metrics)} velocity metrics")
        
        # Seed Meetings
        print("\n🤝 Seeding meetings...")
        meetings = [
            {
                "title": "Daily Standup - Sprint 1",
                "meeting_type": "standup",
                "status": "completed",
                "scheduled_time": datetime.utcnow() - timedelta(days=10),
                "participants": ["alice", "bob", "charlie"],
                "participant_updates": [
                    {
                        "participant_id": "alice",
                        "participant_name": "Alice Johnson",
                        "yesterday_work": "Completed user authentication module",
                        "today_plan": "Working on password reset functionality",
                        "blockers": ["Waiting for design approval"]
                    },
                    {
                        "participant_id": "bob",
                        "participant_name": "Bob Smith", 
                        "yesterday_work": "Fixed database connection issues",
                        "today_plan": "Implementing API rate limiting",
                        "blockers": []
                    }
                ],
                "created_at": datetime.utcnow() - timedelta(days=10),
                "updated_at": datetime.utcnow() - timedelta(days=10)
            },
            {
                "title": "Sprint Planning - Sprint 2",
                "meeting_type": "sprint_planning",
                "status": "completed",
                "scheduled_time": datetime.utcnow() - timedelta(days=7),
                "participants": ["alice", "bob", "charlie", "diana"],
                "participant_updates": [],
                "created_at": datetime.utcnow() - timedelta(days=7),
                "updated_at": datetime.utcnow() - timedelta(days=7)
            }
        ]
        
        meeting_results = await db.meetings.insert_many(meetings)
        print(f"   ✅ Created {len(meetings)} meetings")
        
        # Seed Jira Tickets
        print("\n🎫 Seeding Jira tickets...")
        jira_tickets = [
            {
                "jira_key": "SCRUM-1",
                "title": "Implement user authentication",
                "description": "Create login/logout functionality with JWT tokens",
                "status": "Done",
                "ticket_type": "Story",
                "priority": "High",
                "assignee": "alice",
                "reporter": "product_owner",
                "story_points": 8,
                "labels": ["backend", "auth"],
                "created_at": datetime.utcnow() - timedelta(days=15),
                "updated_at": datetime.utcnow() - timedelta(days=5)
            },
            {
                "jira_key": "SCRUM-2", 
                "title": "Fix database connection timeout",
                "description": "Resolve intermittent connection issues",
                "status": "In Progress",
                "ticket_type": "Bug",
                "priority": "Critical",
                "assignee": "bob",
                "reporter": "qa_team",
                "story_points": 5,
                "labels": ["bug", "database"],
                "created_at": datetime.utcnow() - timedelta(days=10),
                "updated_at": datetime.utcnow() - timedelta(days=1)
            },
            {
                "jira_key": "SCRUM-3",
                "title": "Add API rate limiting",
                "description": "Implement rate limiting for API endpoints",
                "status": "To Do",
                "ticket_type": "Task",
                "priority": "Medium",
                "assignee": "charlie",
                "reporter": "tech_lead",
                "story_points": 3,
                "labels": ["api", "security"],
                "created_at": datetime.utcnow() - timedelta(days=5),
                "updated_at": datetime.utcnow() - timedelta(days=5)
            }
        ]
        
        await db.jira_tickets.insert_many(jira_tickets)
        print(f"   ✅ Created {len(jira_tickets)} Jira tickets")
        
        # Seed Git Commits
        print("\n📝 Seeding Git commits...")
        git_commits = [
            {
                "sha": "abc123def456",
                "message": "feat: implement user authentication with JWT",
                "author": "alice",
                "author_email": "alice@company.com",
                "committer": "alice",
                "committer_email": "alice@company.com",
                "url": "https://github.com/scrum-automation/backend/commit/abc123def456",
                "repository": "scrum-automation/backend",
                "branch": "feature/auth",
                "timestamp": datetime.utcnow() - timedelta(days=5),
                "jira_tickets": ["SCRUM-1"]
            },
            {
                "sha": "def456ghi789",
                "message": "fix: resolve database connection timeout issues",
                "author": "bob",
                "author_email": "bob@company.com",
                "committer": "bob",
                "committer_email": "bob@company.com",
                "url": "https://github.com/scrum-automation/backend/commit/def456ghi789",
                "repository": "scrum-automation/backend",
                "branch": "bugfix/db-timeout",
                "timestamp": datetime.utcnow() - timedelta(days=2),
                "jira_tickets": ["SCRUM-2"]
            },
            {
                "sha": "ghi789jkl012",
                "message": "docs: update API documentation",
                "author": "charlie",
                "author_email": "charlie@company.com",
                "committer": "charlie",
                "committer_email": "charlie@company.com",
                "url": "https://github.com/scrum-automation/backend/commit/ghi789jkl012",
                "repository": "scrum-automation/backend", 
                "branch": "main",
                "timestamp": datetime.utcnow() - timedelta(hours=6),
                "jira_tickets": []
            }
        ]
        
        await db.git_commits.insert_many(git_commits)
        print(f"   ✅ Created {len(git_commits)} Git commits")
        
        # Seed Pull Requests
        print("\n🔄 Seeding pull requests...")
        pull_requests = [
            {
                "number": 42,
                "title": "Implement user authentication system",
                "description": "Adds JWT-based authentication with login/logout functionality",
                "author": "alice",
                "repository": "scrum-automation/backend",
                "status": "merged",
                "head_branch": "feature/auth",
                "base_branch": "main",
                "created_at": datetime.utcnow() - timedelta(days=6),
                "updated_at": datetime.utcnow() - timedelta(days=4),
                "merged_at": datetime.utcnow() - timedelta(days=4),
                "closed_at": None,
                "jira_tickets": ["SCRUM-1"]
            },
            {
                "number": 43,
                "title": "Fix database connection timeout",
                "description": "Resolves intermittent connection issues with connection pooling",
                "author": "bob",
                "repository": "scrum-automation/backend",
                "status": "open",
                "head_branch": "bugfix/db-timeout",
                "base_branch": "main",
                "created_at": datetime.utcnow() - timedelta(days=3),
                "updated_at": datetime.utcnow() - timedelta(hours=2),
                "merged_at": None,
                "closed_at": None,
                "jira_tickets": ["SCRUM-2"]
            }
        ]
        
        await db.pull_requests.insert_many(pull_requests)
        print(f"   ✅ Created {len(pull_requests)} pull requests")
        
        # Seed Chat Messages
        print("\n💬 Seeding chat messages...")
        chat_messages = [
            {
                "message_type": "text",
                "content": "Good morning team! Ready for standup?",
                "sender_id": "alice",
                "sender_name": "Alice Johnson",
                "channel_id": "general",
                "thread_id": None,
                "created_at": datetime.utcnow() - timedelta(hours=2)
            },
            {
                "message_type": "text", 
                "content": "I'm working on the authentication module today",
                "sender_id": "bob",
                "sender_name": "Bob Smith",
                "channel_id": "general",
                "thread_id": None,
                "created_at": datetime.utcnow() - timedelta(hours=1)
            },
            {
                "message_type": "text",
                "content": "Need help with database connection issues",
                "sender_id": "charlie",
                "sender_name": "Charlie Brown",
                "channel_id": "general", 
                "thread_id": None,
                "created_at": datetime.utcnow() - timedelta(minutes=30)
            }
        ]
        
        await db.chat_messages.insert_many(chat_messages)
        print(f"   ✅ Created {len(chat_messages)} chat messages")
        
        print("\n🎉 Sample data seeding completed successfully!")
        print("\n📊 Summary:")
        print(f"   • {len(sprints)} sprints")
        print(f"   • {len(velocity_metrics)} velocity metrics")
        print(f"   • {len(meetings)} meetings")
        print(f"   • {len(jira_tickets)} Jira tickets")
        print(f"   • {len(git_commits)} Git commits")
        print(f"   • {len(pull_requests)} pull requests")
        print(f"   • {len(chat_messages)} chat messages")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        return False
    finally:
        await close_mongo_connection()
    
    return True

if __name__ == "__main__":
    try:
        asyncio.run(seed_data())
    except KeyboardInterrupt:
        print("\n\n⏹️  Seeding interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Unexpected error: {e}")
        sys.exit(1)
