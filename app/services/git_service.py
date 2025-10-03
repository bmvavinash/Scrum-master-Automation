"""Git integration service for GitHub/GitLab."""

import logging
from typing import List, Dict, Any, Optional
from github import Github
from app.config import get_settings
from app.models.git import GitCommit, PullRequest, GitWebhookEvent, GitEventType, PullRequestStatus, PullRequestAction

logger = logging.getLogger(__name__)


class GitService:
    """Service for Git operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.github_client = None
        self._initialize_github()
    
    def _initialize_github(self):
        """Initialize GitHub client."""
        try:
            if not self.settings.github_token:
                logger.warning("GitHub token not configured")
                return
            
            self.github_client = Github(self.settings.github_token)
            logger.info("GitHub client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
            self.github_client = None
    
    async def get_repository(self, owner: str, repo_name: str):
        """Get repository object."""
        
        if not self.github_client:
            logger.error("GitHub client not initialized")
            return None
        
        try:
            return self.github_client.get_repo(f"{owner}/{repo_name}")
        except Exception as e:
            logger.error(f"Failed to get repository {owner}/{repo_name}: {e}")
            return None
    
    async def get_commits(
        self, 
        owner: str, 
        repo_name: str, 
        branch: str = "main",
        since: Optional[str] = None
    ) -> List[GitCommit]:
        """Get commits from repository."""
        
        repo = await self.get_repository(owner, repo_name)
        if not repo:
            return []
        
        try:
            commits = repo.get_commits(sha=branch, since=since)
            git_commits = []
            
            for commit in commits:
                git_commit = GitCommit(
                    sha=commit.sha,
                    message=commit.commit.message,
                    author=commit.commit.author.name,
                    author_email=commit.commit.author.email,
                    committer=commit.commit.committer.name,
                    committer_email=commit.commit.committer.email,
                    timestamp=commit.commit.author.date,
                    url=commit.html_url,
                    branch=branch,
                    repository=f"{owner}/{repo_name}",
                    files_changed=[file.filename for file in commit.files],
                    additions=commit.stats.additions,
                    deletions=commit.stats.deletions,
                    jira_tickets=self._extract_jira_tickets(commit.commit.message)
                )
                git_commits.append(git_commit)
            
            return git_commits
            
        except Exception as e:
            logger.error(f"Failed to get commits: {e}")
            return []
    
    async def get_pull_requests(
        self, 
        owner: str, 
        repo_name: str, 
        state: str = "all"
    ) -> List[PullRequest]:
        """Get pull requests from repository."""
        
        repo = await self.get_repository(owner, repo_name)
        if not repo:
            return []
        
        try:
            prs = repo.get_pulls(state=state, sort="updated", direction="desc")
            pull_requests = []
            
            for pr in prs:
                # Get commits for this PR
                commits = []
                for commit in pr.get_commits():
                    git_commit = GitCommit(
                        sha=commit.sha,
                        message=commit.commit.message,
                        author=commit.commit.author.name,
                        author_email=commit.commit.author.email,
                        committer=commit.commit.committer.name,
                        committer_email=commit.commit.committer.email,
                        timestamp=commit.commit.author.date,
                        url=commit.html_url,
                        branch=pr.head.ref,
                        repository=f"{owner}/{repo_name}",
                        files_changed=[file.filename for file in commit.files],
                        additions=commit.stats.additions,
                        deletions=commit.stats.deletions,
                        jira_tickets=self._extract_jira_tickets(commit.commit.message)
                    )
                    commits.append(git_commit)
                
                pull_request = PullRequest(
                    number=pr.number,
                    title=pr.title,
                    description=pr.body or "",
                    status=PullRequestStatus(pr.state),
                    author=pr.user.login,
                    assignees=[assignee.login for assignee in pr.assignees],
                    reviewers=[reviewer.login for reviewer in pr.requested_reviewers],
                    base_branch=pr.base.ref,
                    head_branch=pr.head.ref,
                    repository=f"{owner}/{repo_name}",
                    created_at=pr.created_at,
                    updated_at=pr.updated_at,
                    merged_at=pr.merged_at,
                    closed_at=pr.closed_at,
                    commits=commits,
                    jira_tickets=self._extract_jira_tickets(pr.title + " " + (pr.body or "")),
                    labels=[label.name for label in pr.labels],
                    milestone=pr.milestone.title if pr.milestone else None
                )
                pull_requests.append(pull_request)
            
            return pull_requests
            
        except Exception as e:
            logger.error(f"Failed to get pull requests: {e}")
            return []
    
    async def get_pull_request(
        self, 
        owner: str, 
        repo_name: str, 
        pr_number: int
    ) -> Optional[PullRequest]:
        """Get specific pull request."""
        
        repo = await self.get_repository(owner, repo_name)
        if not repo:
            return None
        
        try:
            pr = repo.get_pull(pr_number)
            
            # Get commits for this PR
            commits = []
            for commit in pr.get_commits():
                git_commit = GitCommit(
                    sha=commit.sha,
                    message=commit.commit.message,
                    author=commit.commit.author.name,
                    author_email=commit.commit.author.email,
                    committer=commit.commit.committer.name,
                    committer_email=commit.commit.committer.email,
                    timestamp=commit.commit.author.date,
                    url=commit.html_url,
                    branch=pr.head.ref,
                    repository=f"{owner}/{repo_name}",
                    files_changed=[file.filename for file in commit.files],
                    additions=commit.stats.additions,
                    deletions=commit.stats.deletions,
                    jira_tickets=self._extract_jira_tickets(commit.commit.message)
                )
                commits.append(git_commit)
            
            return PullRequest(
                number=pr.number,
                title=pr.title,
                description=pr.body or "",
                status=PullRequestStatus(pr.state),
                author=pr.user.login,
                assignees=[assignee.login for assignee in pr.assignees],
                reviewers=[reviewer.login for reviewer in pr.requested_reviewers],
                base_branch=pr.base.ref,
                head_branch=pr.head.ref,
                repository=f"{owner}/{repo_name}",
                created_at=pr.created_at,
                updated_at=pr.updated_at,
                merged_at=pr.merged_at,
                closed_at=pr.closed_at,
                commits=commits,
                jira_tickets=self._extract_jira_tickets(pr.title + " " + (pr.body or "")),
                labels=[label.name for label in pr.labels],
                milestone=pr.milestone.title if pr.milestone else None
            )
            
        except Exception as e:
            logger.error(f"Failed to get pull request {pr_number}: {e}")
            return None
    
    async def create_pull_request(
        self,
        owner: str,
        repo_name: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main"
    ) -> Optional[PullRequest]:
        """Create a new pull request."""
        
        repo = await self.get_repository(owner, repo_name)
        if not repo:
            return None
        
        try:
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )
            
            return await self.get_pull_request(owner, repo_name, pr.number)
            
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return None
    
    async def add_reviewers(
        self, 
        owner: str, 
        repo_name: str, 
        pr_number: int, 
        reviewers: List[str]
    ) -> bool:
        """Add reviewers to pull request."""
        
        repo = await self.get_repository(owner, repo_name)
        if not repo:
            return False
        
        try:
            pr = repo.get_pull(pr_number)
            pr.create_review_request(reviewers=reviewers)
            logger.info(f"Added reviewers to PR {pr_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to add reviewers to PR {pr_number}: {e}")
            return False
    
    async def merge_pull_request(
        self, 
        owner: str, 
        repo_name: str, 
        pr_number: int,
        merge_method: str = "merge"
    ) -> bool:
        """Merge pull request."""
        
        repo = await self.get_repository(owner, repo_name)
        if not repo:
            return False
        
        try:
            pr = repo.get_pull(pr_number)
            pr.merge(merge_method=merge_method)
            logger.info(f"Merged PR {pr_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to merge PR {pr_number}: {e}")
            return False
    
    async def process_webhook_event(
        self, 
        event_type: str, 
        payload: Dict[str, Any]
    ) -> Optional[GitWebhookEvent]:
        """Process GitHub webhook event."""
        
        try:
            if event_type == "push":
                return self._process_push_event(payload)
            elif event_type == "pull_request":
                return self._process_pull_request_event(payload)
            elif event_type == "pull_request_review":
                return self._process_pull_request_review_event(payload)
            else:
                logger.warning(f"Unsupported webhook event type: {event_type}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to process webhook event: {e}")
            return None
    
    def _process_push_event(self, payload: Dict[str, Any]) -> GitWebhookEvent:
        """Process push webhook event."""
        
        commits = []
        for commit_data in payload.get("commits", []):
            commit = GitCommit(
                sha=commit_data["id"],
                message=commit_data["message"],
                author=commit_data["author"]["name"],
                author_email=commit_data["author"]["email"],
                committer=commit_data["committer"]["name"],
                committer_email=commit_data["committer"]["email"],
                timestamp=commit_data["timestamp"],
                url=commit_data["url"],
                branch=payload["ref"].replace("refs/heads/", ""),
                repository=payload["repository"]["full_name"],
                files_changed=commit_data.get("modified", []) + commit_data.get("added", []) + commit_data.get("removed", []),
                jira_tickets=self._extract_jira_tickets(commit_data["message"])
            )
            commits.append(commit)
        
        return GitWebhookEvent(
            event_type=GitEventType.PUSH,
            action="pushed",
            repository=payload["repository"]["full_name"],
            sender=payload["sender"]["login"],
            timestamp=payload["head_commit"]["timestamp"],
            payload=payload,
            commit=commits[0] if commits else None
        )
    
    def _process_pull_request_event(self, payload: Dict[str, Any]) -> GitWebhookEvent:
        """Process pull request webhook event."""
        
        pr_data = payload["pull_request"]
        
        pull_request = PullRequest(
            number=pr_data["number"],
            title=pr_data["title"],
            description=pr_data["body"] or "",
            status=PullRequestStatus(pr_data["state"]),
            author=pr_data["user"]["login"],
            assignees=[assignee["login"] for assignee in pr_data.get("assignees", [])],
            reviewers=[reviewer["login"] for reviewer in pr_data.get("requested_reviewers", [])],
            base_branch=pr_data["base"]["ref"],
            head_branch=pr_data["head"]["ref"],
            repository=payload["repository"]["full_name"],
            created_at=pr_data["created_at"],
            updated_at=pr_data["updated_at"],
            merged_at=pr_data.get("merged_at"),
            closed_at=pr_data.get("closed_at"),
            jira_tickets=self._extract_jira_tickets(pr_data["title"] + " " + (pr_data["body"] or "")),
            labels=[label["name"] for label in pr_data.get("labels", [])]
        )
        
        return GitWebhookEvent(
            event_type=GitEventType.PULL_REQUEST,
            action=payload["action"],
            repository=payload["repository"]["full_name"],
            sender=payload["sender"]["login"],
            timestamp=pr_data["updated_at"],
            payload=payload,
            pull_request=pull_request
        )
    
    def _process_pull_request_review_event(self, payload: Dict[str, Any]) -> GitWebhookEvent:
        """Process pull request review webhook event."""
        
        return GitWebhookEvent(
            event_type=GitEventType.PULL_REQUEST_REVIEW,
            action=payload["action"],
            repository=payload["repository"]["full_name"],
            sender=payload["sender"]["login"],
            timestamp=payload["review"]["submitted_at"],
            payload=payload
        )
    
    def _extract_jira_tickets(self, text: str) -> List[str]:
        """Extract Jira ticket references from text."""
        import re
        
        # Pattern to match Jira ticket keys (e.g., PROJ-123, ABC-456)
        pattern = r'\b[A-Z][A-Z0-9]+-\d+\b'
        return re.findall(pattern, text)
