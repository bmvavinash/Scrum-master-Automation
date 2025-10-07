"""Git integration endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from typing import List, Optional
from app.models.git import GitCommit, PullRequest, GitWebhookEvent, GitEventType
from app.models.jira import TicketStatus
from app.config import get_settings
import hmac
import hashlib
from app.services.git_service import GitService
from app.services.git_hooks_service import GitHooksService
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/git", tags=["git"])

# Initialize services
git_service = GitService()
git_hooks_service = GitHooksService()


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
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle GitHub webhook events with HMAC verification and header-based event detection."""
    try:
        settings = get_settings()
        # Normalize secret to avoid trailing spaces/quotes issues from .env
        secret = (settings.github_webhook_secret or "").strip().strip("'\"")

        # Read raw body for signature verification
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8")

        # Verify signature if secret is configured
        sig256 = request.headers.get("X-Hub-Signature-256", "")
        sig1 = request.headers.get("X-Hub-Signature", "")
        if secret:
            # Compute both digests to support either header GitHub sends
            expected256 = hmac.new(
                key=secret.encode("utf-8"),
                msg=body_bytes,
                digestmod=hashlib.sha256,
            ).hexdigest()
            expected1 = hmac.new(
                key=secret.encode("utf-8"),
                msg=body_bytes,
                digestmod=hashlib.sha1,
            ).hexdigest()

            match256 = hmac.compare_digest(sig256, f"sha256={expected256}") if sig256 else False
            match1 = hmac.compare_digest(sig1, f"sha1={expected1}") if sig1 else False

            if not (match256 or match1):
                logger.warning(
                    "GitHub webhook signature verification failed (present: sha256=%s sha1=%s)",
                    bool(sig256), bool(sig1)
                )
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Detect event type from headers
        event_type = request.headers.get("X-GitHub-Event", "")
        if not event_type:
            raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")

        # Parse JSON payload
        webhook_data = await request.json()

        # Process webhook in background
        background_tasks.add_task(process_git_webhook, event_type, webhook_data)
        return {"message": "Webhook received"}

    except HTTPException:
        raise
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
        
        # Store webhook event in database and persist derived entities
        from app.database import get_database
        db = get_database()
        
        event_dict = webhook_event.dict(by_alias=True, exclude={"id"})
        await db.git_webhook_events.insert_one(event_dict)
        
        # Persist commit or PR for frontend lists
        if webhook_event.commit:
            commit_dict = webhook_event.commit.dict(by_alias=True, exclude={"id"})
            await db.git_commits.insert_one(commit_dict)
        if webhook_event.pull_request:
            pr_dict = webhook_event.pull_request.dict(by_alias=True, exclude={"id"})
            # Upsert by repository + number
            await db.pull_requests.update_one(
                {"repository": pr_dict.get("repository"), "number": pr_dict.get("number")},
                {"$set": pr_dict},
                upsert=True
            )
        
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
        if webhook_event.commit:
            # Use git hooks service to handle branch-based Jira updates
            event_data = {
                'branch_name': webhook_event.commit.branch,
                'repository': webhook_event.repository,
                'author': webhook_event.commit.author,
                'commit_message': webhook_event.commit.message
            }
            
            # Process the push event through git hooks
            await git_hooks_service.process_git_event('push', event_data)
            
            # Also handle traditional Jira ticket references in commit messages
            if webhook_event.commit.jira_tickets:
                from app.services.jira_service import JiraService
                jira_service = JiraService()
                
                for ticket_key in webhook_event.commit.jira_tickets:
                    # Add comment about the commit
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
        
        # Use git hooks service to handle branch-based Jira updates
        event_data = {
            'branch_name': pr.head_branch,
            'repository': pr.repository,
            'author': pr.author,
            'pr_number': pr.number
        }
        
        # Process the PR event through git hooks based on action
        if webhook_event.action == "opened":
            await git_hooks_service.process_git_event('pull_request_opened', event_data)
        elif webhook_event.action == "closed":
            # On close, treat as merged if any of these indicate merge
            is_merged = (
                (getattr(pr, "status", None) and pr.status.value == "merged")
                or getattr(pr, "merged", False)
                or (getattr(pr, "merged_at", None) is not None)
            )
            if is_merged:
                await git_hooks_service.process_git_event('pull_request_merged', event_data)
            else:
                await git_hooks_service.process_git_event('pull_request_closed', event_data)
        
        # Also handle traditional Jira ticket references in PR title/description
        if pr.jira_tickets:
            from app.services.jira_service import JiraService
            jira_service = JiraService()
            
            for ticket_key in pr.jira_tickets:
                # Map PR state/actions to Jira workflow
                if pr.status.value == "open":
                    await jira_service.update_ticket_status(ticket_key, TicketStatus.IN_REVIEW)
                elif pr.status.value == "merged":
                    await jira_service.update_ticket_status(ticket_key, TicketStatus.DONE)
        
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
        # Optional: advance Jira to Ready for Build on approval if tickets referenced
        try:
            from app.services.jira_service import JiraService
            from app.models.jira import TicketStatus as _TS
            jira_service = JiraService()
            payload = webhook_event.payload or {}
            review_state = (payload.get("review") or {}).get("state", "").lower()
            pr = webhook_event.pull_request
            if pr and pr.jira_tickets and review_state == "approved":
                for ticket_key in pr.jira_tickets:
                    await jira_service.update_ticket_status(ticket_key, _TS.READY_FOR_BUILD)
        except Exception as e:
            logger.warning(f"Failed Jira transition on PR review: {e}")

        # Send notification to Teams
        await send_teams_notification(
            "Pull Request Review",
            f"Review {webhook_event.action} by {webhook_event.sender}",
            None
        )
        
    except Exception as e:
        logger.error(f"Failed to handle pull request review event: {e}")


@router.post("/hooks/trigger")
async def trigger_git_hook(
    event_type: str,
    branch_name: str,
    repository: str,
    author: str,
    commit_message: str = "",
    pr_number: int = 0
):
    """Manually trigger a git hook for testing purposes."""
    
    try:
        event_data = {
            'branch_name': branch_name,
            'repository': repository,
            'author': author,
            'commit_message': commit_message,
            'pr_number': pr_number
        }
        
        success = await git_hooks_service.process_git_event(event_type, event_data)
        
        if success:
            return {"message": f"Git hook {event_type} processed successfully for branch {branch_name}"}
        else:
            return {"message": f"Git hook {event_type} processed but no Jira ticket was updated"}
        
    except Exception as e:
        logger.error(f"Failed to trigger git hook: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger git hook")


@router.get("/hooks/extract-ticket")
async def extract_jira_ticket_from_branch(
    branch_name: str,
    project_key: str = "SCRUM"
):
    """Extract Jira ticket key from branch name for testing."""
    
    try:
        ticket_key = git_hooks_service.extract_jira_ticket_from_branch(branch_name, project_key)
        
        if ticket_key:
            return {"ticket_key": ticket_key, "branch_name": branch_name}
        else:
            return {"ticket_key": None, "branch_name": branch_name, "message": "No Jira ticket found in branch name"}
        
    except Exception as e:
        logger.error(f"Failed to extract Jira ticket from branch: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract Jira ticket")


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
