"""Jira integration models."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TicketPriority(str, Enum):
    """Jira ticket priority levels."""
    LOWEST = "Lowest"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    HIGHEST = "Highest"


class TicketStatus(str, Enum):
    """Jira ticket status."""
    TO_DO = "To Do"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    DONE = "Done"
    CANCELLED = "Cancelled"


class TicketType(str, Enum):
    """Jira ticket types."""
    STORY = "Story"
    TASK = "Task"
    BUG = "Bug"
    EPIC = "Epic"
    SUBTASK = "Sub-task"


class JiraTicket(BaseModel):
    """Jira ticket model."""
    id: Optional[str] = Field(alias="_id", default=None)
    jira_key: str  # e.g., "PROJ-123"
    jira_id: str  # Internal Jira ID
    title: str
    description: Optional[str] = None
    ticket_type: TicketType
    status: TicketStatus
    priority: TicketPriority = TicketPriority.MEDIUM
    assignee: Optional[str] = None
    reporter: str
    project_key: str
    labels: List[str] = []
    components: List[str] = []
    fix_versions: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = None
    story_points: Optional[int] = None
    epic_link: Optional[str] = None
    parent_key: Optional[str] = None  # For subtasks
    custom_fields: Dict[str, Any] = {}
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class JiraProject(BaseModel):
    """Jira project model."""
    id: str
    key: str
    name: str
    description: Optional[str] = None
    project_type: str
    lead: str
    components: List[Dict[str, str]] = []
    issue_types: List[Dict[str, str]] = []
    versions: List[Dict[str, str]] = []


class JiraWebhookEvent(BaseModel):
    """Jira webhook event model."""
    event_type: str
    timestamp: datetime
    user: Dict[str, str]
    issue: Dict[str, Any]
    changelog: Optional[Dict[str, Any]] = None
    webhook_event: str
