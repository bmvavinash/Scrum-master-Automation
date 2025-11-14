"""Service for applying generated code to filesystem."""

import logging
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CodeApplicationService:
    """Service for applying code changes to filesystem."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.backup_dir = os.path.join(repo_path, '.agentic_backups')
        self._ensure_backup_dir()
    
    def _ensure_backup_dir(self):
        """Ensure backup directory exists."""
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            # Add to .gitignore if not already there
            gitignore_path = os.path.join(self.repo_path, '.gitignore')
            if os.path.exists(gitignore_path):
                with open(gitignore_path, 'r') as f:
                    if '.agentic_backups' not in f.read():
                        with open(gitignore_path, 'a') as f:
                            f.write('\n.agentic_backups\n')
            else:
                with open(gitignore_path, 'w') as f:
                    f.write('.agentic_backups\n')
        except Exception as e:
            logger.warning(f"Failed to ensure backup directory: {e}")
    
    async def apply_code_files(
        self,
        code_files: List[Dict[str, Any]],
        backup_existing: bool = True
    ) -> Dict[str, Any]:
        """Apply generated code files to filesystem.
        
        Args:
            code_files: List of code file dicts with 'path' and 'content'
            backup_existing: Whether to backup existing files (default: True)
        
        Returns:
            Result dict with applied files, backups, and errors
        """
        result = {
            "applied_files": [],
            "backed_up_files": [],
            "errors": [],
            "created_dirs": []
        }
        
        # Create backup timestamp
        backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, backup_timestamp)
        
        try:
            os.makedirs(backup_path, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create backup directory: {e}")
            backup_existing = False
        
        for file_info in code_files:
            file_path = file_info.get('path')
            content = file_info.get('content', '')
            
            if not file_path:
                result["errors"].append({
                    "file": "unknown",
                    "error": "File path not provided"
                })
                continue
            
            try:
                # Resolve full path
                full_path = os.path.join(self.repo_path, file_path)
                
                # Create directory if it doesn't exist
                file_dir = os.path.dirname(full_path)
                if file_dir and not os.path.exists(file_dir):
                    os.makedirs(file_dir, exist_ok=True)
                    result["created_dirs"].append(file_dir)
                
                # Backup existing file if it exists
                if backup_existing and os.path.exists(full_path):
                    backup_file_path = os.path.join(backup_path, file_path.replace('/', '_'))
                    backup_file_dir = os.path.dirname(backup_file_path)
                    if backup_file_dir:
                        os.makedirs(backup_file_dir, exist_ok=True)
                    
                    shutil.copy2(full_path, backup_file_path)
                    result["backed_up_files"].append({
                        "original": file_path,
                        "backup": backup_file_path
                    })
                    logger.info(f"Backed up {file_path} to {backup_file_path}")
                
                # Write new file
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                result["applied_files"].append(file_path)
                logger.info(f"Applied code to {file_path}")
                
            except Exception as e:
                error_msg = f"Failed to apply code to {file_path}: {e}"
                logger.error(error_msg)
                result["errors"].append({
                    "file": file_path,
                    "error": str(e)
                })
        
        return result
    
    async def apply_code_changes(
        self,
        code_changes: Dict[str, Any],
        backup_existing: bool = True
    ) -> Dict[str, Any]:
        """Apply code changes (new and modified files).
        
        Args:
            code_changes: Dict with 'code' (list of files) and optionally 'tests'
            backup_existing: Whether to backup existing files
        
        Returns:
            Result dict with applied files and errors
        """
        code_files = code_changes.get('code', [])
        test_files = code_changes.get('tests', [])
        
        # Apply code files
        code_result = await self.apply_code_files(code_files, backup_existing)
        
        # Apply test files if provided
        test_result = await self.apply_code_files(test_files, backup_existing) if test_files else {
            "applied_files": [],
            "backed_up_files": [],
            "errors": [],
            "created_dirs": []
        }
        
        return {
            "code_files": code_result,
            "test_files": test_result,
            "total_applied": len(code_result["applied_files"]) + len(test_result["applied_files"]),
            "total_errors": len(code_result["errors"]) + len(test_result["errors"])
        }
    
    async def restore_from_backup(
        self,
        backup_timestamp: str
    ) -> bool:
        """Restore files from backup.
        
        Args:
            backup_timestamp: Timestamp of backup to restore
        
        Returns:
            True if successful, False otherwise
        """
        try:
            backup_path = os.path.join(self.backup_dir, backup_timestamp)
            if not os.path.exists(backup_path):
                logger.error(f"Backup {backup_timestamp} not found")
                return False
            
            # Restore all files from backup
            for root, dirs, files in os.walk(backup_path):
                for file in files:
                    backup_file_path = os.path.join(root, file)
                    # Reconstruct original path from backup filename
                    original_path = file.replace('_', '/')
                    full_path = os.path.join(self.repo_path, original_path)
                    
                    # Ensure directory exists
                    file_dir = os.path.dirname(full_path)
                    if file_dir:
                        os.makedirs(file_dir, exist_ok=True)
                    
                    # Restore file
                    shutil.copy2(backup_file_path, full_path)
                    logger.info(f"Restored {original_path} from backup")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore from backup {backup_timestamp}: {e}")
            return False
    
    async def check_file_conflicts(
        self,
        code_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check for file conflicts before applying changes.
        
        Args:
            code_files: List of code file dicts
        
        Returns:
            Conflict information dict
        """
        conflicts = {
            "existing_files": [],
            "missing_dirs": [],
            "permission_errors": []
        }
        
        for file_info in code_files:
            file_path = file_info.get('path')
            if not file_path:
                continue
            
            full_path = os.path.join(self.repo_path, file_path)
            
            # Check if file exists
            if os.path.exists(full_path):
                conflicts["existing_files"].append(file_path)
            
            # Check if directory exists and is writable
            file_dir = os.path.dirname(full_path)
            if file_dir and not os.path.exists(file_dir):
                conflicts["missing_dirs"].append(file_dir)
            elif file_dir and not os.access(file_dir, os.W_OK):
                conflicts["permission_errors"].append(file_dir)
        
        return conflicts
    
    async def get_file_content(
        self,
        file_path: str
    ) -> Optional[str]:
        """Get content of a file.
        
        Args:
            file_path: Relative path to file
        
        Returns:
            File content or None if not found
        """
        try:
            full_path = os.path.join(self.repo_path, file_path)
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None
    
    async def list_files_in_directory(
        self,
        directory: str,
        pattern: Optional[str] = None
    ) -> List[str]:
        """List files in a directory.
        
        Args:
            directory: Directory path (relative to repo)
            pattern: File pattern to match (e.g., "*.py")
        
        Returns:
            List of file paths
        """
        try:
            full_path = os.path.join(self.repo_path, directory)
            if not os.path.exists(full_path):
                return []
            
            files = []
            for root, dirs, filenames in os.walk(full_path):
                for filename in filenames:
                    if pattern:
                        if filename.endswith(pattern.replace('*', '')):
                            rel_path = os.path.relpath(os.path.join(root, filename), self.repo_path)
                            files.append(rel_path)
                    else:
                        rel_path = os.path.relpath(os.path.join(root, filename), self.repo_path)
                        files.append(rel_path)
            
            return files
        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {e}")
            return []



