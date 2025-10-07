"""Git hooks service for automatic Jira card status updates based on branch names."""

import logging
import re
from typing import List, Optional, Dict, Any
from app.services.jira_service import JiraService
from app.models.jira import TicketStatus
from app.services.git_service import GitService

logger = logging.getLogger(__name__)


class GitHooksService:
    """Service for handling git hooks and automatic Jira updates."""
    
    def __init__(self):
        self.jira_service = JiraService()
        self.git_service = GitService()
    
    def extract_jira_ticket_from_branch(self, branch_name: str, project_key: str = "SCRUM") -> Optional[str]:
        """
        Extract Jira ticket key from branch name.
        
        Examples:
        - feature/SCRUM-25 -> SCRUM-25
        - bugfix/SCRUM-123 -> SCRUM-123
        - SCRUM-456 -> SCRUM-456
        - hotfix/SCRUM-789 -> SCRUM-789
        - SCRUM-250 -> None (doesn't match SCRUM-25)
        
        Args:
            branch_name: The git branch name
            project_key: The Jira project key (default: SCRUM)
            
        Returns:
            Jira ticket key if found, None otherwise
        """
        try:
            # Pattern to match project key followed by dash and numbers
            # This ensures SCRUM-25 matches but SCRUM-250 doesn't match SCRUM-25
            # Support any project key (not just SCRUM)
            pattern = rf'\b[A-Z][A-Z0-9]+-\d+\b'
            matches = re.findall(pattern, branch_name)
            
            if matches:
                # Return the first match
                ticket_key = matches[0]
                logger.info(f"Extracted Jira ticket {ticket_key} from branch {branch_name}")
                return ticket_key
            
            logger.debug(f"No Jira ticket found in branch {branch_name}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract Jira ticket from branch {branch_name}: {e}")
            return None
    
    async def handle_branch_creation(self, branch_name: str, repository: str, author: str) -> bool:
        """
        Handle branch creation event.
        Update Jira ticket status to 'In Progress' when a feature branch is created.
        
        Args:
            branch_name: The new branch name
            repository: The repository name
            author: The author who created the branch
            
        Returns:
            True if Jira ticket was updated successfully, False otherwise
        """
        try:
            ticket_key = self.extract_jira_ticket_from_branch(branch_name)
            if not ticket_key:
                logger.debug(f"No Jira ticket found in branch {branch_name}")
                return False
            
            # Check if ticket exists in Jira
            ticket = await self.jira_service.get_ticket(ticket_key)
            if not ticket:
                logger.warning(f"Jira ticket {ticket_key} not found")
                return False
            
            # Update ticket status to 'In Progress'
            success = await self.jira_service.update_ticket_status(ticket_key, TicketStatus.IN_PROGRESS)
            
            if success:
                # Add a comment about the branch creation
                comment = f"Feature branch '{branch_name}' created by {author} in {repository}. Moving to In Progress."
                await self.jira_service.add_comment(ticket_key, comment)
                
                logger.info(f"Updated Jira ticket {ticket_key} to In Progress for branch {branch_name}")
                return True
            else:
                logger.warning(f"Failed to update Jira ticket {ticket_key} status")
                return False
                
        except Exception as e:
            logger.error(f"Failed to handle branch creation for {branch_name}: {e}")
            return False
    
    async def handle_branch_push(self, branch_name: str, repository: str, author: str, commit_message: str) -> bool:
        """
        Handle branch push event.
        Add comment to Jira ticket when code is pushed to a feature branch.
        
        Args:
            branch_name: The branch name
            repository: The repository name
            author: The author who pushed
            commit_message: The commit message
            
        Returns:
            True if Jira ticket was updated successfully, False otherwise
        """
        try:
            ticket_key = self.extract_jira_ticket_from_branch(branch_name)
            if not ticket_key:
                logger.debug(f"No Jira ticket found in branch {branch_name}")
                return False
            
            # Check if ticket exists in Jira
            ticket = await self.jira_service.get_ticket(ticket_key)
            if not ticket:
                logger.warning(f"Jira ticket {ticket_key} not found")
                return False
            
            # If ticket is still in To Do, transition it to In Progress on first push
            transitioned = False
            try:
                if getattr(ticket, "status", None) == TicketStatus.TO_DO:
                    moved = await self.jira_service.update_ticket_status(ticket_key, TicketStatus.IN_PROGRESS)
                    if moved:
                        transitioned = True
                        logger.info(f"Moved Jira ticket {ticket_key} to In Progress due to push on {branch_name}")
            except Exception as e:
                logger.warning(f"Could not transition ticket {ticket_key} on push: {e}")

            # Add a comment about the push
            comment_prefix = "Ticket moved to 'In Progress'. " if transitioned else ""
            comment = f"{comment_prefix}Code pushed to branch '{branch_name}' by {author} in {repository}.\n\nCommit: {commit_message}"
            success = await self.jira_service.add_comment(ticket_key, comment)
            
            if success:
                logger.info(f"Added comment to Jira ticket {ticket_key} for push to {branch_name}")
                return True
            else:
                logger.warning(f"Failed to add comment to Jira ticket {ticket_key}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to handle branch push for {branch_name}: {e}")
            return False
    
    async def handle_pull_request_created(self, branch_name: str, repository: str, author: str, pr_number: int) -> bool:
        """
        Handle pull request creation event.
        Update Jira ticket status to 'In Review' when a PR is created.
        
        Args:
            branch_name: The branch name
            repository: The repository name
            author: The author who created the PR
            pr_number: The pull request number
            
        Returns:
            True if Jira ticket was updated successfully, False otherwise
        """
        try:
            ticket_key = self.extract_jira_ticket_from_branch(branch_name)
            if not ticket_key:
                logger.debug(f"No Jira ticket found in branch {branch_name}")
                return False
            
            # Check if ticket exists in Jira
            ticket = await self.jira_service.get_ticket(ticket_key)
            if not ticket:
                logger.warning(f"Jira ticket {ticket_key} not found")
                return False
            
            # Update ticket status to 'In Review'
            success = await self.jira_service.update_ticket_status(ticket_key, TicketStatus.IN_REVIEW)
            
            if success:
                # Add a comment about the PR creation
                comment = f"Pull Request #{pr_number} created by {author} in {repository} for branch '{branch_name}'. Moving to In Review."
                await self.jira_service.add_comment(ticket_key, comment)
                
                logger.info(f"Updated Jira ticket {ticket_key} to In Review for PR #{pr_number}")
                return True
            else:
                logger.warning(f"Failed to update Jira ticket {ticket_key} status")
                return False
                
        except Exception as e:
            logger.error(f"Failed to handle PR creation for {branch_name}: {e}")
            return False
    
    async def handle_pull_request_merged(self, branch_name: str, repository: str, author: str, pr_number: int) -> bool:
        """
        Handle pull request merge event.
        Update Jira ticket status to 'Done' when a PR is merged.
        
        Args:
            branch_name: The branch name
            repository: The repository name
            author: The author who merged the PR
            pr_number: The pull request number
            
        Returns:
            True if Jira ticket was updated successfully, False otherwise
        """
        try:
            ticket_key = self.extract_jira_ticket_from_branch(branch_name)
            if not ticket_key:
                logger.debug(f"No Jira ticket found in branch {branch_name}")
                return False
            
            # Check if ticket exists in Jira
            ticket = await self.jira_service.get_ticket(ticket_key)
            if not ticket:
                logger.warning(f"Jira ticket {ticket_key} not found")
                return False
            
            # Update ticket status to 'Done'
            success = await self.jira_service.update_ticket_status(ticket_key, TicketStatus.DONE)
            
            if success:
                # Add a comment about the PR merge
                comment = f"Pull Request #{pr_number} merged by {author} in {repository} for branch '{branch_name}'. Moving to Done."
                await self.jira_service.add_comment(ticket_key, comment)
                
                logger.info(f"Updated Jira ticket {ticket_key} to Done for merged PR #{pr_number}")
                return True
            else:
                logger.warning(f"Failed to update Jira ticket {ticket_key} status")
                return False
                
        except Exception as e:
            logger.error(f"Failed to handle PR merge for {branch_name}: {e}")
            return False
    
    async def handle_pull_request_closed(self, branch_name: str, repository: str, author: str, pr_number: int) -> bool:
        """
        Handle pull request close event (without merge).
        Update Jira ticket status to 'To Do' when a PR is closed without merge.
        
        Args:
            branch_name: The branch name
            repository: The repository name
            author: The author who closed the PR
            pr_number: The pull request number
            
        Returns:
            True if Jira ticket was updated successfully, False otherwise
        """
        try:
            ticket_key = self.extract_jira_ticket_from_branch(branch_name)
            if not ticket_key:
                logger.debug(f"No Jira ticket found in branch {branch_name}")
                return False
            
            # Check if ticket exists in Jira
            ticket = await self.jira_service.get_ticket(ticket_key)
            if not ticket:
                logger.warning(f"Jira ticket {ticket_key} not found")
                return False
            
            # Update ticket status to 'To Do' (reopened)
            success = await self.jira_service.update_ticket_status(ticket_key, TicketStatus.TO_DO)
            
            if success:
                # Add a comment about the PR close
                comment = f"Pull Request #{pr_number} closed by {author} in {repository} for branch '{branch_name}'. Moving back to To Do."
                await self.jira_service.add_comment(ticket_key, comment)
                
                logger.info(f"Updated Jira ticket {ticket_key} to To Do for closed PR #{pr_number}")
                return True
            else:
                logger.warning(f"Failed to update Jira ticket {ticket_key} status")
                return False
                
        except Exception as e:
            logger.error(f"Failed to handle PR close for {branch_name}: {e}")
            return False
    
    async def update_jira_status_from_branch(self, branch_name: str, git_action: str = "push") -> bool:
        """
        Update Jira ticket status based on branch name and git action.
        
        Args:
            branch_name: The branch name
            git_action: The git action (push, pull_request, etc.)
            
        Returns:
            True if Jira ticket was updated successfully, False otherwise
        """
        try:
            ticket_key = self.extract_jira_ticket_from_branch(branch_name)
            if not ticket_key:
                logger.debug(f"No Jira ticket found in branch {branch_name}")
                return False
            
            # Check if ticket exists in Jira
            ticket = await self.jira_service.get_ticket(ticket_key)
            if not ticket:
                logger.warning(f"Jira ticket {ticket_key} not found")
                return False
            
            # Determine status based on git action
            if git_action == "push":
                # If in To Do, move to In Progress first
                transitioned = False
                try:
                    if getattr(ticket, "status", None) == TicketStatus.TO_DO:
                        moved = await self.jira_service.update_ticket_status(ticket_key, TicketStatus.IN_PROGRESS)
                        if moved:
                            transitioned = True
                            logger.info(f"Moved Jira ticket {ticket_key} to In Progress due to push on {branch_name}")
                except Exception as e:
                    logger.warning(f"Could not transition ticket {ticket_key} on push: {e}")

                # Add push comment
                prefix = "Ticket moved to 'In Progress'. " if transitioned else ""
                comment = f"{prefix}Code pushed to branch '{branch_name}'"
                success = await self.jira_service.add_comment(ticket_key, comment)
                if success:
                    logger.info(f"Added comment to Jira ticket {ticket_key} for push to {branch_name}")
                    return True
            elif git_action == "pull_request":
                # For PR, move to In Review
                success = await self.jira_service.update_ticket_status(ticket_key, TicketStatus.IN_REVIEW)
                if success:
                    comment = f"Pull Request created for branch '{branch_name}'. Moving to In Review."
                    await self.jira_service.add_comment(ticket_key, comment)
                    logger.info(f"Updated Jira ticket {ticket_key} to In Review for PR")
                    return True
            elif git_action == "merge":
                # For merge, move to Done
                success = await self.jira_service.update_ticket_status(ticket_key, TicketStatus.DONE)
                if success:
                    comment = f"Branch '{branch_name}' merged. Moving to Done."
                    await self.jira_service.add_comment(ticket_key, comment)
                    logger.info(f"Updated Jira ticket {ticket_key} to Done for merge")
                    return True
            
            return False
                
        except Exception as e:
            logger.error(f"Failed to update Jira status from branch {branch_name}: {e}")
            return False

    async def process_git_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Process git events and update Jira tickets accordingly.
        
        Args:
            event_type: Type of git event (push, pull_request, etc.)
            event_data: Event data containing branch, repository, author info
            
        Returns:
            True if processing was successful, False otherwise
        """
        try:
            branch_name = event_data.get('branch_name', '')
            repository = event_data.get('repository', '')
            author = event_data.get('author', '')
            
            if not branch_name:
                logger.warning("No branch name provided in event data")
                return False
            
            if event_type == 'push':
                commit_message = event_data.get('commit_message', '')
                return await self.handle_branch_push(branch_name, repository, author, commit_message)
            
            elif event_type == 'pull_request_opened':
                pr_number = event_data.get('pr_number', 0)
                return await self.handle_pull_request_created(branch_name, repository, author, pr_number)
            
            elif event_type == 'pull_request_merged':
                pr_number = event_data.get('pr_number', 0)
                return await self.handle_pull_request_merged(branch_name, repository, author, pr_number)
            
            elif event_type == 'pull_request_closed':
                pr_number = event_data.get('pr_number', 0)
                return await self.handle_pull_request_closed(branch_name, repository, author, pr_number)
            
            else:
                logger.warning(f"Unsupported git event type: {event_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to process git event {event_type}: {e}")
            return False