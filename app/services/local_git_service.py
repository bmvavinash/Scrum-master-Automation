"""Local Git service for repository operations."""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import git
from github import Github
from app.config import get_settings

logger = logging.getLogger(__name__)


class LocalGitService:
    """Service for local Git repository operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.github_client = None
        self._repos_cache = {}  # Cache for repository objects
        self._initialize_github()
    
    def _initialize_github(self):
        """Initialize GitHub client."""
        try:
            if self.settings.github_token:
                self.github_client = Github(self.settings.github_token)
                logger.info("GitHub client initialized successfully")
            else:
                logger.warning("GitHub token not configured")
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
    
    def _force_remove_directory(self, path: str, max_retries: int = 5):
        """Force remove a directory with retries for locked files."""
        import time
        for attempt in range(max_retries):
            try:
                if os.path.exists(path):
                    # Try to remove read-only files first
                    for root, dirs, files in os.walk(path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                os.chmod(file_path, 0o777)
                            except:
                                pass
                        for dir in dirs:
                            dir_path = os.path.join(root, dir)
                            try:
                                os.chmod(dir_path, 0o777)
                            except:
                                pass
                    shutil.rmtree(path, ignore_errors=True)
                    # Verify it's removed
                    if not os.path.exists(path):
                        logger.info(f"Successfully removed directory: {path}")
                        return
                    else:
                        logger.warning(f"Directory still exists after removal attempt {attempt + 1}")
                        time.sleep(1)  # Wait before retry
                else:
                    return
            except Exception as e:
                logger.warning(f"Failed to remove directory (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                else:
                    logger.error(f"Failed to remove directory after {max_retries} attempts: {path}")
                    raise
    
    async def clone_or_get_repository(
        self,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        local_path: Optional[str] = None
    ) -> Optional[git.Repo]:
        """Clone repository or get existing repository object.
        
        Args:
            repo_owner: Repository owner (uses config if not provided)
            repo_name: Repository name (uses config if not provided)
            local_path: Local path to repository (uses config if not provided)
        
        Returns:
            Git repository object or None if failed
        """
        try:
            repo_owner = repo_owner or self.settings.github_repo_owner
            repo_name = repo_name or self.settings.github_repo_name
            local_path = local_path or self.settings.github_repo_path
            
            # Validate configuration
            if not repo_owner:
                error_msg = "GitHub repository owner not configured. Set GITHUB_REPO_OWNER in .env file."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if not repo_name:
                error_msg = "GitHub repository name not configured. Set GITHUB_REPO_NAME in .env file."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if not self.settings.github_token:
                error_msg = "GitHub token not configured. Set GITHUB_TOKEN in .env file."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.info(f"Repository configuration: owner={repo_owner}, name={repo_name}, path={local_path or 'auto'}")
            
            # CRITICAL: Always use a dedicated directory for agentic repository
            # NEVER use the current backend repository directory
            current_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            backend_git_dir = os.path.join(current_backend_dir, '.git')
            
            # Determine the local path for the agentic repository
            # Always use a dedicated repos directory, never the backend repo
            if not local_path:
                # Use a dedicated repos directory in the backend folder
                repos_dir = os.path.join(current_backend_dir, "repos")
                os.makedirs(repos_dir, exist_ok=True)
                local_path = os.path.join(repos_dir, f"{repo_owner}_{repo_name}")
                logger.info(f"Using dedicated repository directory: {local_path}")
            else:
                # If path is provided, verify it's NOT the current backend repository
                local_path_abs = os.path.abspath(local_path)
                backend_dir_abs = os.path.abspath(current_backend_dir)
                
                # Check if the path is the backend directory or contains backend's .git
                if local_path_abs == backend_dir_abs or os.path.exists(os.path.join(local_path, '.git')) and os.path.samefile(os.path.join(local_path, '.git'), backend_git_dir) if os.path.exists(backend_git_dir) else False:
                    logger.error(f"SECURITY: Cannot use backend repository directory for agentic operations!")
                    logger.error(f"Backend directory: {backend_dir_abs}")
                    logger.error(f"Requested path: {local_path_abs}")
                    raise ValueError(
                        f"Cannot use backend repository directory for agentic operations. "
                        f"Use a separate directory or leave GITHUB_REPO_PATH empty to auto-create one."
                    )
                
                # Verify the provided path doesn't point to backend directory
                if os.path.exists(local_path) and os.path.exists(backend_git_dir):
                    try:
                        if os.path.samefile(local_path, backend_dir_abs):
                            logger.error(f"SECURITY: Provided path is the backend directory!")
                            raise ValueError(f"Cannot use backend repository directory: {local_path}")
                    except OSError:
                        # Files might not exist or be on different filesystems
                        pass
                
                logger.info(f"Using provided repository directory: {local_path}")
            
            # FINAL SAFETY CHECK: Ensure we're not using the backend repository
            local_path_abs = os.path.abspath(local_path)
            backend_dir_abs = os.path.abspath(current_backend_dir)
            if local_path_abs == backend_dir_abs:
                logger.error(f"SECURITY: Cannot use backend repository directory!")
                raise ValueError(f"Agentic operations cannot use backend repository: {local_path}")
            
            # If local path exists and is a git repo, verify it matches the expected repository
            if os.path.exists(local_path):
                git_dir = os.path.join(local_path, '.git')
                if os.path.exists(git_dir):
                    logger.info(f"Found existing repository at {local_path}")
                    try:
                        repo = git.Repo(local_path)
                        # Verify it's the correct repository (must match owner/name)
                        remote_url = repo.remotes.origin.url
                        expected_repo = f"{repo_owner}/{repo_name}"
                        expected_repo_lower = expected_repo.lower()
                        remote_url_lower = remote_url.lower()
                        
                        # Check if repository matches (case-insensitive)
                        repo_matches = (
                            repo_name.lower() in remote_url_lower and 
                            repo_owner.lower() in remote_url_lower
                        )
                        
                        if repo_matches:
                            logger.info(f"✅ Verified repository: {remote_url} matches {expected_repo}")
                            logger.info(f"   Using repository: {local_path}")
                            return repo
                        else:
                            logger.warning(f"⚠️  Repository mismatch detected!")
                            logger.warning(f"   Found: {remote_url}")
                            logger.warning(f"   Expected: {expected_repo}")
                            logger.info(f"   Removing mismatched repository and cloning correct one...")
                            # Close repo before removing
                            try:
                                repo.close()
                            except:
                                pass
                            # Force remove with retries
                            self._force_remove_directory(local_path)
                    except Exception as e:
                        logger.error(f"Failed to open existing repository: {e}")
                        logger.info(f"Removing corrupted repository and cloning fresh")
                        if os.path.exists(local_path):
                            self._force_remove_directory(local_path)
                else:
                    logger.warning(f"Path {local_path} exists but is not a git repository, removing it")
                    self._force_remove_directory(local_path)
            
            # Clone if doesn't exist
            if not os.path.exists(local_path):
                # Use token in URL for authentication
                repo_url = f"https://{self.settings.github_token}@github.com/{repo_owner}/{repo_name}.git"
                logger.info(f"Cloning repository {repo_owner}/{repo_name} to {local_path}")
                logger.debug(f"Repository URL: https://github.com/{repo_owner}/{repo_name}.git")
                
                try:
                    repo = git.Repo.clone_from(repo_url, local_path, depth=1)
                    logger.info(f"Repository cloned successfully to {local_path}")
                except git.exc.GitCommandError as e:
                    error_msg = f"Git clone failed: {e}"
                    logger.error(error_msg)
                    # Check for common errors
                    if "Authentication failed" in str(e) or "401" in str(e):
                        raise ValueError("GitHub authentication failed. Check GITHUB_TOKEN in .env file.")
                    elif "Repository not found" in str(e) or "404" in str(e):
                        raise ValueError(f"Repository {repo_owner}/{repo_name} not found. Check GITHUB_REPO_OWNER and GITHUB_REPO_NAME.")
                    else:
                        raise
            else:
                logger.info(f"Repository already exists at {local_path}, opening...")
                repo = git.Repo(local_path)
                # Pull latest changes
                try:
                    logger.info(f"Pulling latest changes from {repo_owner}/{repo_name}")
                    repo.remotes.origin.pull()
                    logger.info("Repository updated successfully")
                except git.exc.GitCommandError as e:
                    logger.warning(f"Failed to pull latest changes: {e}")
                    # Continue anyway - repository exists
            
            # Cache repository
            cache_key = f"{repo_owner}/{repo_name}"
            self._repos_cache[cache_key] = repo
            
            logger.info(f"Repository ready: {repo.working_dir}, branch: {repo.active_branch.name}")
            return repo
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_msg = f"Failed to clone or get repository: {e}"
            logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    
    async def create_branch(
        self,
        repo: git.Repo,
        branch_name: str,
        base_branch: Optional[str] = None
    ) -> bool:
        """Create a new branch from base branch.
        
        Args:
            repo: Git repository object
            branch_name: Name of the new branch
            base_branch: Base branch name (defaults to config base branch)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            base_branch = base_branch or self.settings.github_base_branch
            
            logger.info(f"Creating branch '{branch_name}' from '{base_branch}'")
            
            # Check if we're already on the target branch
            try:
                current_branch = repo.active_branch.name
                if current_branch == branch_name:
                    logger.info(f"Already on branch '{branch_name}'")
                    return True
            except Exception as e:
                logger.warning(f"Could not determine current branch: {e}")
            
            # Check if branch already exists locally
            local_branches = [ref.name for ref in repo.heads]
            if branch_name in local_branches:
                logger.info(f"Branch '{branch_name}' already exists locally, checking out")
                try:
                    repo.git.checkout(branch_name)
                    # Try to pull latest changes if remote exists
                    try:
                        if repo.remotes.origin.exists():
                            repo.remotes.origin.pull()
                    except Exception as e:
                        logger.warning(f"Could not pull from origin: {e}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to checkout existing branch: {e}")
                    # Continue to try creating fresh
            
            # Check if branch exists on remote
            remote_branches = []
            try:
                if repo.remotes.origin.exists():
                    for ref in repo.remotes.origin.refs:
                        # Extract branch name from ref (e.g., 'origin/feature/SCRUM-38' -> 'feature/SCRUM-38')
                        ref_name = ref.name
                        if ref_name.startswith('origin/'):
                            remote_branches.append(ref_name.replace('origin/', ''))
            except Exception as e:
                logger.warning(f"Could not fetch remote branches: {e}")
            
            if branch_name in remote_branches:
                logger.info(f"Branch '{branch_name}' exists on remote, checking out and tracking")
                try:
                    # Checkout and track remote branch
                    repo.git.checkout('-b', branch_name, f'origin/{branch_name}')
                    return True
                except Exception as e:
                    logger.warning(f"Failed to checkout remote branch: {e}")
                    # Try creating local branch that tracks remote
                    try:
                        repo.git.checkout('-b', branch_name, '--track', f'origin/{branch_name}')
                        return True
                    except Exception as e2:
                        logger.error(f"Failed to track remote branch: {e2}")
                        # Continue to create new branch
            
            # Ensure we're on the base branch before creating new branch
            try:
                # Check if base branch exists
                if base_branch not in local_branches:
                    # Try to checkout from remote
                    try:
                        if repo.remotes.origin.exists():
                            repo.git.checkout('-b', base_branch, f'origin/{base_branch}')
                            logger.info(f"Checked out base branch '{base_branch}' from remote")
                        else:
                            logger.error(f"Base branch '{base_branch}' not found locally and no remote")
                            return False
                    except Exception as e:
                        logger.error(f"Base branch '{base_branch}' not found: {e}")
                        return False
                else:
                    # Checkout base branch
                    repo.git.checkout(base_branch)
                    logger.info(f"Checked out base branch '{base_branch}'")
                    
                    # Try to pull latest changes
                    try:
                        if repo.remotes.origin.exists():
                            repo.remotes.origin.pull()
                    except Exception as e:
                        logger.warning(f"Could not pull latest changes: {e}")
                        # Continue anyway
            except Exception as e:
                logger.error(f"Failed to checkout base branch '{base_branch}': {e}")
                # If we can't checkout base branch, try creating from current branch
                logger.warning(f"Attempting to create branch from current branch instead")
            
            # Create and checkout new branch
            try:
                repo.git.checkout('-b', branch_name)
                logger.info(f"Successfully created and checked out branch '{branch_name}'")
                return True
            except git.exc.GitCommandError as e:
                error_msg = str(e)
                if "already exists" in error_msg.lower():
                    # Branch was created between checks, just checkout
                    logger.info(f"Branch '{branch_name}' now exists, checking out")
                    repo.git.checkout(branch_name)
                    return True
                else:
                    logger.error(f"Git command failed: {error_msg}")
                    raise
            
        except git.exc.GitCommandError as e:
            error_msg = str(e)
            logger.error(f"Git command error while creating branch '{branch_name}': {error_msg}")
            # Provide more specific error information
            if "pathspec" in error_msg.lower():
                logger.error(f"Branch name or path issue. Branch: '{branch_name}', Base: '{base_branch}'")
            elif "uncommitted changes" in error_msg.lower() or "would be overwritten" in error_msg.lower():
                logger.error("Repository has uncommitted changes. Stash or commit them first.")
            return False
        except Exception as e:
            logger.error(f"Failed to create branch '{branch_name}': {e}", exc_info=True)
            return False
    
    async def commit_changes(
        self,
        repo: git.Repo,
        file_paths: List[str],
        commit_message: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None
    ) -> bool:
        """Commit changes to repository.
        
        Args:
            repo: Git repository object
            file_paths: List of file paths to commit
            commit_message: Commit message
            author_name: Author name (optional)
            author_email: Author email (optional)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure git user is configured
            try:
                current_name = repo.git.config('user.name', get=True)
                current_email = repo.git.config('user.email', get=True)
                logger.debug(f"Git user: {current_name} <{current_email}>")
            except Exception:
                # Git user not configured, set defaults
                default_name = author_name or "Agentic Code Generator"
                default_email = author_email or "agentic@scrum-automation.local"
                repo.git.config('user.name', default_name, scope='local')
                repo.git.config('user.email', default_email, scope='local')
                logger.info(f"Configured git user: {default_name} <{default_email}>")
            
            # Add files to staging
            files_added = False
            for file_path in file_paths:
                full_path = os.path.join(repo.working_dir, file_path)
                if os.path.exists(full_path):
                    try:
                        # Check if file has changes compared to HEAD
                        try:
                            diff_output = repo.git.diff('HEAD', '--', file_path, exit_code=[0, 1])
                            if not diff_output.strip():
                                # File exists but no changes, check if it's in the commit
                                try:
                                    repo.git.show(f'HEAD:{file_path}', exit_code=[0, 1])
                                    logger.debug(f"File {file_path} unchanged, skipping")
                                    continue
                                except Exception:
                                    # File is new, needs to be added
                                    pass
                        except Exception:
                            pass
                        
                        repo.git.add(file_path)
                        logger.info(f"Added {file_path} to staging")
                        files_added = True
                    except Exception as e:
                        logger.warning(f"Failed to add {file_path}: {e}")
                else:
                    logger.warning(f"File {file_path} does not exist, skipping")
            
            # Also add any untracked files in the directories we're working with
            untracked = repo.untracked_files
            if untracked:
                for untracked_path in untracked:
                    # Check if this untracked file is in any of the directories we're committing
                    for file_path in file_paths:
                        dir_path = os.path.dirname(file_path) if os.path.dirname(file_path) else '.'
                        if untracked_path.startswith(dir_path) or file_path == untracked_path:
                            try:
                                repo.git.add(untracked_path)
                                logger.info(f"Added untracked file {untracked_path}")
                                files_added = True
                            except Exception as e:
                                logger.warning(f"Failed to add untracked file {untracked_path}: {e}")
                            break
            
            # Check if there are changes to commit after adding files
            try:
                # Check staged changes (files added to index)
                staged_changes = repo.index.diff("HEAD")
                # Check if index has any changes
                if not staged_changes and not files_added:
                    # Check if any of the files are actually different from HEAD
                    has_changes = False
                    for file_path in file_paths:
                        full_path = os.path.join(repo.working_dir, file_path)
                        if os.path.exists(full_path):
                            try:
                                # Check if file is tracked
                                tracked = repo.git.ls_files(file_path, exit_code=[0, 1])
                                if tracked.strip():
                                    # File is tracked, check if it differs from HEAD
                                    diff = repo.git.diff('HEAD', '--', file_path, exit_code=[0, 1])
                                    if diff.strip():
                                        has_changes = True
                                        break
                                    else:
                                        # File is unchanged, might already be committed
                                        logger.debug(f"File {file_path} is unchanged from HEAD")
                                else:
                                    # File is not tracked, needs to be added
                                    has_changes = True
                                    break
                            except Exception as e:
                                logger.debug(f"Error checking file {file_path}: {e}")
                                has_changes = True  # If we can't check, assume changes exist
                                break
                    
                    if not has_changes:
                        logger.info("No changes to commit (all files are already committed)")
                        return True
            except Exception as e:
                logger.debug(f"Error checking repo status: {e}")
                # Continue with commit attempt - better to try than to fail silently
            
            # Ensure git user is configured before committing
            try:
                repo.git.config('user.name', scope='local')
            except git.exc.GitCommandError:
                default_name = author_name or "Agentic Code Generator"
                repo.git.config('user.name', default_name, scope='local')
                logger.info(f"Configured git user.name: {default_name}")
            
            try:
                repo.git.config('user.email', scope='local')
            except git.exc.GitCommandError:
                default_email = author_email or "agentic@scrum-automation.local"
                repo.git.config('user.email', default_email, scope='local')
                logger.info(f"Configured git user.email: {default_email}")
            
            # Commit changes
            try:
                repo.git.commit('-m', commit_message)
                logger.info(f"Committed changes: {commit_message}")
                return True
            except git.exc.GitCommandError as e:
                error_msg = str(e)
                if "nothing to commit" in error_msg.lower() or "no changes added to commit" in error_msg.lower():
                    logger.info("No changes to commit (all files already committed)")
                    return True
                elif "author identity unknown" in error_msg.lower():
                    # Set author identity and retry
                    default_name = author_name or "Agentic Code Generator"
                    default_email = author_email or "agentic@scrum-automation.local"
                    repo.git.config('user.name', default_name, scope='local')
                    repo.git.config('user.email', default_email, scope='local')
                    repo.git.commit('-m', commit_message)
                    logger.info(f"Committed changes with configured user: {commit_message}")
                    return True
                else:
                    logger.error(f"Failed to commit changes: {error_msg}")
                    logger.error(f"Repository state: is_dirty={repo.is_dirty()}, files_added={files_added}")
                    return False
            
        except git.exc.GitCommandError as e:
            error_msg = str(e)
            if "nothing to commit" in error_msg.lower():
                logger.info("No changes to commit")
                return True
            logger.error(f"Git command error during commit: {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Failed to commit changes: {e}", exc_info=True)
            return False
    
    async def push_branch(
        self,
        repo: git.Repo,
        branch_name: str,
        force: bool = False
    ) -> bool:
        """Push branch to remote repository.
        
        Args:
            repo: Git repository object
            branch_name: Branch name to push
            force: Force push (default: False)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if remote exists
            if not repo.remotes.origin.exists():
                logger.error("Remote 'origin' does not exist")
                return False
            
            # Ensure we're on the correct branch
            try:
                current_branch = repo.active_branch.name
                if current_branch != branch_name:
                    logger.info(f"Switching from {current_branch} to {branch_name}")
                    repo.git.checkout(branch_name)
            except Exception as e:
                logger.warning(f"Could not determine current branch: {e}")
                try:
                    repo.git.checkout(branch_name)
                except Exception as e2:
                    logger.error(f"Failed to checkout branch {branch_name}: {e2}")
                    return False
            
            # Check if there are commits to push
            try:
                # Get commits ahead of remote
                ahead = repo.git.rev_list('--count', f'{branch_name}...origin/{branch_name}', '--left-right').strip()
                if ahead:
                    ahead_count = int(ahead.split()[0]) if ahead.split()[0].isdigit() else 0
                else:
                    ahead_count = 0
                
                # Check if branch exists on remote
                remote_branches = [ref.name.replace('origin/', '') for ref in repo.remotes.origin.refs]
                branch_exists_remote = branch_name in remote_branches
                
                if not branch_exists_remote:
                    logger.info(f"Branch {branch_name} does not exist on remote, will create it")
                elif ahead_count == 0:
                    logger.info(f"Branch {branch_name} is up to date with remote")
                    return True
                else:
                    logger.info(f"Branch {branch_name} is {ahead_count} commits ahead of remote")
            except Exception as e:
                logger.debug(f"Could not check branch status: {e}")
                # Continue to attempt push
            
            # Update remote URL to include token for authentication
            try:
                current_url = repo.remotes.origin.url
                if self.settings.github_token and '@' not in current_url:
                    # Update remote URL to include token
                    repo_owner = self.settings.github_repo_owner
                    repo_name = self.settings.github_repo_name
                    if repo_owner and repo_name:
                        new_url = f"https://{self.settings.github_token}@github.com/{repo_owner}/{repo_name}.git"
                        repo.remotes.origin.set_url(new_url)
                        logger.debug(f"Updated remote URL to include authentication")
            except Exception as e:
                logger.warning(f"Could not update remote URL: {e}")
            
            # Push to remote using refspec (local_branch:remote_branch)
            refspec = f"{branch_name}:{branch_name}"
            push_kwargs = {}
            if force:
                push_kwargs['force'] = True

            logger.info(f"Pushing branch {branch_name} to remote")
            try:
                push_info = repo.remotes.origin.push(refspec=refspec, **push_kwargs)

                # Check push result
                for info in push_info:
                    if hasattr(info, 'flags'):
                        if info.flags & info.ERROR:
                            logger.error(f"Push error: {info.summary}")
                            return False
                        elif info.flags & info.REJECTED:
                            logger.warning(f"Push rejected: {info.summary}")
                            if not force:
                                logger.info("Consider using force push if appropriate, or check branch permissions")
                            return False
                        elif info.flags & info.UP_TO_DATE:
                            logger.info("Branch is already up to date on remote")
                            return True
                        elif info.flags & info.NEW_HEAD:
                            logger.info(f"New branch pushed: {info.summary}")
                            return True
                        elif info.flags & info.FAST_FORWARD:
                            logger.info(f"Fast-forward push: {info.summary}")
                            return True

                logger.info(f"Branch {branch_name} pushed successfully")
                return True

            except git.exc.GitCommandError as e:
                error_msg = str(e)
                logger.error(f"Git push command failed: {error_msg}")

                # Provide specific error guidance
                if "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower() or "403" in error_msg:
                    logger.error("Authentication failed. Check GITHUB_TOKEN in .env file has 'repo' scope")
                    logger.error("Token should have permissions to push to the repository")
                elif "not found" in error_msg.lower() or "404" in error_msg:
                    logger.error("Repository or branch not found. Check GITHUB_REPO_OWNER and GITHUB_REPO_NAME")
                elif "protected branch" in error_msg.lower():
                    logger.error("Branch is protected. Cannot push directly. Consider creating a PR instead.")
                elif "permission denied" in error_msg.lower():
                    logger.error("Permission denied. Check repository access and token permissions")

                return False
            
        except Exception as e:
            logger.error(f"Failed to push branch {branch_name}: {e}", exc_info=True)
            return False
    
    async def create_pull_request(
        self,
        repo_owner: str,
        repo_name: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: Optional[str] = None,
        draft: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Create a pull request.
        
        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            title: PR title
            body: PR description
            head_branch: Head branch (feature branch)
            base_branch: Base branch (defaults to config base branch)
            draft: Create as draft PR (default: False)
        
        Returns:
            PR information dict or None if failed
        """
        try:
            if not self.github_client:
                logger.error("GitHub client not initialized")
                return None
            
            base_branch = base_branch or self.settings.github_base_branch
            
            repo = self.github_client.get_repo(f"{repo_owner}/{repo_name}")
            
            # Create pull request
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
                draft=draft
            )
            
            logger.info(f"Created pull request #{pr.number}: {title}")
            
            return {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body,
                "state": pr.state,
                "url": pr.html_url,
                "head_branch": pr.head.ref,
                "base_branch": pr.base.ref,
                "draft": pr.draft
            }
            
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return None
    
    async def get_branch_name_from_jira_key(
        self,
        jira_key: str,
        prefix: Optional[str] = None
    ) -> str:
        """Generate branch name from Jira ticket key.
        
        Args:
            jira_key: Jira ticket key (e.g., "SCRUM-123")
            prefix: Branch prefix (defaults to config prefix)
        
        Returns:
            Branch name (e.g., "feature/SCRUM-123")
        """
        prefix = prefix or self.settings.agentic_branch_prefix
        # Sanitize branch name (remove special characters, convert to lowercase)
        sanitized_key = jira_key.upper().replace(' ', '-')
        return f"{prefix}/{sanitized_key}"
    
    async def get_repository_status(
        self,
        repo: git.Repo
    ) -> Dict[str, Any]:
        """Get repository status.
        
        Args:
            repo: Git repository object
        
        Returns:
            Repository status information
        """
        try:
            return {
                "active_branch": repo.active_branch.name,
                "is_dirty": repo.is_dirty(),
                "untracked_files": repo.untracked_files,
                "modified_files": [item.a_path for item in repo.index.diff(None)],
                "staged_files": [item.a_path for item in repo.index.diff("HEAD")],
                "last_commit": repo.head.commit.hexsha,
                "last_commit_message": repo.head.commit.message
            }
        except Exception as e:
            logger.error(f"Failed to get repository status: {e}")
            return {}
    
    async def cleanup_temp_repository(self, repo_path: str) -> bool:
        """Clean up temporary repository.
        
        Args:
            repo_path: Path to repository
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if repo_path and os.path.exists(repo_path):
                # Only clean up if it's in temp directory
                if tempfile.gettempdir() in repo_path:
                    logger.info(f"Cleaning up temporary repository at {repo_path}")
                    shutil.rmtree(repo_path)
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to cleanup repository: {e}")
            return False

