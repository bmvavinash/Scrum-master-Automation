"""Agentic code generation API endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from app.services.agentic_code_service import AgenticCodeService
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agentic", tags=["agentic"])

# Initialize service
agentic_service = AgenticCodeService()


class AgenticWorkflowRequest(BaseModel):
    """Request model for agentic workflow."""
    jira_key: str = Field(..., description="Jira ticket key (e.g., SCRUM-123)")
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional workflow configuration overrides"
    )


class AgenticWorkflowResponse(BaseModel):
    """Response model for agentic workflow."""
    jira_key: str
    status: str
    steps: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    iterations: int
    max_iterations_reached: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)


@router.post("/process", response_model=AgenticWorkflowResponse)
async def process_jira_ticket(
    request: AgenticWorkflowRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Process a Jira ticket through the agentic workflow.
    
    This endpoint:
    1. Fetches Jira ticket details
    2. Generates code using LLM (Bedrock/Cursor/Amazon Q)
    3. Applies code to repository
    4. Validates code (syntax, linters)
    5. Generates and runs tests
    6. Commits and pushes to git branch
    7. Creates Pull Request (if configured)
    8. Updates Jira ticket
    """
    try:
        logger.info(f"Processing Jira ticket: {request.jira_key}")
        
        # Process ticket
        result = await agentic_service.process_jira_ticket(
            jira_key=request.jira_key,
            config=request.config
        )
        
        # Store result in database
        result_doc = {
            **result,
            "created_at": datetime.utcnow(),
            "request_config": request.config
        }
        await db.agentic_workflows.insert_one(result_doc)
        
        return AgenticWorkflowResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to process Jira ticket: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process ticket: {str(e)}")


@router.post("/process/async")
async def process_jira_ticket_async(
    request: AgenticWorkflowRequest,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Process a Jira ticket asynchronously (returns immediately)."""
    try:
        logger.info(f"Queueing async processing for Jira ticket: {request.jira_key}")
        
        # Add to background tasks
        async def process_task():
            try:
                result = await agentic_service.process_jira_ticket(
                    jira_key=request.jira_key,
                    config=request.config
                )
                # Store result in database
                result_doc = {
                    **result,
                    "created_at": datetime.utcnow(),
                    "request_config": request.config
                }
                await db.agentic_workflows.insert_one(result_doc)
            except Exception as e:
                logger.error(f"Background task failed for {request.jira_key}: {e}")
        
        background_tasks.add_task(process_task)
        
        return {
            "status": "queued",
            "jira_key": request.jira_key,
            "message": "Processing started in background"
        }
        
    except Exception as e:
        logger.error(f"Failed to queue Jira ticket: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue ticket: {str(e)}")


@router.get("/workflows")
async def get_workflows(
    jira_key: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get agentic workflow execution history."""
    try:
        query = {}
        if jira_key:
            query["jira_key"] = jira_key
        if status:
            query["status"] = status
        
        cursor = db.agentic_workflows.find(query).sort("created_at", -1).limit(limit)
        workflows = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for workflow in workflows:
            workflow["_id"] = str(workflow["_id"])
        
        return {
            "workflows": workflows,
            "count": len(workflows)
        }
        
    except Exception as e:
        logger.error(f"Failed to get workflows: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workflows")


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific workflow execution by ID."""
    try:
        from bson import ObjectId
        workflow = await db.agentic_workflows.find_one({"_id": ObjectId(workflow_id)})
        
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        workflow["_id"] = str(workflow["_id"])
        return workflow
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workflow")


@router.get("/config")
async def get_workflow_config():
    """Get default workflow configuration."""
    from app.config import get_settings
    settings = get_settings()
    
    return {
        "language": "python",
        "framework": "fastapi",
        "follow_style": settings.codegen_follow_style,
        "generate_tests": settings.codegen_add_tests,
        "run_tests": settings.codegen_run_tests,
        "validate_syntax": settings.codegen_validate_syntax,
        "run_linters": settings.codegen_run_linters,
        "create_pr": settings.agentic_auto_create_pr,
        "pr_draft": False,
        "update_jira_status": False,
        "branch_prefix": settings.agentic_branch_prefix,
        "max_iterations": settings.agentic_max_iterations,
        "analyze_existing_code": True
    }


@router.post("/webhook/jira")
async def jira_webhook_handler(
    webhook_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Handle Jira webhook events for automatic ticket processing."""
    try:
        event_type = webhook_data.get("webhookEvent", "")
        issue = webhook_data.get("issue", {})
        issue_key = issue.get("key")
        
        if not issue_key:
            logger.warning("Jira webhook received without issue key")
            return {"status": "ignored", "reason": "No issue key"}
        
        # Process only certain event types
        processable_events = [
            "jira:issue_created",
            "jira:issue_updated",
            "jira:issue_assigned"
        ]
        
        if event_type not in processable_events:
            logger.info(f"Ignoring Jira webhook event: {event_type}")
            return {"status": "ignored", "reason": f"Event type {event_type} not processable"}
        
        # Check if ticket has a label or custom field that triggers agentic processing
        # For now, process all tickets (can be made configurable)
        issue_fields = issue.get("fields", {})
        labels = issue_fields.get("labels", [])
        
        # Check for trigger label (e.g., "agentic", "auto-code")
        trigger_labels = ["agentic", "auto-code", "auto-generate"]
        should_process = any(label in trigger_labels for label in labels)
        
        # Also check if description contains trigger keyword
        description = issue_fields.get("description", "")
        if not should_process and description:
            trigger_keywords = ["[AGENTIC]", "[AUTO-CODE]", "[AUTO-GENERATE]"]
            should_process = any(keyword in description.upper() for keyword in trigger_keywords)
        
        if not should_process:
            logger.info(f"Jira ticket {issue_key} does not have trigger for agentic processing")
            return {"status": "ignored", "reason": "No trigger found"}
        
        # Queue processing
        logger.info(f"Queuing agentic processing for Jira ticket: {issue_key}")
        
        async def process_task():
            try:
                result = await agentic_service.process_jira_ticket(jira_key=issue_key)
                result_doc = {
                    **result,
                    "created_at": datetime.utcnow(),
                    "triggered_by": "jira_webhook",
                    "webhook_event": event_type
                }
                await db.agentic_workflows.insert_one(result_doc)
            except Exception as e:
                logger.error(f"Background task failed for {issue_key}: {e}")
        
        background_tasks.add_task(process_task)
        
        return {
            "status": "queued",
            "jira_key": issue_key,
            "event_type": event_type,
            "message": "Agentic processing queued"
        }
        
    except Exception as e:
        logger.error(f"Failed to handle Jira webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to handle webhook: {str(e)}")


@router.get("/status/{jira_key}")
async def get_ticket_status(
    jira_key: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get status of agentic processing for a Jira ticket."""
    try:
        # Get latest workflow for this ticket
        workflow = await db.agentic_workflows.find_one(
            {"jira_key": jira_key},
            sort=[("created_at", -1)]
        )
        
        if not workflow:
            return {
                "jira_key": jira_key,
                "status": "not_processed",
                "message": "No workflow found for this ticket"
            }
        
        workflow["_id"] = str(workflow["_id"])
        return {
            "jira_key": jira_key,
            "status": workflow.get("status"),
            "workflow": workflow
        }
        
    except Exception as e:
        logger.error(f"Failed to get ticket status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get ticket status")


