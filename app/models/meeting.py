"""Meeting and standup related models."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class MeetingType(str, Enum):
    """Meeting types."""
    STANDUP = "standup"
    SPRINT_PLANNING = "sprint_planning"
    RETROSPECTIVE = "retrospective"
    REVIEW = "review"


class MeetingStatus(str, Enum):
    """Meeting status."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ParticipantUpdate(BaseModel):
    """Individual participant update in a meeting."""
    participant_id: str
    participant_name: str
    yesterday_work: Optional[str] = None
    today_plan: Optional[str] = None
    blockers: List[str] = []
    mood: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ActionItem(BaseModel):
    """Action item extracted from meeting."""
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    title: str
    description: Optional[str] = None
    assignee: str
    due_date: Optional[datetime] = None
    priority: str = "medium"  # low, medium, high, critical
    status: str = "open"  # open, in_progress, completed, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MeetingSummary(BaseModel):
    """AI-generated meeting summary."""
    key_points: List[str]
    action_items: List[ActionItem]
    blockers: List[str]
    progress_summary: str
    team_mood: Optional[str] = None
    velocity_insights: Optional[Dict[str, Any]] = None


class Meeting(BaseModel):
    """Meeting model."""
    id: Optional[str] = Field(alias="_id", default=None)
    title: str
    meeting_type: MeetingType
    status: MeetingStatus = MeetingStatus.SCHEDULED
    scheduled_time: datetime
    duration_minutes: int = 30
    participants: List[str]  # List of participant IDs
    participant_updates: List[ParticipantUpdate] = []
    summary: Optional[MeetingSummary] = None
    jira_tickets_created: List[str] = []  # List of Jira ticket IDs
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
