"""Git integration endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from app.models.git import GitCommit, PullRequest, GitWebhookEvent, GitEventType
from app.services.git_service import GitService
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/git", tags=["git"])

# Initialize service
git_service = GitService()


@router.get("/repositories/{owner}/{repo}/commits", response_model=List[GitCommit])
async def get_commits(
    owner: str,
    repo: str,
    branch: str = "main",
    since: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get commits from a repository."""
    
    try:
        commits = await git_service.get_commits(owner, repo, branch, since)
        
        # Store commits in database
        if commits:
            commit_dicts = [commit.dict(by_alias=True, exclude={"id"}) for commit in commits]
            await db.git_commits.insert_many(commit_dicts)
        
        return commits
        
    except Exception as e:
        logger.error(f"Failed to get commits: {e}")
        raise HTTPException(status_code=500, detail="Failed to get commits")


@router.get("/repositories/{owner}/{repo}/pull-requests", response_model=List[PullRequest])
async def get_pull_requests(
    owner: str,
    repo: str,
    state: str = "all",
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get pull requests from a repository."""
    
    try:
        pull_requests = await git_service.get_pull_requests(owner, repo, state)
        
        # Store pull requests in database
        if pull_requests:
            pr_dicts = [pr.dict(by_alias=True, exclude={"id"}) for pr in pull_requests]
            await db.pull_requests.insert_many(pr_dicts)
        
        return pull_requests
        
    except Exception as e:
        logger.error(f"Failed to get pull requests: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pull requests")


@router.get("/repositories/{owner}/{repo}/pull-requests/{pr_number}", response_model=PullRequest)
async def get_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific pull request."""
    
    try:
        pull_request = await git_service.get_pull_request(owner, repo, pr_number)
        
        if not pull_request:
            raise HTTPException(status_code=404, detail="Pull request not found")
        
        # Store in database
        pr_dict = pull_request.dict(by_alias=True, exclude={"id"})
        await db.pull_requests.insert_one(pr_dict)
        
        return pull_request
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pull request: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pull request")


@router.post("/repositories/{owner}/{repo}/pull-requests", response_model=PullRequest)
async def create_pull_request(
    owner: str,
    repo: str,
    title: str,
    body: str,
    head_branch: str,
    base_branch: str = "main",
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new pull request."""
    
    try:
        pull_request = await git_service.create_pull_request(
            owner, repo, title, body, head_branch, base_branch
        )
        
        if not pull_request:
            raise HTTPException(status_code=500, detail="Failed to create pull request")
        
        # Store in database
        pr_dict = pull_request.dict(by_alias=True, exclude={"id"})
        result = await db.pull_requests.insert_one(pr_dict)
        pull_request.id = str(result.inserted_id)
        
        logger.info(f"Created pull request: {pull_request.number}")
        return pull_request
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create pull request: {e}")
        raise HTTPException(status_code=500, detail="Failed to create pull request")


@router.post("/repositories/{owner}/{repo}/pull-requests/{pr_number}/reviewers")
async def add_reviewers(
    owner: str,
    repo: str,
    pr_number: int,
    reviewers: List[str]
):
    """Add reviewers to a pull request."""
    
    try:
        success = await git_service.add_reviewers(owner, repo, pr_number, reviewers)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add reviewers")
        
        logger.info(f"Added reviewers to PR {pr_number}")
        return {"message": "Reviewers added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add reviewers: {e}")
        raise HTTPException(status_code=500, detail="Failed to add reviewers")


@router.post("/repositories/{owner}/{repo}/pull-requests/{pr_number}/merge")
async def merge_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    merge_method: str = "merge"
):
    """Merge a pull request."""
    
    try:
        success = await git_service.merge_pull_request(owner, repo, pr_number, merge_method)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to merge pull request")
        
        logger.info(f"Merged PR {pr_number}")
        return {"message": "Pull request merged successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to merge pull request: {e}")
        raise HTTPException(status_code=500, detail="Failed to merge pull request")


@router.post("/webhook")
async def handle_git_webhook(
    webhook_data: dict,
    event_type: str,
    background_tasks: BackgroundTasks
):
    """Handle Git webhook events."""
    
    try:
        # Process webhook in background
        background_tasks.add_task(process_git_webhook, event_type, webhook_data)
        
        return {"message": "Webhook received"}
        
    except Exception as e:
        logger.error(f"Failed to process Git webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@router.get("/commits", response_model=List[GitCommit])
async def get_commits_from_db(
    repository: Optional[str] = None,
    author: Optional[str] = None,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get commits from database with optional filters."""
    
    try:
        filter_dict = {}
        if repository:
            filter_dict["repository"] = repository
        if author:
            filter_dict["author"] = author
        
        cursor = db.git_commits.find(filter_dict).limit(limit).sort("timestamp", -1)
        commits = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            commits.append(GitCommit(**doc))
        
        return commits
        
    except Exception as e:
        logger.error(f"Failed to get commits from database: {e}")
        raise HTTPException(status_code=500, detail="Failed to get commits")


@router.get("/pull-requests", response_model=List[PullRequest])
async def get_pull_requests_from_db(
    repository: Optional[str] = None,
    author: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get pull requests from database with optional filters."""
    
    try:
        filter_dict = {}
        if repository:
            filter_dict["repository"] = repository
        if author:
            filter_dict["author"] = author
        if status:
            filter_dict["status"] = status
        
        cursor = db.pull_requests.find(filter_dict).limit(limit).sort("updated_at", -1)
        pull_requests = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            pull_requests.append(PullRequest(**doc))
        
        return pull_requests
        
    except Exception as e:
        logger.error(f"Failed to get pull requests from database: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pull requests")


async def process_git_webhook(event_type: str, webhook_data: dict):
    """Background task to process Git webhook."""
    
    try:
        # Process the webhook event
        webhook_event = await git_service.process_webhook_event(event_type, webhook_data)
        
        if not webhook_event:
            logger.warning(f"Failed to process webhook event: {event_type}")
            return
        
        # Store webhook event in database
        from app.database import get_database
        db = get_database()
        
        event_dict = webhook_event.dict(by_alias=True, exclude={"id"})
        await db.git_webhook_events.insert_one(event_dict)
        
        # Handle different event types
        if event_type == "push":
            await handle_push_event(webhook_event)
        elif event_type == "pull_request":
            await handle_pull_request_event(webhook_event)
        elif event_type == "pull_request_review":
            await handle_pull_request_review_event(webhook_event)
        
        logger.info(f"Processed {event_type} webhook event")
        
    except Exception as e:
        logger.error(f"Failed to process Git webhook: {e}")


async def handle_push_event(webhook_event: GitWebhookEvent):
    """Handle push webhook event."""
    
    try:
        # Update Jira tickets if they're referenced in commits
        if webhook_event.commit and webhook_event.commit.jira_tickets:
            from app.services.jira_service import JiraService
            jira_service = JiraService()
            
            for ticket_key in webhook_event.commit.jira_tickets:
                # Update ticket status to "In Progress" or add comment
                await jira_service.add_comment(
                    ticket_key, 
                    f"Code pushed to {webhook_event.commit.branch}: {webhook_event.commit.message}"
                )
        
        # Send notification to Teams
        await send_teams_notification(
            "Push Event",
            f"Code pushed to {webhook_event.repository} by {webhook_event.sender}",
            webhook_event.commit.url if webhook_event.commit else None
        )
        
    except Exception as e:
        logger.error(f"Failed to handle push event: {e}")


async def handle_pull_request_event(webhook_event: GitWebhookEvent):
    """Handle pull request webhook event."""
    
    try:
        if not webhook_event.pull_request:
            return
        
        pr = webhook_event.pull_request
        
        # Update Jira tickets if they're referenced
        if pr.jira_tickets:
            from app.services.jira_service import JiraService
            jira_service = JiraService()
            
            for ticket_key in pr.jira_tickets:
                if pr.status.value == "open":
                    await jira_service.update_ticket_status(ticket_key, "In Review")
                elif pr.status.value == "merged":
                    await jira_service.update_ticket_status(ticket_key, "Done")
        
        # Send notification to Teams
        action_text = {
            "opened": "opened",
            "closed": "closed",
            "merged": "merged",
            "approved": "approved"
        }.get(webhook_event.action, webhook_event.action)
        
        await send_teams_notification(
            f"Pull Request {action_text.title()}",
            f"PR #{pr.number}: {pr.title} by {pr.author}",
            f"https://github.com/{pr.repository}/pull/{pr.number}"
        )
        
    except Exception as e:
        logger.error(f"Failed to handle pull request event: {e}")


async def handle_pull_request_review_event(webhook_event: GitWebhookEvent):
    """Handle pull request review webhook event."""
    
    try:
        # Send notification to Teams
        await send_teams_notification(
            "Pull Request Review",
            f"Review {webhook_event.action} by {webhook_event.sender}",
            None
        )
        
    except Exception as e:
        logger.error(f"Failed to handle pull request review event: {e}")


async def send_teams_notification(title: str, message: str, url: str = None):
    """Send notification to Microsoft Teams."""
    
    try:
        # This would integrate with your Teams bot service
        # For now, just log the notification
        logger.info(f"Teams Notification - {title}: {message}")
        if url:
            logger.info(f"URL: {url}")
        
        # TODO: Implement actual Teams notification
        # from app.services.teams_service import TeamsService
        # teams_service = TeamsService()
        # await teams_service.send_notification(title, message, url)
        
    except Exception as e:
        logger.error(f"Failed to send Teams notification: {e}")
