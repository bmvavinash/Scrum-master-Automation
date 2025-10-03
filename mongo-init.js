// MongoDB initialization script
db = db.getSiblingDB('scrum_automation');

// Create collections with validation
db.createCollection('meetings', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['title', 'meeting_type', 'scheduled_time', 'participants'],
      properties: {
        title: { bsonType: 'string' },
        meeting_type: { enum: ['standup', 'sprint_planning', 'retrospective', 'review'] },
        status: { enum: ['scheduled', 'in_progress', 'completed', 'cancelled'] },
        scheduled_time: { bsonType: 'date' },
        participants: { bsonType: 'array' }
      }
    }
  }
});

db.createCollection('jira_tickets', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['jira_key', 'title', 'ticket_type', 'status', 'project_key'],
      properties: {
        jira_key: { bsonType: 'string' },
        title: { bsonType: 'string' },
        ticket_type: { enum: ['Story', 'Task', 'Bug', 'Epic', 'Sub-task'] },
        status: { enum: ['To Do', 'In Progress', 'In Review', 'Done', 'Cancelled'] }
      }
    }
  }
});

db.createCollection('git_commits');
db.createCollection('pull_requests');
db.createCollection('sprints');
db.createCollection('velocity_metrics');
db.createCollection('team_member_metrics');
db.createCollection('prediction_insights');
db.createCollection('chat_messages');
db.createCollection('code_analyses');
db.createCollection('code_smells');
db.createCollection('pr_analyses');
db.createCollection('command_executions');
db.createCollection('git_webhook_events');

// Create indexes for better performance
db.meetings.createIndex({ "scheduled_time": 1 });
db.meetings.createIndex({ "meeting_type": 1 });
db.meetings.createIndex({ "status": 1 });

db.jira_tickets.createIndex({ "jira_key": 1 }, { unique: true });
db.jira_tickets.createIndex({ "project_key": 1 });
db.jira_tickets.createIndex({ "assignee": 1 });
db.jira_tickets.createIndex({ "status": 1 });

db.git_commits.createIndex({ "sha": 1 }, { unique: true });
db.git_commits.createIndex({ "repository": 1 });
db.git_commits.createIndex({ "timestamp": -1 });

db.pull_requests.createIndex({ "number": 1, "repository": 1 }, { unique: true });
db.pull_requests.createIndex({ "repository": 1 });
db.pull_requests.createIndex({ "status": 1 });
db.pull_requests.createIndex({ "author": 1 });

db.sprints.createIndex({ "start_date": -1 });
db.sprints.createIndex({ "status": 1 });

db.velocity_metrics.createIndex({ "sprint_id": 1 });
db.velocity_metrics.createIndex({ "team_id": 1 });

db.chat_messages.createIndex({ "channel_id": 1 });
db.chat_messages.createIndex({ "created_at": -1 });

db.code_analyses.createIndex({ "repository_path": 1 });
db.code_analyses.createIndex({ "timestamp": -1 });

db.code_smells.createIndex({ "repository_path": 1 });
db.code_smells.createIndex({ "severity": 1 });
db.code_smells.createIndex({ "detected_at": -1 });

print('Database initialization completed successfully!');
