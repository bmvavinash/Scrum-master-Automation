"""Velocity and sprint metrics models."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum


class SprintStatus(str, Enum):
    """Sprint status."""
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Sprint(BaseModel):
    """Sprint model."""
    id: Optional[str] = Field(alias="_id", default=None)
    name: str
    status: SprintStatus
    start_date: date
    end_date: date
    goal: Optional[str] = None
    team_members: List[str] = []
    total_story_points: int = 0
    completed_story_points: int = 0
    jira_sprint_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class VelocityMetrics(BaseModel):
    """Velocity metrics for a team."""
    team_id: str
    sprint_id: str
    sprint_name: str
    planned_story_points: int
    completed_story_points: int
    velocity: float  # Completed points per sprint
    average_cycle_time: float  # Days
    average_lead_time: float  # Days
    burndown_data: List[Dict[str, Any]] = []
    blockers_count: int = 0
    bugs_count: int = 0
    technical_debt_hours: float = 0.0
    team_satisfaction: Optional[float] = None
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TeamMemberMetrics(BaseModel):
    """Individual team member metrics."""
    member_id: str
    member_name: str
    sprint_id: str
    story_points_assigned: int
    story_points_completed: int
    tasks_completed: int
    average_cycle_time: float
    blockers_raised: int
    bugs_introduced: int
    code_reviews_given: int
    code_reviews_received: int
    satisfaction_score: Optional[float] = None
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PredictionInsight(BaseModel):
    """AI-generated prediction insight."""
    type: str  # "deadline_risk", "bottleneck", "velocity_trend", "quality_risk"
    confidence: float  # 0.0 to 1.0
    description: str
    recommendations: List[str] = []
    affected_items: List[str] = []  # Ticket IDs, member IDs, etc.
    predicted_date: Optional[datetime] = None
    severity: str = "medium"  # low, medium, high, critical
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
