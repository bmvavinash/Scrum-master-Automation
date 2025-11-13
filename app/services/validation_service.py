"""Service for validating code quality, syntax, and running linters."""

import logging
import subprocess
import asyncio
import os
import ast
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import get_settings

logger = logging.getLogger(__name__)


class ValidationService:
    """Service for code validation and quality checks."""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def validate_code(
        self,
        repo_path: str,
        file_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Validate code with all enabled checks.
        
        Args:
            repo_path: Path to repository
            file_paths: List of specific files to validate (optional)
        
        Returns:
            Validation results dict
        """
        results = {
            "syntax_valid": True,
            "linter_passed": True,
            "syntax_errors": [],
            "linter_errors": [],
            "warnings": []
        }
        
        # Syntax validation
        if self.settings.codegen_validate_syntax:
            syntax_result = await self.validate_syntax(repo_path, file_paths)
            results["syntax_valid"] = syntax_result["valid"]
            results["syntax_errors"] = syntax_result.get("errors", [])
            results["warnings"].extend(syntax_result.get("warnings", []))
        
        # Linter checks
        if self.settings.codegen_run_linters:
            linter_result = await self.run_linters(repo_path, file_paths)
            results["linter_passed"] = linter_result["passed"]
            results["linter_errors"] = linter_result.get("errors", [])
            results["warnings"].extend(linter_result.get("warnings", []))
        
        results["overall_valid"] = results["syntax_valid"] and results["linter_passed"]
        
        return results
    
    async def validate_syntax(
        self,
        repo_path: str,
        file_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Validate Python syntax.
        
        Args:
            repo_path: Path to repository
            file_paths: List of specific files to validate (optional)
        
        Returns:
            Validation results dict
        """
        errors = []
        warnings = []
        
        try:
            if file_paths:
                files_to_check = [os.path.join(repo_path, f) for f in file_paths if f.endswith('.py')]
            else:
                # Find all Python files
                files_to_check = []
                for root, dirs, files in os.walk(repo_path):
                    # Skip hidden directories and virtual environments
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
                    for file in files:
                        if file.endswith('.py'):
                            files_to_check.append(os.path.join(root, file))
            
            for file_path in files_to_check:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Try to parse as AST
                    try:
                        ast.parse(content, filename=file_path)
                    except SyntaxError as e:
                        errors.append({
                            "file": os.path.relpath(file_path, repo_path),
                            "line": e.lineno,
                            "message": e.msg,
                            "text": e.text
                        })
                    except Exception as e:
                        warnings.append({
                            "file": os.path.relpath(file_path, repo_path),
                            "message": f"Unexpected error: {str(e)}"
                        })
                        
                except Exception as e:
                    warnings.append({
                        "file": os.path.relpath(file_path, repo_path),
                        "message": f"Failed to read file: {str(e)}"
                    })
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Failed to validate syntax: {e}")
            return {
                "valid": False,
                "errors": [{"message": str(e)}],
                "warnings": []
            }
    
    async def run_linters(
        self,
        repo_path: str,
        file_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run linters on code.
        
        Args:
            repo_path: Path to repository
            file_paths: List of specific files to lint (optional)
        
        Returns:
            Linter results dict
        """
        errors = []
        warnings = []
        
        # Try flake8 first (most common Python linter)
        flake8_result = await self._run_flake8(repo_path, file_paths)
        if flake8_result:
            errors.extend(flake8_result.get("errors", []))
            warnings.extend(flake8_result.get("warnings", []))
        
        # Try pylint if available
        pylint_result = await self._run_pylint(repo_path, file_paths)
        if pylint_result:
            errors.extend(pylint_result.get("errors", []))
            warnings.extend(pylint_result.get("warnings", []))
        
        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def _run_flake8(
        self,
        repo_path: str,
        file_paths: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Run flake8 linter."""
        try:
            # Check if flake8 is available
            process = await asyncio.create_subprocess_exec(
                "flake8", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            if process.returncode != 0:
                logger.warning("flake8 not available, skipping")
                return None
            
            # Build flake8 command
            cmd = ["flake8", "--max-line-length=120", "--exclude=.git,__pycache__,*.pyc"]
            
            if file_paths:
                cmd.extend([os.path.join(repo_path, f) for f in file_paths if f.endswith('.py')])
            else:
                cmd.append(repo_path)
            
            # Run flake8
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode('utf-8')
            
            # Parse flake8 output
            errors = []
            warnings = []
            
            for line in output.split('\n'):
                if not line.strip():
                    continue
                
                # Parse flake8 output format: file:line:col: code message
                parts = line.split(':', 3)
                if len(parts) >= 4:
                    file_path = parts[0]
                    line_num = parts[1]
                    col_num = parts[2]
                    message = parts[3].strip()
                    
                    # Classify as error or warning based on error code
                    error_code = message.split()[0] if message else ""
                    if error_code.startswith('E'):  # Error
                        errors.append({
                            "file": os.path.relpath(file_path, repo_path),
                            "line": int(line_num),
                            "column": int(col_num),
                            "message": message,
                            "code": error_code
                        })
                    else:  # Warning
                        warnings.append({
                            "file": os.path.relpath(file_path, repo_path),
                            "line": int(line_num),
                            "column": int(col_num),
                            "message": message,
                            "code": error_code
                        })
            
            return {
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.warning(f"Failed to run flake8: {e}")
            return None
    
    async def _run_pylint(
        self,
        repo_path: str,
        file_paths: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Run pylint linter."""
        try:
            # Check if pylint is available
            process = await asyncio.create_subprocess_exec(
                "pylint", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            if process.returncode != 0:
                logger.warning("pylint not available, skipping")
                return None
            
            # Build pylint command
            cmd = ["pylint", "--disable=all", "--enable=E,F"]
            
            if file_paths:
                cmd.extend([os.path.join(repo_path, f) for f in file_paths if f.endswith('.py')])
            else:
                # Find Python files
                python_files = []
                for root, dirs, files in os.walk(repo_path):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for file in files:
                        if file.endswith('.py'):
                            python_files.append(os.path.join(root, file))
                if python_files:
                    cmd.extend(python_files[:10])  # Limit to first 10 files
                else:
                    return None
            
            # Run pylint
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode('utf-8')
            
            # Parse pylint output
            errors = []
            warnings = []
            
            for line in output.split('\n'):
                if not line.strip() or line.startswith('*') or line.startswith('-'):
                    continue
                
                # Parse pylint output format: file:line:col: code: message
                parts = line.split(':', 3)
                if len(parts) >= 4:
                    file_path = parts[0]
                    line_num = parts[1]
                    col_num = parts[2]
                    rest = parts[3].strip()
                    
                    # Extract error code and message
                    code_message = rest.split(':', 1)
                    if len(code_message) >= 2:
                        error_code = code_message[0].strip()
                        message = code_message[1].strip()
                        
                        errors.append({
                            "file": os.path.relpath(file_path, repo_path),
                            "line": int(line_num),
                            "column": int(col_num),
                            "message": message,
                            "code": error_code
                        })
            
            return {
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.warning(f"Failed to run pylint: {e}")
            return None
    
    async def check_code_quality(
        self,
        repo_path: str,
        file_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Check overall code quality.
        
        Args:
            repo_path: Path to repository
            file_paths: List of specific files to check (optional)
        
        Returns:
            Quality metrics dict
        """
        metrics = {
            "complexity": 0,
            "maintainability_index": 0,
            "code_duplication": 0,
            "test_coverage": 0
        }
        
        # Basic quality checks can be added here
        # For now, return placeholder metrics
        
        return metrics


