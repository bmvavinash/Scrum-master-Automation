"""Jira integration endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from app.models.jira import JiraTicket, JiraProject, TicketType, TicketPriority, TicketStatus
from app.services.jira_service import JiraService
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["jira"])

# Initialize service
jira_service = JiraService()


@router.post("/tickets", response_model=JiraTicket)
async def create_ticket(
    title: str,
    description: str = "",
    ticket_type: TicketType = TicketType.TASK,
    priority: TicketPriority = TicketPriority.MEDIUM,
    assignee: Optional[str] = None,
    project_key: str = "SCRUM",
    labels: List[str] = None,
    story_points: Optional[int] = None
    # db: AsyncIOMotorDatabase = Depends(get_database)  # Commented out - no DB
):
    """Create a new Jira ticket."""
    
    try:
        ticket = await jira_service.create_ticket(
            title=title,
            description=description,
            ticket_type=ticket_type,
            priority=priority,
            assignee=assignee,
            project_key=project_key,
            labels=labels or [],
            story_points=story_points
        )
        
        if not ticket:
            raise HTTPException(status_code=500, detail="Failed to create Jira ticket")
        
        # Store in database - commented out
        # ticket_dict = ticket.dict(by_alias=True, exclude={"id"})
        # result = await db.jira_tickets.insert_one(ticket_dict)
        # ticket.id = str(result.inserted_id)
        
        logger.info(f"Created Jira ticket: {ticket.jira_key}")
        return ticket
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create Jira ticket: {e}")
        raise HTTPException(status_code=500, detail="Failed to create Jira ticket")


@router.get("/tickets", response_model=List[JiraTicket])
async def get_tickets(
    project_key: Optional[str] = None,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    ticket_type: Optional[str] = None,
    reporter: Optional[str] = None,
    view: Optional[str] = 'active',
    limit: int = 50
    # db: AsyncIOMotorDatabase = Depends(get_database)  # Commented out - no DB (reads)
):
    """Get Jira tickets with optional filters."""
    
    try:
        # Verify project exists if project_key is provided
        if project_key:
            try:
                projects = await jira_service.get_projects()
                project_exists = any(p.key == project_key for p in projects)
                if not project_exists:
                    available_projects = [p.key for p in projects]
                    logger.warning(f"Project '{project_key}' not found in accessible projects. Available projects: {available_projects}")
                    # Don't fail, just log - maybe user wants to see if project exists
            except Exception as e:
                logger.debug(f"Could not verify project existence: {e}")
        
        # Build JQL query (always fetch from Jira, never DB)
        jql_parts = []
        if project_key:
            jql_parts.append(f"project = {project_key}")
        if assignee:
            jql_parts.append(f"assignee = {assignee}")
        if reporter:
            jql_parts.append(f"reporter = {reporter}")
        if status:
            jql_parts.append(f"status = '{status}'")
        if priority:
            jql_parts.append(f"priority = '{priority}'")
        if ticket_type:
            jql_parts.append(f"type = '{ticket_type}'")
        
        # Active vs Backlog view - make it optional to avoid empty results
        normalized_view = (view or 'active').lower()
        view_filter_added = False
        if normalized_view == 'active':
            # Try to filter by active sprints, but this might return empty if no sprints exist
            # We'll try with sprint filter first, then fallback if empty
            jql_parts.append("sprint IN openSprints()")
            view_filter_added = True
        elif normalized_view == 'backlog':
            # Show true backlog items only (not assigned to any sprint)
            jql_parts.append("sprint IS EMPTY")
            view_filter_added = True

        # Build final JQL query
        if jql_parts:
            jql = " AND ".join(jql_parts)
            # Add ORDER BY if not already present
            if "ORDER BY" not in jql.upper():
                jql += " ORDER BY created DESC"
        else:
            # Default query if no filters - get recent tickets
            jql = "ORDER BY created DESC"
        
        logger.info(f"Executing JQL query: {jql}")
        logger.debug(f"JQL parameters: project_key={project_key}, view={view}, limit={limit}")
        
        try:
            tickets = await jira_service.search_tickets(jql, limit)
            
            # If no tickets found, try progressive fallbacks
            if len(tickets) == 0:
                # Fallback 1: Remove sprint filter if it was added
                if view_filter_added and normalized_view == 'active':
                    logger.info("No tickets found with sprint filter, trying without sprint filter")
                    jql_parts_without_sprint = [p for p in jql_parts if "sprint" not in p.lower()]
                    if jql_parts_without_sprint:
                        jql_fallback = " AND ".join(jql_parts_without_sprint)
                        if "ORDER BY" not in jql_fallback.upper():
                            jql_fallback += " ORDER BY created DESC"
                        logger.info(f"Trying fallback JQL query: {jql_fallback}")
                        tickets = await jira_service.search_tickets(jql_fallback, limit)
                        logger.info(f"Fallback query returned {len(tickets)} tickets")
                
                # Fallback 2: If still empty and project_key was specified, try without project filter
                if len(tickets) == 0 and project_key:
                    logger.info(f"No tickets found for project '{project_key}', trying query without project filter")
                    jql_parts_no_project = [p for p in jql_parts if not p.startswith("project =")]
                    if jql_parts_no_project:
                        jql_fallback2 = " AND ".join(jql_parts_no_project)
                        if "ORDER BY" not in jql_fallback2.upper():
                            jql_fallback2 += " ORDER BY created DESC"
                    else:
                        jql_fallback2 = "ORDER BY created DESC"
                    logger.info(f"Trying fallback JQL query (no project): {jql_fallback2}")
                    tickets_fallback = await jira_service.search_tickets(jql_fallback2, limit)
                    if len(tickets_fallback) > 0:
                        logger.warning(f"Found {len(tickets_fallback)} tickets without project filter, but 0 with project '{project_key}'")
                        logger.warning(f"This suggests project '{project_key}' either doesn't exist, has no tickets, or user doesn't have access")
                    # Don't use fallback tickets - user requested specific project
                    # tickets = tickets_fallback  # Uncomment if you want to show all tickets when project has none
            
            # Diagnostic logging
            if not jira_service.is_initialized():
                logger.warning("Jira tickets requested but Jira client is not initialized - returning empty or mock upstream")
            
            logger.info(f"Returning {len(tickets)} tickets for JQL: {jql}")
            return tickets
            
        except Exception as e:
            logger.error(f"Error in search_tickets: {e}", exc_info=True)
            # Don't raise HTTPException here, let it be caught by outer try-except
            raise
        
    except Exception as e:
        logger.error(f"Failed to get tickets: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tickets")


@router.get("/tickets/{ticket_key}", response_model=JiraTicket)
async def get_ticket(
    ticket_key: str
    # db: AsyncIOMotorDatabase = Depends(get_database)  # Commented out - no DB
):
    """Get a specific Jira ticket by key."""
    
    try:
        # Fetch directly from Jira
        ticket = await jira_service.get_ticket(ticket_key)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        return ticket
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ticket {ticket_key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get ticket")


@router.put("/tickets/{ticket_key}/status")
async def update_ticket_status(
    ticket_key: str,
    new_status: TicketStatus
    # db: AsyncIOMotorDatabase = Depends(get_database)  # Commented out - no DB
):
    """Update ticket status."""
    
    try:
        # Update in Jira
        success = await jira_service.update_ticket_status(ticket_key, new_status)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update ticket status in Jira")
        
        logger.info(f"Updated ticket {ticket_key} to {new_status.value}")
        return {"message": f"Ticket {ticket_key} updated to {new_status.value}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ticket status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update ticket status")


@router.post("/tickets/{ticket_key}/comments")
async def add_ticket_comment(
    ticket_key: str,
    comment: str
    # db: AsyncIOMotorDatabase = Depends(get_database)  # Commented out - no DB
):
    """Add comment to ticket."""
    
    try:
        success = await jira_service.add_comment(ticket_key, comment)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add comment to ticket")
        
        logger.info(f"Added comment to ticket {ticket_key}")
        return {"message": "Comment added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add comment: {e}")
        raise HTTPException(status_code=500, detail="Failed to add comment")


@router.put("/tickets/{ticket_key}/description")
async def update_ticket_description(
    ticket_key: str,
    description: str
):
    """Update a Jira ticket description (plain text → ADF)."""
    try:
        success = await jira_service.update_ticket_description(ticket_key, description)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update ticket description")
        return {"message": "Description updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update description: {e}")
        raise HTTPException(status_code=500, detail="Failed to update description")


@router.post("/tickets/{ticket_key}/subtasks", response_model=JiraTicket)
async def create_subtask(
    ticket_key: str,
    title: str,
    description: str = "",
    assignee: Optional[str] = None
    # db: AsyncIOMotorDatabase = Depends(get_database)  # Commented out - no DB
):
    """Create a subtask for a ticket."""
    
    try:
        subtask = await jira_service.create_subtask(
            parent_key=ticket_key,
            title=title,
            description=description,
            assignee=assignee
        )
        
        if not subtask:
            raise HTTPException(status_code=500, detail="Failed to create subtask")
        
        # Store in database - commented out
        # subtask_dict = subtask.dict(by_alias=True, exclude={"id"})
        # result = await db.jira_tickets.insert_one(subtask_dict)
        # subtask.id = str(result.inserted_id)
        
        logger.info(f"Created subtask {subtask.jira_key} for {ticket_key}")
        return subtask
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subtask: {e}")
        raise HTTPException(status_code=500, detail="Failed to create subtask")


@router.get("/projects", response_model=List[JiraProject])
async def get_projects():
    """Get all accessible Jira projects."""
    
    try:
        projects = await jira_service.get_projects()
        return projects
        
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to get projects")


@router.get("/test-connection")
async def test_jira_connection():
    """Test Jira connection and return diagnostic information."""
    try:
        diagnostics = {
            "jira_configured": bool(jira_service.settings.jira_url and jira_service.settings.jira_email and jira_service.settings.jira_api_token),
            "jira_initialized": jira_service.is_initialized(),
            "jira_url": jira_service.settings.jira_url,
            "jira_email": jira_service.settings.jira_email,
            "projects": [],
            "test_queries": {},
            "error": None
        }
        
        if diagnostics["jira_configured"]:
            try:
                # Get accessible projects
                projects = await jira_service.get_projects()
                diagnostics["projects"] = [
                    {
                        "key": p.key,
                        "name": p.name,
                        "id": p.id
                    }
                    for p in projects
                ]
                
                # Test queries
                test_queries = [
                    ("All tickets", "ORDER BY created DESC"),
                    ("Project SCRUM", "project = SCRUM ORDER BY created DESC"),
                    ("Any project", "project IS NOT EMPTY ORDER BY created DESC"),
                ]
                
                for query_name, test_jql in test_queries:
                    try:
                        test_results = await jira_service.search_tickets(test_jql, 5)
                        diagnostics["test_queries"][query_name] = {
                            "jql": test_jql,
                            "count": len(test_results),
                            "tickets": [t.jira_key for t in test_results[:5]]
                        }
                    except Exception as e:
                        diagnostics["test_queries"][query_name] = {
                            "jql": test_jql,
                            "error": str(e)
                        }
                        
            except Exception as e:
                diagnostics["error"] = str(e)
                logger.error(f"Test failed: {e}", exc_info=True)
        
        return diagnostics
        
    except Exception as e:
        logger.error(f"Failed to test Jira connection: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test connection: {str(e)}")


@router.get("/search")
async def search_tickets(
    jql: str,
    max_results: int = 50
):
    """Search tickets using JQL."""
    
    try:
        tickets = await jira_service.search_tickets(jql, max_results)
        return {"tickets": [ticket.dict() for ticket in tickets]}
        
    except Exception as e:
        logger.error(f"Failed to search tickets: {e}")
        raise HTTPException(status_code=500, detail="Failed to search tickets")


@router.post("/webhook")
async def handle_jira_webhook(
    webhook_data: dict,
    background_tasks: BackgroundTasks
):
    """Handle Jira webhook events."""
    
    try:
        # Process webhook in background
        background_tasks.add_task(process_jira_webhook, webhook_data)
        
        return {"message": "Webhook received"}
        
    except Exception as e:
        logger.error(f"Failed to process Jira webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


async def process_jira_webhook(webhook_data: dict):
    """Background task to process Jira webhook."""
    
    try:
        # Extract relevant information from webhook
        event_type = webhook_data.get("webhookEvent", "")
        issue = webhook_data.get("issue", {})
        
        logger.info(f"Processing Jira webhook: {event_type} for {issue.get('key', 'unknown')}")
        
        # Here you would typically:
        # 1. Update local database with ticket changes
        # 2. Send notifications to Teams
        # 3. Update related meetings or velocity metrics
        
    except Exception as e:
        logger.error(f"Failed to process Jira webhook: {e}")
