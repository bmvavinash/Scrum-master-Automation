"""Git hooks endpoints for Jira integration."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from app.services.git_hooks_service import GitHooksService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/git-hooks", tags=["git-hooks"])

# Initialize service
git_hooks_service = GitHooksService()


@router.post("/webhook")
async def handle_git_webhook(
    webhook_data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Handle git webhook events."""
    
    try:
        # Process webhook in background
        background_tasks.add_task(process_git_webhook, webhook_data)
        
        return {"message": "Git webhook received and processing"}
        
    except Exception as e:
        logger.error(f"Failed to process git webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process git webhook")


@router.post("/update-from-branch")
async def update_jira_from_branch(
    branch_name: str,
    git_action: str = "push"
):
    """Update Jira card status based on branch name."""
    
    try:
        success = await git_hooks_service.update_jira_status_from_branch(branch_name, git_action)
        
        if success:
            return {"message": f"Successfully updated Jira card for branch {branch_name}"}
        else:
            return {"message": f"No Jira card found or updated for branch {branch_name}"}
        
    except Exception as e:
        logger.error(f"Failed to update Jira from branch: {e}")
        raise HTTPException(status_code=500, detail="Failed to update Jira from branch")


@router.get("/current-branch")
async def get_current_branch():
    """Get current git branch."""
    
    try:
        branch = git_hooks_service.get_current_branch()
        
        if branch:
            return {"branch": branch}
        else:
            raise HTTPException(status_code=404, detail="Could not determine current branch")
        
    except Exception as e:
        logger.error(f"Failed to get current branch: {e}")
        raise HTTPException(status_code=500, detail="Failed to get current branch")


@router.get("/branches")
async def get_all_branches():
    """Get all git branches."""
    
    try:
        branches = git_hooks_service.get_branch_list()
        
        return {"branches": branches, "count": len(branches)}
        
    except Exception as e:
        logger.error(f"Failed to get branches: {e}")
        raise HTTPException(status_code=500, detail="Failed to get branches")


@router.post("/sync-all")
async def sync_all_branches_to_jira():
    """Sync all branches to their corresponding Jira tickets."""
    
    try:
        results = await git_hooks_service.sync_all_branches_to_jira()
        
        return {
            "message": "Branch sync completed",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to sync branches: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync branches")


@router.post("/extract-jira-key")
async def extract_jira_key_from_branch(branch_name: str):
    """Extract Jira key from branch name."""
    
    try:
        jira_key = git_hooks_service.extract_jira_ticket_from_branch(branch_name)
        
        return {
            "branch_name": branch_name,
            "jira_key": jira_key,
            "found": jira_key is not None
        }
        
    except Exception as e:
        logger.error(f"Failed to extract Jira key: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract Jira key")


async def process_git_webhook(webhook_data: Dict[str, Any]):
    """Background task to process git webhook."""
    
    try:
        # Extract relevant information from webhook
        ref = webhook_data.get("ref", "")
        action = webhook_data.get("action", "push")
        
        # Extract branch name from ref (e.g., "refs/heads/feature/SCRUM-25")
        branch_name = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
        
        logger.info(f"Processing git webhook: {action} for branch {branch_name}")
        
        # Update Jira card status
        success = await git_hooks_service.update_jira_status_from_branch(branch_name, action)
        
        if success:
            logger.info(f"Successfully updated Jira card for branch {branch_name}")
        else:
            logger.info(f"No Jira card updated for branch {branch_name}")
        
    except Exception as e:
        logger.error(f"Failed to process git webhook: {e}")
