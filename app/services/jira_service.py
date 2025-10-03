"""Jira integration service."""

import logging
from typing import List, Dict, Any, Optional
from jira import JIRA
from app.config import get_settings
from app.models.jira import JiraTicket, JiraProject, TicketType, TicketPriority, TicketStatus

logger = logging.getLogger(__name__)


class JiraService:
    """Service for Jira operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.jira_client = None
        self._initialize_jira()
    
    def _initialize_jira(self):
        """Initialize Jira client."""
        try:
            if not all([self.settings.jira_url, self.settings.jira_email, self.settings.jira_api_token]):
                logger.warning("Jira credentials not configured")
                return
            
            self.jira_client = JIRA(
                server=self.settings.jira_url,
                basic_auth=(self.settings.jira_email, self.settings.jira_api_token)
            )
            logger.info("Jira client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Jira client: {e}")
            self.jira_client = None
    
    async def create_ticket(
        self,
        title: str,
        description: str = "",
        ticket_type: TicketType = TicketType.TASK,
        priority: TicketPriority = TicketPriority.MEDIUM,
        assignee: Optional[str] = None,
        project_key: str = "SCRUM",
        labels: List[str] = None,
        story_points: Optional[int] = None
    ) -> Optional[JiraTicket]:
        """Create a new Jira ticket."""
        
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return None
        
        try:
            issue_dict = {
                'project': {'key': project_key},
                'summary': title,
                'description': description,
                'issuetype': {'name': ticket_type.value},
                'priority': {'name': priority.value},
            }
            
            if assignee:
                issue_dict['assignee'] = {'name': assignee}
            
            if labels:
                issue_dict['labels'] = labels
            
            if story_points:
                issue_dict['customfield_10016'] = story_points  # Story points field
            
            new_issue = self.jira_client.create_issue(fields=issue_dict)
            
            # Fetch the created issue to get all details
            issue = self.jira_client.issue(new_issue.key)
            
            return self._convert_issue_to_ticket(issue)
            
        except Exception as e:
            logger.error(f"Failed to create Jira ticket: {e}")
            return None
    
    async def update_ticket_status(
        self, 
        ticket_key: str, 
        new_status: TicketStatus
    ) -> bool:
        """Update ticket status."""
        
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return False
        
        try:
            issue = self.jira_client.issue(ticket_key)
            transitions = self.jira_client.transitions(issue)
            
            # Find the transition for the new status
            transition_id = None
            for transition in transitions:
                if new_status.value.lower() in transition['name'].lower():
                    transition_id = transition['id']
                    break
            
            if transition_id:
                self.jira_client.transition_issue(issue, transition_id)
                logger.info(f"Updated ticket {ticket_key} to {new_status.value}")
                return True
            else:
                logger.warning(f"No transition found for status {new_status.value}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update ticket status: {e}")
            return False
    
    async def get_ticket(self, ticket_key: str) -> Optional[JiraTicket]:
        """Get ticket by key."""
        
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return None
        
        try:
            issue = self.jira_client.issue(ticket_key)
            return self._convert_issue_to_ticket(issue)
        except Exception as e:
            logger.error(f"Failed to get ticket {ticket_key}: {e}")
            return None
    
    async def search_tickets(
        self, 
        jql: str, 
        max_results: int = 50
    ) -> List[JiraTicket]:
        """Search tickets using JQL."""
        
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return []
        
        try:
            issues = self.jira_client.search_issues(jql, maxResults=max_results)
            return [self._convert_issue_to_ticket(issue) for issue in issues]
        except Exception as e:
            logger.error(f"Failed to search tickets: {e}")
            return []
    
    async def get_projects(self) -> List[JiraProject]:
        """Get all accessible projects."""
        
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return []
        
        try:
            projects = self.jira_client.projects()
            return [self._convert_project_to_model(project) for project in projects]
        except Exception as e:
            logger.error(f"Failed to get projects: {e}")
            return []
    
    async def add_comment(
        self, 
        ticket_key: str, 
        comment: str
    ) -> bool:
        """Add comment to ticket."""
        
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return False
        
        try:
            issue = self.jira_client.issue(ticket_key)
            self.jira_client.add_comment(issue, comment)
            logger.info(f"Added comment to ticket {ticket_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to add comment to ticket {ticket_key}: {e}")
            return False
    
    async def create_subtask(
        self,
        parent_key: str,
        title: str,
        description: str = "",
        assignee: Optional[str] = None
    ) -> Optional[JiraTicket]:
        """Create a subtask."""
        
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return None
        
        try:
            parent_issue = self.jira_client.issue(parent_key)
            project_key = parent_issue.fields.project.key
            
            issue_dict = {
                'project': {'key': project_key},
                'summary': title,
                'description': description,
                'issuetype': {'name': TicketType.SUBTASK.value},
                'parent': {'key': parent_key},
            }
            
            if assignee:
                issue_dict['assignee'] = {'name': assignee}
            
            new_issue = self.jira_client.create_issue(fields=issue_dict)
            issue = self.jira_client.issue(new_issue.key)
            
            return self._convert_issue_to_ticket(issue)
            
        except Exception as e:
            logger.error(f"Failed to create subtask: {e}")
            return None
    
    def _convert_issue_to_ticket(self, issue) -> JiraTicket:
        """Convert Jira issue to JiraTicket model."""
        
        return JiraTicket(
            jira_key=issue.key,
            jira_id=issue.id,
            title=issue.fields.summary,
            description=getattr(issue.fields, 'description', ''),
            ticket_type=TicketType(issue.fields.issuetype.name),
            status=TicketStatus(issue.fields.status.name),
            priority=TicketPriority(issue.fields.priority.name),
            assignee=getattr(issue.fields.assignee, 'displayName', None) if issue.fields.assignee else None,
            reporter=issue.fields.reporter.displayName,
            project_key=issue.fields.project.key,
            labels=getattr(issue.fields, 'labels', []),
            created_at=issue.fields.created,
            updated_at=issue.fields.updated,
            due_date=getattr(issue.fields, 'duedate', None),
            story_points=getattr(issue.fields, 'customfield_10016', None),
            epic_link=getattr(issue.fields, 'customfield_10014', None),
            parent_key=getattr(issue.fields, 'parent', {}).get('key') if hasattr(issue.fields, 'parent') and issue.fields.parent else None
        )
    
    def _convert_project_to_model(self, project) -> JiraProject:
        """Convert Jira project to JiraProject model."""
        
        return JiraProject(
            id=project.id,
            key=project.key,
            name=project.name,
            description=getattr(project, 'description', None),
            project_type=getattr(project, 'projectTypeKey', ''),
            lead=getattr(project, 'lead', {}).get('displayName', '') if hasattr(project, 'lead') else '',
            components=[],
            issue_types=[],
            versions=[]
        )
