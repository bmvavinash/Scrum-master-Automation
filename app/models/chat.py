"""Chat and Teams bot models."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """Message types."""
    TEXT = "text"
    CARD = "card"
    COMMAND = "command"
    NOTIFICATION = "notification"


class CommandType(str, Enum):
    """Bot command types."""
    CREATE_TASK = "create-task"
    CREATE_BLOCKER = "create-blocker"
    SCHEDULE_STANDUP = "schedule-standup"
    GET_STATUS = "get-status"
    GET_VELOCITY = "get-velocity"
    GET_INSIGHTS = "get-insights"
    HELP = "help"


class ChatMessage(BaseModel):
    """Chat message model."""
    id: Optional[str] = Field(alias="_id", default=None)
    message_type: MessageType
    content: str
    sender_id: str
    sender_name: str
    channel_id: str
    thread_id: Optional[str] = None
    command_type: Optional[CommandType] = None
    command_args: Dict[str, Any] = {}
    attachments: List[Dict[str, Any]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TeamsAdaptiveCard(BaseModel):
    """Microsoft Teams adaptive card model."""
    type: str = "AdaptiveCard"
    version: str = "1.4"
    body: List[Dict[str, Any]]
    actions: Optional[List[Dict[str, Any]]] = None
    schema: str = "http://adaptivecards.io/schemas/adaptive-card.json"


class BotResponse(BaseModel):
    """Bot response model."""
    message: str
    card: Optional[TeamsAdaptiveCard] = None
    attachments: List[Dict[str, Any]] = []
    commands: List[Dict[str, Any]] = []
    should_notify: bool = False
    notification_type: Optional[str] = None


class NotificationTemplate(BaseModel):
    """Notification template model."""
    id: str
    name: str
    event_type: str
    template: str
    variables: List[str] = []
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
