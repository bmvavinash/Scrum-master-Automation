"""Jira integration service."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
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
            
            # Test connection first with REST API
            test_url = self.settings.jira_url.rstrip('/') + '/rest/api/3/myself'
            auth = (self.settings.jira_email, self.settings.jira_api_token)
            headers = {'Accept': 'application/json'}
            
            try:
                test_resp = requests.get(test_url, auth=auth, headers=headers, timeout=10)
                if test_resp.ok:
                    user_info = test_resp.json()
                    logger.info(f"Jira connection test successful. Connected as: {user_info.get('displayName', user_info.get('emailAddress', 'unknown'))}")
                else:
                    error_msg = test_resp.text[:200] if test_resp.text else "Unknown error"
                    if test_resp.status_code == 401:
                        logger.error(f"Jira authentication FAILED (401). Please check:")
                        logger.error(f"  1. JIRA_EMAIL is correct: {self.settings.jira_email}")
                        logger.error(f"  2. JIRA_API_TOKEN is valid and not expired")
                        logger.error(f"  3. API token was generated from: https://id.atlassian.com/manage-profile/security/api-tokens")
                        logger.error(f"  Error: {error_msg}")
                    else:
                        logger.warning(f"Jira connection test failed: {test_resp.status_code} - {error_msg}")
            except Exception as test_e:
                logger.error(f"Jira connection test error: {test_e}")
            
            # Initialize Jira client (for fallback operations)
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
            logger.error(f"Failed to initialize Jira client: {e}", exc_info=True)
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
            # First try via jira python client (may return ADF objects)
            issue = self.jira_client.issue(ticket_key)
            ticket = self._convert_issue_to_ticket(issue)
            # If description missing/empty, fallback to direct v3 REST for robust ADF parsing
            if ticket and (ticket.description is None or ticket.description.strip() == ""):
                try:
                    url = self.jira_url.rstrip('/') + f"/rest/api/3/issue/{ticket_key}?fields=summary,description,issuetype,status,priority,assignee,reporter,project,labels,created,updated,duedate,parent,customfield_10016,customfield_10014,customfield_10020,customfield_10021,customfield_10026,customfield_10027"
                    auth = (self.settings.jira_email, self.settings.jira_api_token)
                    headers = {'Accept': 'application/json'}
                    resp = self.jira_client._session.get(url, headers=headers, auth=auth)
                    if resp.ok:
                        issue_json = resp.json()
                        ticket = self._convert_issue_json_to_ticket(issue_json)
                except Exception as e2:
                    logger.warning(f"Fallback v3 read failed for {ticket_key}: {e2}")
            return ticket
        except Exception as e:
            logger.error(f"Failed to get ticket {ticket_key}: {e}")
            return None
    
    async def search_tickets(
        self, 
        jql: str, 
        max_results: int = 50
    ) -> List[JiraTicket]:
        """Search tickets using JQL.
        
        Uses the new /rest/api/3/search/jql endpoint as the old /rest/api/3/search
        endpoint has been deprecated and removed by Jira.
        """
        
        # Use the new v3 /search/jql endpoint directly (required as of Jira API changes)
        # The old search_issues() method uses deprecated /rest/api/3/search endpoint
        try:
            return self._search_tickets_v3_jql(jql, max_results)
        except Exception as e:
            logger.error(f"Failed to search tickets using v3 /search/jql: {e}")
            # If v3 endpoint fails, try using jira library as last resort
            # (though it will likely fail due to deprecated endpoint)
            if self.jira_client:
                try:
                    logger.warning("Attempting fallback to jira library search_issues (may fail due to deprecated endpoint)")
                    issues = self.jira_client.search_issues(jql, maxResults=max_results)
                    return [self._convert_issue_to_ticket(issue) for issue in issues]
                except Exception as e2:
                    logger.error(f"Fallback to jira library also failed: {e2}")
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
        """Get all accessible projects using REST API v3."""
        
        if not all([self.settings.jira_url, self.settings.jira_email, self.settings.jira_api_token]):
            logger.error("Jira credentials not configured")
            return []
        
        try:
            # Use REST API v3 directly to get projects
            url = self.settings.jira_url.rstrip('/') + '/rest/api/3/project'
            auth = (self.settings.jira_email, self.settings.jira_api_token)
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            logger.debug(f"Fetching projects from: {url}")
            resp = requests.get(url, auth=auth, headers=headers, timeout=30)
            
            if not resp.ok:
                logger.error(f"Failed to get projects: {resp.status_code} - {resp.text}")
                # Try to use jira client as fallback
                if self.jira_client:
                    try:
                        logger.info("Trying fallback: using jira client to get projects")
                        projects = self.jira_client.projects()
                        project_list = [self._convert_project_to_model(project) for project in projects]
                        logger.info(f"Found {len(project_list)} accessible projects via jira client: {[p.key for p in project_list]}")
                        return project_list
                    except Exception as e2:
                        logger.error(f"Jira client fallback also failed: {e2}")
                return []
            
            try:
                data = resp.json()
            except Exception as json_e:
                logger.error(f"Failed to parse JSON response: {json_e}")
                logger.error(f"Response text: {resp.text[:500]}")
                return []
            
            if not isinstance(data, list):
                logger.error(f"Unexpected response format. Expected list, got: {type(data)}")
                logger.error(f"Response: {str(data)[:500]}")
                return []
            
            logger.debug(f"Received {len(data)} projects from API")
            
            # Convert JSON response to JiraProject models
            project_list = []
            for proj_data in data:
                try:
                    project = JiraProject(
                        id=str(proj_data.get('id', '')),
                        key=proj_data.get('key', ''),
                        name=proj_data.get('name', ''),
                        description=proj_data.get('description', ''),
                        project_type=proj_data.get('projectTypeKey', ''),
                        lead=proj_data.get('lead', {}).get('displayName', '') if proj_data.get('lead') else ''
                    )
                    project_list.append(project)
                except Exception as e:
                    logger.warning(f"Failed to convert project {proj_data.get('key', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Found {len(project_list)} accessible projects: {[p.key for p in project_list]}")
            if len(project_list) == 0:
                logger.warning("No projects found. This could mean:")
                logger.warning("  1. User has no project access")
                logger.warning("  2. Jira instance has no projects")
                logger.warning("  3. Authentication/permissions issue")
            
            return project_list
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while getting projects: {e}")
            # Try jira client as fallback
            if self.jira_client:
                try:
                    logger.info("Trying fallback: using jira client to get projects")
                    projects = self.jira_client.projects()
                    project_list = [self._convert_project_to_model(project) for project in projects]
                    logger.info(f"Found {len(project_list)} accessible projects via jira client: {[p.key for p in project_list]}")
                    return project_list
                except Exception as e2:
                    logger.error(f"Jira client fallback also failed: {e2}")
            return []
        except Exception as e:
            logger.error(f"Failed to get projects: {e}", exc_info=True)
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
        description_text = description or ''
        if description and not isinstance(description, str):
            description_text = self._adf_to_plain_text(description) or ''
        
        # Extract acceptance criteria
        acceptance_criteria = None
        # Try custom fields first
        ac_field_ids = ['customfield_10020', 'customfield_10021', 'customfield_10026', 'customfield_10027']
        for field_id in ac_field_ids:
            ac_value = getattr(issue.fields, field_id, None)
            if ac_value:
                if isinstance(ac_value, str):
                    acceptance_criteria = ac_value
                elif isinstance(ac_value, dict):
                    acceptance_criteria = self._adf_to_plain_text(ac_value)
                break
        
        # If not in custom fields, try to extract from description
        if not acceptance_criteria and description_text:
            acceptance_criteria = self._extract_acceptance_criteria_from_text(description_text)
            # Remove AC from description if found
            if acceptance_criteria and acceptance_criteria in description_text:
                # Simple cleanup - remove AC section
                lines = description_text.split('\n')
                cleaned = []
                in_ac = False
                for line in lines:
                    if any(m in line.lower() for m in ['acceptance criteria', 'acceptance:', 'ac:', 'criteria:']):
                        in_ac = True
                        continue
                    if in_ac and line.strip() and not (line.strip().startswith('-') or line.strip().startswith('*')):
                        if len(line.strip()) > 50:
                            in_ac = False
                            cleaned.append(line)
                        continue
                    if not in_ac:
                        cleaned.append(line)
                description_text = '\n'.join(cleaned).strip()
        
        return JiraTicket(
            jira_key=issue.key,
            jira_id=issue.id,
            title=issue.fields.summary,
            description=description_text or '',
            acceptance_criteria=acceptance_criteria,
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
        # Import datetime locally to ensure it's available in nested functions
        from datetime import datetime as dt_class
        
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
        description_text = _adf_to_plain_text(description_raw) or ''
        
        # Extract acceptance criteria from description or custom fields
        acceptance_criteria = self._extract_acceptance_criteria(
            description_text, fields
        )
        
        # Remove acceptance criteria from description if found
        if acceptance_criteria and acceptance_criteria in description_text:
            # Try to clean up description by removing AC section
            description_lines = description_text.split('\n')
            cleaned_lines = []
            in_ac_section = False
            for line in description_lines:
                if any(marker in line.lower() for marker in ['acceptance criteria', 'acceptance:', 'ac:', 'criteria:']):
                    in_ac_section = True
                    continue
                if in_ac_section and line.strip() and not line.startswith('-') and not line.startswith('*'):
                    # Check if we're past the AC section
                    if len(line) > 50:  # Likely not an AC item
                        in_ac_section = False
                        cleaned_lines.append(line)
                    continue
                if not in_ac_section:
                    cleaned_lines.append(line)
            description_text = '\n'.join(cleaned_lines).strip()
        
        # Parse dates safely
        created_at = _get(fields, ['created'])
        updated_at = _get(fields, ['updated'])
        due_date = _get(fields, ['duedate'])
        
        # Parse dates safely - use dt_class imported in method scope
        def parse_date(date_str):
            """Parse Jira date string to datetime object."""
            if not date_str:
                return None
            # dt_class is datetime imported in method scope
            if isinstance(date_str, dt_class):
                return date_str
            try:
                # Jira dates are in ISO format: 2024-01-01T12:00:00.000+0530 or 2024-01-01T12:00:00.000Z
                date_str_clean = str(date_str).strip()
                if not date_str_clean:
                    return None
                    
                # Try parsing with dateutil first (more robust for timezones)
                try:
                    from dateutil import parser as date_parser
                    return date_parser.parse(date_str_clean)
                except ImportError:
                    # Fallback: parse manually without dateutil
                    import re
                    # Remove timezone offset (e.g., +0530, -0500, Z)
                    # Pattern: +0530, -0500, or Z at end
                    tz_pattern = r'[+-]\d{4}|Z$'
                    date_str_no_tz = re.sub(tz_pattern, '', date_str_clean)
                    # Remove microseconds if present
                    if '.' in date_str_no_tz:
                        date_str_no_tz = date_str_no_tz.split('.')[0]
                    
                    # Parse ISO format: YYYY-MM-DDTHH:MM:SS
                    try:
                        return dt_class.fromisoformat(date_str_no_tz)
                    except ValueError:
                        # Try alternative format
                        try:
                            return dt_class.strptime(date_str_no_tz, '%Y-%m-%dT%H:%M:%S')
                        except ValueError:
                            # Try date only
                            try:
                                return dt_class.strptime(date_str_no_tz.split('T')[0], '%Y-%m-%d')
                            except ValueError:
                                # Last resort: return current time
                                logger.warning(f"Could not parse date '{date_str}', using current time")
                                try:
                                    from datetime import timezone
                                    return dt_class.now(timezone.utc)
                                except (ImportError, AttributeError):
                                    return dt_class.utcnow()
            except Exception as e:
                logger.warning(f"Failed to parse date '{date_str}': {e}")
                # Return current time as fallback (better than None to avoid errors)
                try:
                    from datetime import timezone
                    return dt_class.now(timezone.utc)
                except (ImportError, AttributeError):
                    return dt_class.utcnow()
        
        created_at_parsed = parse_date(created_at)
        updated_at_parsed = parse_date(updated_at)
        due_date_parsed = parse_date(due_date)
        
        # Get ticket type, status, priority with safe defaults
        ticket_type_str = _get(fields, ['issuetype', 'name'], 'Task')
        status_str = _get(fields, ['status', 'name'], 'To Do')
        priority_str = _get(fields, ['priority', 'name'], 'Medium')
        
        # Convert to enum with fallback
        try:
            ticket_type = TicketType(ticket_type_str)
        except ValueError:
            logger.warning(f"Unknown ticket type: {ticket_type_str}, defaulting to Task")
            ticket_type = TicketType.TASK
        
        try:
            status = TicketStatus(status_str)
        except ValueError:
            logger.debug(f"Status '{status_str}' not in enum, trying to map...")
            # Try to match common variations (case-insensitive)
            status_lower = status_str.lower().strip()
            status_mapping = {
                'to do': TicketStatus.TO_DO,
                'todo': TicketStatus.TO_DO,
                'open': TicketStatus.TO_DO,
                'in progress': TicketStatus.IN_PROGRESS,
                'inprogress': TicketStatus.IN_PROGRESS,
                'progress': TicketStatus.IN_PROGRESS,
                'in review': TicketStatus.IN_REVIEW,
                'inreview': TicketStatus.IN_REVIEW,
                'review': TicketStatus.IN_REVIEW,
                'ready for build': TicketStatus.READY_FOR_BUILD,
                'readyforbuild': TicketStatus.READY_FOR_BUILD,
                'done': TicketStatus.DONE,
                'completed': TicketStatus.DONE,
                'complete': TicketStatus.DONE,
                'closed': TicketStatus.DONE,
                'cancelled': TicketStatus.CANCELLED,
                'canceled': TicketStatus.CANCELLED,
            }
            status = status_mapping.get(status_lower, TicketStatus.TO_DO)
            logger.debug(f"Mapped status '{status_str}' to '{status.value}'")
        
        try:
            priority = TicketPriority(priority_str)
        except ValueError:
            logger.warning(f"Unknown priority: {priority_str}, defaulting to Medium")
            priority_lower = priority_str.lower()
            if 'high' in priority_lower:
                priority = TicketPriority.HIGH
            elif 'low' in priority_lower:
                priority = TicketPriority.LOW
            elif 'critical' in priority_lower or 'highest' in priority_lower:
                priority = TicketPriority.HIGHEST
            else:
                priority = TicketPriority.MEDIUM
        
        return JiraTicket(
            jira_key=issue.get('key', ''),
            jira_id=str(issue.get('id', '')),
            title=_get(fields, ['summary'], '') or 'Untitled',
            description=description_text or '',
            acceptance_criteria=acceptance_criteria,
            ticket_type=ticket_type,
            status=status,
            priority=priority,
            assignee=_get(fields, ['assignee', 'displayName']),
            reporter=_get(fields, ['reporter', 'displayName'], '') or 'Unknown',
            project_key=_get(fields, ['project', 'key'], ''),
            labels=fields.get('labels', []) or [],
            components=[],
            fix_versions=[],
            created_at=created_at_parsed or dt_class.utcnow(),
            updated_at=updated_at_parsed or dt_class.utcnow(),
            due_date=due_date_parsed,
            story_points=fields.get('customfield_10016'),
            epic_link=fields.get('customfield_10014'),
            parent_key=_get(fields, ['parent', 'key'])
        )
    
    def _extract_acceptance_criteria(self, description: str, fields: Dict[str, Any]) -> Optional[str]:
        """Extract acceptance criteria from description or custom fields."""
        # Helper to convert ADF to text
        def _adf_to_text(adf):
            if adf is None:
                return None
            if isinstance(adf, str):
                return adf
            parts = []
            def walk(node):
                if isinstance(node, dict):
                    if 'text' in node and isinstance(node['text'], str):
                        parts.append(node['text'])
                    if 'content' in node:
                        for child in node['content']:
                            walk(child)
                elif isinstance(node, list):
                    for child in node:
                        walk(child)
            walk(adf)
            return '\n'.join(parts) if parts else None
        
        # Try custom fields first (common field IDs for acceptance criteria)
        ac_custom_fields = [
            'customfield_10020',  # Common AC field
            'customfield_10021',
            'customfield_10026',
            'customfield_10027',
        ]
        
        for field_id in ac_custom_fields:
            if field_id in fields:
                ac_value = fields[field_id]
                if ac_value:
                    # Convert ADF to text if needed
                    if isinstance(ac_value, dict):
                        ac_text = _adf_to_text(ac_value)
                        if ac_text:
                            return ac_text
                    else:
                        return str(ac_value)
        
        # Try to extract from description
        if not description:
            return None
        
        description_lower = description.lower()
        ac_markers = [
            'acceptance criteria:',
            'acceptance criteria',
            'ac:',
            'criteria:',
            'acceptance:'
        ]
        
        for marker in ac_markers:
            if marker in description_lower:
                # Find the section after the marker
                marker_index = description_lower.find(marker)
                ac_section = description[marker_index + len(marker):].strip()
                
                # Extract lines until we hit a new section or end
                lines = ac_section.split('\n')
                ac_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    # Stop if we hit another section header
                    if line_stripped.endswith(':') and len(line_stripped) < 30:
                        # Might be a new section
                        if not any(m in line_stripped.lower() for m in ['given', 'when', 'then', 'and', 'or']):
                            break
                    ac_lines.append(line)
                
                if ac_lines:
                    return '\n'.join(ac_lines).strip()
        
        return None
    
    def _extract_acceptance_criteria_from_text(self, text: str) -> Optional[str]:
        """Extract acceptance criteria from text description."""
        if not text:
            return None
        
        text_lower = text.lower()
        ac_markers = [
            'acceptance criteria:',
            'acceptance criteria',
            'ac:',
            'criteria:',
            'acceptance:'
        ]
        
        for marker in ac_markers:
            if marker in text_lower:
                marker_index = text_lower.find(marker)
                ac_section = text[marker_index + len(marker):].strip()
                
                lines = ac_section.split('\n')
                ac_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    if line_stripped.endswith(':') and len(line_stripped) < 30:
                        if not any(m in line_stripped.lower() for m in ['given', 'when', 'then', 'and', 'or']):
                            break
                    ac_lines.append(line)
                
                if ac_lines:
                    return '\n'.join(ac_lines).strip()
        
        return None

    def _search_tickets_v3_jql(self, jql: str, max_results: int) -> List[JiraTicket]:
        """Direct call to Jira Cloud v3 search/jql endpoint (POST).
        
        This uses the new /rest/api/3/search/jql endpoint which replaced the deprecated
        /rest/api/3/search endpoint. The new endpoint requires POST with JSON body.
        """
        if not all([self.settings.jira_url, self.settings.jira_email, self.settings.jira_api_token]):
            logger.warning("Jira credentials missing for direct v3 call")
            return []
        
        url = self.settings.jira_url.rstrip('/') + '/rest/api/3/search/jql'
        payload = {
            'jql': jql,
            'maxResults': max_results,
            'fields': [
                'summary','description','issuetype','status','priority','assignee','reporter',
                'project','labels','created','updated','duedate','parent','customfield_10016','customfield_10014',
                'customfield_10020','customfield_10021','customfield_10026','customfield_10027'
            ]
        }
        auth = (self.settings.jira_email, self.settings.jira_api_token)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        logger.info(f"Searching Jira with JQL: {jql}")
        logger.debug(f"Jira search URL: {url}")
        logger.debug(f"Jira search payload: {payload}")
        
        try:
            resp = requests.post(url, json=payload, auth=auth, headers=headers, timeout=30)
            
            logger.debug(f"Jira search response status: {resp.status_code}")
            
            if not resp.ok:
                error_msg = f"Jira v3 search/jql failed: {resp.status_code}"
                try:
                    error_data = resp.json()
                    error_messages = error_data.get('errorMessages', [])
                    errors = error_data.get('errors', {})
                    error_msg += f" - Messages: {error_messages}, Errors: {errors}"
                    logger.error(f"Jira API error: {error_msg}")
                    logger.error(f"Response text: {resp.text}")
                except:
                    error_msg += f" - {resp.text}"
                    logger.error(f"Jira API error (non-JSON): {error_msg}")
                raise RuntimeError(error_msg)
            
            data = resp.json() or {}
            logger.debug(f"Jira search response keys: {list(data.keys())}")
            
            # Log full response structure for debugging (but limit size)
            response_str = str(data)
            logger.debug(f"Jira search response (first 2000 chars): {response_str[:2000]}")
            
            # The new /search/jql endpoint returns: { "issues": [...], "total": N, "isLast": bool }
            # Check for issues in the response
            issues = data.get('issues', [])
            if issues is None:
                issues = []
            
            # Sometimes total might be missing or 0, but issues array has items
            total = data.get('total', len(issues))
            max_results_returned = data.get('maxResults', max_results)
            start_at = data.get('startAt', 0)
            is_last = data.get('isLast', True)
            
            logger.info(f"Jira search returned {len(issues)} issues (total in response: {data.get('total', 'N/A')}) for JQL: {jql}")
            logger.info(f"Response metadata: startAt={start_at}, maxResults={max_results_returned}, total={total}, isLast={is_last}")
            
            # If we have issues but total is 0, use issue count
            if len(issues) > 0 and data.get('total', 0) == 0:
                logger.info(f"API returned {len(issues)} issues but total=0. Using issue count as total.")
                total = len(issues)
            
            # Log success if we have issues
            if len(issues) > 0:
                logger.info(f"✓ Successfully retrieved {len(issues)} issues from Jira")
            
            # If no issues found, log warning
            if len(issues) == 0:
                logger.warning(f"No issues found for JQL: {jql}")
                logger.warning(f"This could mean:")
                logger.warning(f"  1. Project doesn't exist or project key is incorrect")
                logger.warning(f"  2. No tickets exist in the project")
                logger.warning(f"  3. User doesn't have permission to view tickets")
                logger.warning(f"  4. JQL query is too restrictive")
                
                # Try to get project info to verify it exists (synchronous check)
                try:
                    # Extract project key from JQL (handles various formats)
                    project_key = None
                    if 'project =' in jql:
                        parts = jql.split('project =')[1].strip()
                        project_key = parts.split()[0].strip()
                        # Remove AND or ORDER if present
                        project_key = project_key.split('AND')[0].strip()
                        project_key = project_key.split('ORDER')[0].strip()
                    
                    if project_key:
                        logger.info(f"Attempting to verify project '{project_key}' exists...")
                        try:
                            # Use REST API to get projects synchronously
                            projects_url = self.settings.jira_url.rstrip('/') + '/rest/api/3/project'
                            projects_auth = (self.settings.jira_email, self.settings.jira_api_token)
                            projects_headers = {'Accept': 'application/json'}
                            projects_resp = requests.get(projects_url, auth=projects_auth, headers=projects_headers, timeout=10)
                            
                            if projects_resp.ok:
                                projects_data = projects_resp.json() or []
                                project_list = [p.get('key', '') for p in projects_data if p.get('key')]
                                project_exists = project_key in project_list
                                
                                if project_exists:
                                    logger.info(f"✓ Project '{project_key}' exists and is accessible")
                                    logger.warning(f"  But query returned 0 tickets. This means:")
                                    logger.warning(f"  - Either no tickets exist in this project")
                                    logger.warning(f"  - Or the JQL filters are too restrictive")
                                else:
                                    logger.error(f"✗ Project '{project_key}' NOT FOUND in accessible projects")
                                    logger.error(f"  Available projects: {project_list}")
                                    logger.error(f"  Please use one of the available project keys")
                            else:
                                logger.warning(f"Could not verify project existence: HTTP {projects_resp.status_code}")
                        except Exception as e:
                            logger.debug(f"Could not verify project existence: {e}")
                except Exception as e:
                    logger.debug(f"Could not verify project existence: {e}", exc_info=True)
            
            if not issues:
                # Log full response for debugging empty results
                logger.warning(f"Response data: {data}")
                return []
            
            # Convert issues to tickets
            tickets = []
            conversion_errors = []
            for idx, issue in enumerate(issues):
                try:
                    issue_key = issue.get('key', f'issue_{idx + 1}')
                    ticket = self._convert_issue_json_to_ticket(issue)
                    tickets.append(ticket)
                    logger.debug(f"✓ Converted {issue_key}: {ticket.title[:50]}")
                except Exception as e:
                    error_msg = str(e)
                    issue_key = issue.get('key', f'issue_{idx + 1}')
                    logger.error(f"✗ Failed to convert issue {idx + 1} ({issue_key}) to ticket: {error_msg}")
                    logger.error(f"Error type: {type(e).__name__}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    conversion_errors.append({
                        'issue_key': issue_key,
                        'error': error_msg,
                        'error_type': type(e).__name__
                    })
                    # Continue with other issues instead of failing completely
                    continue
            
            if conversion_errors:
                logger.warning(f"Failed to convert {len(conversion_errors)} out of {len(issues)} issues:")
                for err in conversion_errors:
                    logger.warning(f"  - {err['issue_key']}: {err['error_type']} - {err['error']}")
            else:
                logger.info(f"✓ Successfully converted all {len(tickets)} issues to tickets")
            
            return tickets
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during Jira search: {e}")
            raise RuntimeError(f"Failed to connect to Jira: {e}")
        except RuntimeError:
            # Re-raise RuntimeError (API errors)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Jira search: {e}", exc_info=True)
            raise
