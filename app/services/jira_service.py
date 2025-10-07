"""Jira integration service."""

import logging
from typing import List, Dict, Any, Optional
from jira import JIRA
import requests
from app.config import get_settings
from app.models.jira import JiraTicket, JiraProject, TicketType, TicketPriority, TicketStatus

logger = logging.getLogger(__name__)


class JiraService:
    """Service for Jira operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.jira_client = None
        self.jira_url = self.settings.jira_url
        self._initialize_jira()

    def is_initialized(self) -> bool:
        """Return True if Jira client is initialized with credentials."""
        return self.jira_client is not None
    
    def _initialize_jira(self):
        """Initialize Jira client."""
        try:
            if not all([self.settings.jira_url, self.settings.jira_email, self.settings.jira_api_token]):
                logger.warning("Jira credentials not configured")
                return
            
            # Force Jira Cloud REST API v3 usage
            options = {
                'server': self.settings.jira_url,
                'rest_api_version': '3'
            }
            self.jira_client = JIRA(
                options=options,
                basic_auth=(self.settings.jira_email, self.settings.jira_api_token)
            )
            logger.info("Jira client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Jira client: {e}")
            self.jira_client = None
    
    def _text_to_adf(self, text: str) -> Dict[str, Any]:
        """Convert plain text to Atlassian Document Format (ADF)."""
        if not text:
            return {
                "type": "doc",
                "version": 1,
                "content": []
            }
        
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": text
                        }
                    ]
                }
            ]
        }

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
                'description': self._text_to_adf(description),
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
            logger.warning("Jira client not initialized - returning empty list")
            return []
        
        try:
            issues = self.jira_client.search_issues(jql, maxResults=max_results)
            return [self._convert_issue_to_ticket(issue) for issue in issues]
        except Exception as e:
            logger.error(f"Failed to search tickets: {e}")
            # Fallback to direct Jira Cloud v3 /search/jql
            try:
                return self._search_tickets_v3_jql(jql, max_results)
            except Exception as e2:
                logger.error(f"Fallback v3 /search/jql failed: {e2}")
                return []
    
    def _get_mock_tickets(self) -> List[JiraTicket]:
        """Return mock tickets for development/testing."""
        from datetime import datetime
        
        return [
            JiraTicket(
                jira_key="SCRUM-123",
                jira_id="10001",
                title="Implement user authentication",
                description="Add login and registration functionality",
                ticket_type=TicketType.STORY,
                status=TicketStatus.IN_PROGRESS,
                priority=TicketPriority.HIGH,
                assignee="John Doe",
                reporter="Jane Smith",
                project_key="SCRUM",
                labels=["backend", "security"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                story_points=8
            ),
            JiraTicket(
                jira_key="SCRUM-124",
                jira_id="10002",
                title="Fix login button styling",
                description="Button appears misaligned on mobile devices",
                ticket_type=TicketType.BUG,
                status=TicketStatus.TO_DO,
                priority=TicketPriority.MEDIUM,
                assignee="Alice Johnson",
                reporter="Bob Wilson",
                project_key="SCRUM",
                labels=["frontend", "ui"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                story_points=3
            ),
            JiraTicket(
                jira_key="SCRUM-125",
                jira_id="10003",
                title="Database migration for user roles",
                description="Create migration scripts for new role system",
                ticket_type=TicketType.TASK,
                status=TicketStatus.DONE,
                priority=TicketPriority.HIGH,
                assignee="Charlie Brown",
                reporter="Diana Prince",
                project_key="SCRUM",
                labels=["database", "migration"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                story_points=5
            )
        ]
    
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

    async def add_comment_adf(
        self,
        ticket_key: str,
        adf_body: Dict[str, Any]
    ) -> bool:
        """Add a rich-text ADF comment to a ticket (supports code blocks)."""
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return False
        try:
            url = f"{self.jira_url}/rest/api/3/issue/{ticket_key}/comment"
            comment_data = {"body": adf_body}
            response = self.jira_client._session.post(url, json=comment_data)
            if response.status_code in [200, 201]:
                logger.info(f"Added ADF comment to ticket {ticket_key}")
                return True
            logger.error(
                f"Failed to add ADF comment to ticket {ticket_key}: {response.status_code} - {response.text}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to add ADF comment to ticket {ticket_key}: {e}")
            return False

    async def update_ticket_description(self, ticket_key: str, description: str) -> bool:
        """Update Jira ticket description using ADF format (REST v3)."""
        if not self.jira_client:
            logger.error("Jira client not initialized")
            return False
        try:
            url = f"{self.jira_url}/rest/api/3/issue/{ticket_key}"
            payload = {
                "update": {
                    "description": [
                        {"set": self._text_to_adf(description)}
                    ]
                }
            }
            response = self.jira_client._session.put(url, json=payload)
            if response.status_code in [200, 204]:
                logger.info(f"Updated description for {ticket_key}")
                return True
            logger.error(
                f"Failed to update description for {ticket_key}: {response.status_code} - {response.text}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to update description for {ticket_key}: {e}")
            return False
        
        try:
            # Use the REST API v3 format for comments
            comment_data = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": comment
                                }
                            ]
                        }
                    ]
                }
            }
            
            # Use the REST API directly for v3 compatibility
            url = f"{self.jira_url}/rest/api/3/issue/{ticket_key}/comment"
            response = self.jira_client._session.post(url, json=comment_data)
            
            if response.status_code in [200, 201]:
                logger.info(f"Added comment to ticket {ticket_key}")
                return True
            else:
                logger.error(f"Failed to add comment to ticket {ticket_key}: {response.status_code} - {response.text}")
                return False
                
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
    
    def _adf_to_plain_text(self, adf: Any) -> Optional[str]:
        """Convert Atlassian Document Format (ADF) to plain text."""
        if adf is None:
            return None
        if isinstance(adf, str):
            return adf
        # Expected ADF dict structure with 'content' arrays and 'text' leafs
        parts: list[str] = []
        def walk(node: Any):
            if isinstance(node, dict):
                # Append text if present
                text = node.get('text')
                if isinstance(text, str):
                    parts.append(text)
                # Recurse into content
                content = node.get('content')
                if isinstance(content, list):
                    for child in content:
                        walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
        walk(adf)
        return " ".join(p.strip() for p in parts if isinstance(p, str) and p.strip()) or None

    def _convert_issue_to_ticket(self, issue) -> JiraTicket:
        """Convert Jira issue to JiraTicket model."""
        
        # Handle description field - convert ADF to plain text if needed
        description = getattr(issue.fields, 'description', '')
        if description and not isinstance(description, str):
            description = self._adf_to_plain_text(description)
        
        return JiraTicket(
            jira_key=issue.key,
            jira_id=issue.id,
            title=issue.fields.summary,
            description=description or '',
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

    def _convert_issue_json_to_ticket(self, issue: Dict[str, Any]) -> JiraTicket:
        """Convert Jira v3 REST issue JSON to JiraTicket model."""
        fields = issue.get('fields', {})
        
        def _adf_to_plain_text(adf: Any) -> Optional[str]:
            """Convert Atlassian Document Format (ADF) to plain text."""
            if adf is None:
                return None
            if isinstance(adf, str):
                return adf
            # Expected ADF dict structure with 'content' arrays and 'text' leafs
            parts: list[str] = []
            def walk(node: Any):
                if isinstance(node, dict):
                    # Append text if present
                    text = node.get('text')
                    if isinstance(text, str):
                        parts.append(text)
                    # Recurse into content
                    content = node.get('content')
                    if isinstance(content, list):
                        for child in content:
                            walk(child)
                elif isinstance(node, list):
                    for child in node:
                        walk(child)
            walk(adf)
            return " ".join(p.strip() for p in parts if isinstance(p, str) and p.strip()) or None
        
        def _get(d, path, default=None):
            cur = d
            for p in path:
                if cur is None:
                    return default
                if isinstance(cur, dict):
                    cur = cur.get(p)
                else:
                    cur = getattr(cur, p, None)
            return cur if cur is not None else default
        
        description_raw = _get(fields, ['description'])
        description_text = _adf_to_plain_text(description_raw)
        return JiraTicket(
            jira_key=issue.get('key', ''),
            jira_id=str(issue.get('id', '')),
            title=_get(fields, ['summary'], ''),
            description=description_text or '',
            ticket_type=_get(fields, ['issuetype', 'name'], 'Task'),
            status=_get(fields, ['status', 'name'], 'To Do'),
            priority=_get(fields, ['priority', 'name'], 'Medium'),
            assignee=_get(fields, ['assignee', 'displayName']),
            reporter=_get(fields, ['reporter', 'displayName'], ''),
            project_key=_get(fields, ['project', 'key'], ''),
            labels=fields.get('labels', []) or [],
            components=[],
            fix_versions=[],
            created_at=_get(fields, ['created']),
            updated_at=_get(fields, ['updated']),
            due_date=_get(fields, ['duedate']),
            story_points=fields.get('customfield_10016'),
            epic_link=fields.get('customfield_10014'),
            parent_key=_get(fields, ['parent', 'key'])
        )

    def _search_tickets_v3_jql(self, jql: str, max_results: int) -> List[JiraTicket]:
        """Direct call to Jira Cloud v3 search/jql endpoint (POST)."""
        if not all([self.settings.jira_url, self.settings.jira_email, self.settings.jira_api_token]):
            logger.warning("Jira credentials missing for direct v3 call")
            return []
        url = self.settings.jira_url.rstrip('/') + '/rest/api/3/search/jql'
        payload = {
            'jql': jql,
            'maxResults': max_results,
            'fields': [
                'summary','description','issuetype','status','priority','assignee','reporter',
                'project','labels','created','updated','duedate','parent','customfield_10016','customfield_10014'
            ]
        }
        auth = (self.settings.jira_email, self.settings.jira_api_token)
        headers = {'Accept': 'application/json','Content-Type': 'application/json'}
        resp = requests.post(url, json=payload, auth=auth, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"Jira v3 search failed: {resp.status_code} {resp.text}")
        data = resp.json() or {}
        issues = data.get('issues', []) or []
        return [self._convert_issue_json_to_ticket(issue) for issue in issues]
