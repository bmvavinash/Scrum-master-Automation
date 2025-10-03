"""Git integration models."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class GitEventType(str, Enum):
    """Git event types."""
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    PULL_REQUEST_REVIEW = "pull_request_review"
    ISSUE = "issue"
    COMMIT = "commit"
    BRANCH = "branch"


class PullRequestStatus(str, Enum):
    """Pull request status."""
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    DRAFT = "draft"


class PullRequestAction(str, Enum):
    """Pull request actions."""
    OPENED = "opened"
    CLOSED = "closed"
    MERGED = "merged"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVIEW_REQUESTED = "review_requested"


class GitCommit(BaseModel):
    """Git commit model."""
    id: Optional[str] = Field(alias="_id", default=None)
    sha: str
    message: str
    author: str
    author_email: str
    committer: str
    committer_email: str
    timestamp: datetime
    url: str
    branch: str
    repository: str
    files_changed: List[str] = []
    additions: int = 0
    deletions: int = 0
    jira_tickets: List[str] = []  # Extracted Jira ticket references
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PullRequest(BaseModel):
    """Pull request model."""
    id: Optional[str] = Field(alias="_id", default=None)
    number: int
    title: str
    description: Optional[str] = None
    status: PullRequestStatus
    author: str
    assignees: List[str] = []
    reviewers: List[str] = []
    base_branch: str
    head_branch: str
    repository: str
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    commits: List[GitCommit] = []
    jira_tickets: List[str] = []
    labels: List[str] = []
    milestone: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GitWebhookEvent(BaseModel):
    """Git webhook event model."""
    event_type: GitEventType
    action: str
    repository: str
    sender: str
    timestamp: datetime
    payload: Dict[str, Any]
    pull_request: Optional[PullRequest] = None
    commit: Optional[GitCommit] = None
