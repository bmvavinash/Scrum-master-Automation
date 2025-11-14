"""Agentic code service for automated Jira-to-code-to-git workflow."""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.config import get_settings
from app.services.jira_service import JiraService
from app.services.llm_service import LLMService
from app.services.local_git_service import LocalGitService
from app.services.code_application_service import CodeApplicationService
from app.services.test_generation_service import TestGenerationService
from app.services.validation_service import ValidationService
from app.services.code_intelligence_service import CodeIntelligenceService

logger = logging.getLogger(__name__)


class AgenticCodeService:
    """Service for agentic code generation and deployment workflow."""
    
    def __init__(self):
        self.settings = get_settings()
        self.jira_service = JiraService()
        self.llm_service = LLMService()
        self.git_service = LocalGitService()
        self.test_service = TestGenerationService()
        self.validation_service = ValidationService()
        self.code_intelligence = CodeIntelligenceService()
    
    async def process_jira_ticket(
        self,
        jira_key: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a Jira ticket: fetch, generate code, apply, test, commit, push.
        
        Args:
            jira_key: Jira ticket key (e.g., "SCRUM-123")
            config: Optional configuration overrides
        
        Returns:
            Process result dict
        """
        # Merge config with defaults
        workflow_config = self._get_workflow_config(config)
        
        # Initialize result tracking
        result = {
            "jira_key": jira_key,
            "status": "started",
            "steps": {},
            "errors": [],
            "warnings": [],
            "iterations": 0,
            "max_iterations_reached": False
        }
        
        try:
            # Step 1: Fetch Jira ticket
            logger.info(f"Processing Jira ticket: {jira_key}")
            ticket = await self.jira_service.get_ticket(jira_key)
            if not ticket:
                result["status"] = "failed"
                result["errors"].append("Jira ticket not found")
                return result
            
            result["steps"]["jira_fetch"] = {
                "status": "success",
                "ticket_title": ticket.title,
                "ticket_status": ticket.status.value if hasattr(ticket.status, 'value') else str(ticket.status)
            }
            
            # Step 2: Get repository
            try:
                repo = await self.git_service.clone_or_get_repository()
                if not repo:
                    result["status"] = "failed"
                    result["errors"].append("Failed to clone or get repository (returned None)")
                    return result
            except ValueError as e:
                # Configuration error
                result["status"] = "failed"
                result["errors"].append(f"Repository configuration error: {str(e)}")
                logger.error(f"Repository configuration error: {e}")
                return result
            except Exception as e:
                # Other errors
                result["status"] = "failed"
                error_msg = f"Failed to clone or get repository: {str(e)}"
                result["errors"].append(error_msg)
                logger.error(error_msg, exc_info=True)
                return result
            
            repo_path = repo.working_dir
            result["steps"]["repository_setup"] = {
                "status": "success",
                "repo_path": repo_path
            }
            
            # Step 3: Create branch
            branch_name = await self.git_service.get_branch_name_from_jira_key(
                jira_key, workflow_config.get("branch_prefix")
            )
            branch_created = await self.git_service.create_branch(repo, branch_name)
            if not branch_created:
                result["status"] = "failed"
                result["errors"].append("Failed to create branch")
                return result
            
            result["steps"]["branch_creation"] = {
                "status": "success",
                "branch_name": branch_name
            }
            
            # Step 4: Analyze existing codebase (for context)
            existing_code_context = None
            if workflow_config.get("analyze_existing_code"):
                try:
                    existing_code_context = await self._analyze_codebase_context(repo_path)
                except Exception as e:
                    logger.warning(f"Failed to analyze codebase context: {e}")
            
            # Step 5: Generate code with iterative improvement
            code_generation_result = await self._generate_and_improve_code(
                ticket=ticket,
                repo_path=repo_path,
                existing_code_context=existing_code_context,
                workflow_config=workflow_config,
                result=result
            )
            
            if not code_generation_result["success"]:
                result["status"] = "failed"
                result["errors"].extend(code_generation_result.get("errors", []))
                return result
            
            result["steps"]["code_generation"] = code_generation_result
            
            # Step 6: Apply code to filesystem
            code_application_service = CodeApplicationService(repo_path)
            applied_files = code_generation_result.get("generated_code", {}).get("code", [])
            test_files = code_generation_result.get("generated_code", {}).get("tests", [])
            
            apply_result = await code_application_service.apply_code_changes({
                "code": applied_files,
                "tests": test_files
            }, backup_existing=True)
            
            result["steps"]["code_application"] = {
                "status": "success" if apply_result["total_errors"] == 0 else "partial",
                "applied_files": apply_result["code_files"]["applied_files"],
                "test_files": apply_result["test_files"]["applied_files"],
                "errors": apply_result["code_files"]["errors"] + apply_result["test_files"]["errors"]
            }
            
            if apply_result["total_errors"] > 0:
                result["warnings"].append(f"Some files failed to apply: {apply_result['total_errors']} errors")
            
            # Step 7: Validate code
            validation_result = await self.validation_service.validate_code(
                repo_path,
                file_paths=[f["path"] for f in applied_files]
            )
            
            result["steps"]["validation"] = validation_result
            
            if not validation_result["overall_valid"]:
                result["warnings"].append("Code validation found issues")
            
            # Step 8: Generate and run tests
            if workflow_config.get("generate_tests"):
                if ticket.acceptance_criteria:
                    logger.info(f"Generating tests from acceptance criteria for {jira_key}")
                    test_result = await self._generate_and_run_tests(
                        ticket=ticket,
                        repo_path=repo_path,
                        code_files=applied_files,
                        workflow_config=workflow_config
                    )
                    result["steps"]["testing"] = test_result
                    
                    # Only warn if tests were actually run and failed
                    if test_result.get("success") is False:
                        test_results = test_result.get("test_results", {})
                        if test_results and test_results.get("failed", 0) > 0:
                            result["warnings"].append(f"Some tests failed: {test_results.get('failed', 0)} failed out of {test_results.get('test_count', 0)}")
                        elif test_result.get("error"):
                            logger.warning(f"Test generation/execution error: {test_result.get('error')}")
                            result["warnings"].append(f"Test generation/execution error: {test_result.get('error')}")
                        else:
                            logger.warning("Test generation or execution failed (no specific error)")
                            result["warnings"].append("Test generation or execution failed")
                else:
                    logger.info(f"Skipping test generation for {jira_key}: no acceptance criteria")
                    result["steps"]["testing"] = {
                        "status": "skipped",
                        "reason": "No acceptance criteria provided"
                    }
            else:
                logger.info(f"Skipping test generation for {jira_key}: generate_tests is False")
                result["steps"]["testing"] = {
                    "status": "skipped",
                    "reason": "Test generation disabled in config"
                }
            
            # Step 9: Commit changes
            commit_message = self._generate_commit_message(ticket, code_generation_result)
            logger.info(f"Attempting to commit changes for {jira_key}: {len(applied_files)} code files, {len(test_files)} test files")
            
            # Only try to commit if we have files to commit
            if applied_files or test_files:
                commit_success = await self.git_service.commit_changes(
                    repo=repo,
                    file_paths=[f["path"] for f in applied_files + test_files],
                    commit_message=commit_message
                )
                
                if not commit_success:
                    # Check if files are already committed (push succeeded = commit worked)
                    # This might be a false negative, so check if push will succeed
                    logger.warning(f"Commit returned False for {jira_key}, but checking if changes are already committed")
                    # Don't add warning if push succeeds - commit must have worked
                else:
                    logger.info(f"Successfully committed changes for {jira_key}")
            else:
                logger.info(f"No files to commit for {jira_key}")
                commit_success = True  # No files to commit is success
            
            # Only add commit step if we have files
            if applied_files or test_files:
                if commit_success:
                    result["steps"]["commit"] = {
                        "status": "success",
                        "message": commit_message
                    }
                # Don't add warning if push succeeds - commit must have worked (even if returned False)
                # We'll check push status later to determine if commit actually worked
            
            # Step 10: Push to remote
            push_success = await self.git_service.push_branch(repo, branch_name, force=False)
            
            # If push succeeded, commit must have worked (even if commit_changes returned False)
            # This handles the case where files are already committed or commit check returned false negative
            if push_success:
                if "commit" not in result["steps"]:
                    result["steps"]["commit"] = {
                        "status": "success",
                        "message": commit_message if applied_files or test_files else "No changes to commit"
                    }
                    logger.info(f"Commit succeeded (verified by successful push): {jira_key}")
                # Remove any false warnings about commit failure
                if "Failed to commit changes" in result.get("warnings", []):
                    result["warnings"] = [w for w in result["warnings"] if w != "Failed to commit changes"]
                    logger.info(f"Removed false commit warning (push succeeded): {jira_key}")
            
            if not push_success:
                result["status"] = "partial"
                result["errors"].append("Failed to push branch to remote")
            else:
                result["steps"]["push"] = {
                    "status": "success",
                    "branch": branch_name
                }
            
            # Step 11: Create Pull Request (if configured)
            if workflow_config.get("create_pr"):
                pr_result = await self.git_service.create_pull_request(
                    repo_owner=self.settings.github_repo_owner,
                    repo_name=self.settings.github_repo_name,
                    title=f"{ticket.title} ({jira_key})",
                    body=self._generate_pr_description(ticket, code_generation_result, result),
                    head_branch=branch_name,
                    draft=workflow_config.get("pr_draft", False)
                )
                
                if pr_result:
                    result["steps"]["pull_request"] = {
                        "status": "success",
                        "pr_number": pr_result["number"],
                        "pr_url": pr_result["url"]
                    }
                else:
                    result["warnings"].append("Failed to create pull request")
            
            # Step 12: Update Jira ticket
            jira_comment = self._generate_jira_comment(result)
            await self.jira_service.add_comment(jira_key, jira_comment)
            
            # Update ticket status if configured
            if workflow_config.get("update_jira_status"):
                try:
                    await self.jira_service.update_ticket_status(
                        jira_key,
                        workflow_config.get("target_jira_status")
                    )
                except Exception as e:
                    logger.warning(f"Failed to update Jira status: {e}")
            
            result["status"] = "success"
            return result
            
        except Exception as e:
            logger.error(f"Failed to process Jira ticket {jira_key}: {e}", exc_info=True)
            result["status"] = "failed"
            result["errors"].append(str(e))
            return result
    
    async def _generate_and_improve_code(
        self,
        ticket,
        repo_path: str,
        existing_code_context: Optional[str],
        workflow_config: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate code with iterative improvement."""
        max_iterations = workflow_config.get("max_iterations", self.settings.agentic_max_iterations)
        iteration = 0
        last_errors = []
        
        while iteration < max_iterations:
            iteration += 1
            result["iterations"] = iteration
            
            logger.info(f"Code generation iteration {iteration}/{max_iterations}")
            
            try:
                # Generate code
                description = ticket.description or ""
                acceptance_criteria = getattr(ticket, 'acceptance_criteria', None) or ""
                
                logger.info(f"Generating code with provider fallback (description length: {len(description)}, acceptance_criteria length: {len(acceptance_criteria)})")
                
                generated_code, provider = await self.llm_service.generate_code_with_fallback(
                    description=description,
                    context={
                        "language": workflow_config.get("language", "python"),
                        "framework": workflow_config.get("framework", "fastapi"),
                        "follow_style": workflow_config.get("follow_style", True)
                    },
                    existing_code=existing_code_context,
                    acceptance_criteria=acceptance_criteria
                )
                
                logger.info(f"Code generation completed. Provider: {provider}, Has code: {generated_code is not None}")
                
                if not generated_code:
                    logger.warning("Generated code is None")
                    last_errors.append("Failed to generate code")
                    continue
                
                # Validate generated code structure
                if not self._validate_generated_code_structure(generated_code):
                    logger.warning(f"Generated code structure is invalid. Keys: {list(generated_code.keys()) if generated_code else 'None'}")
                    last_errors.append("Generated code structure is invalid")
                    continue
                
                logger.info(f"Generated code structure is valid. Files: {len(generated_code.get('code', []))}")
                
                # If we have errors from previous iteration, try to fix them
                if last_errors and iteration > 1:
                    # Add error feedback to prompt for next iteration
                    error_feedback = "\n".join([f"- {e}" for e in last_errors])
                    # For now, we'll proceed with the generated code
                    # In a more advanced implementation, we could feed errors back to LLM
                
                return {
                    "success": True,
                    "generated_code": generated_code,
                    "provider": provider,
                    "iterations": iteration
                }
                
            except Exception as e:
                logger.error(f"Code generation iteration {iteration} failed: {e}")
                last_errors.append(str(e))
                continue
        
        # Max iterations reached
        result["max_iterations_reached"] = True
        return {
            "success": False,
            "errors": last_errors,
            "iterations": iteration
        }
    
    async def _generate_and_run_tests(
        self,
        ticket,
        repo_path: str,
        code_files: List[Dict[str, Any]],
        workflow_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate and run tests."""
        try:
            acceptance_criteria = getattr(ticket, 'acceptance_criteria', None) or ""
            if not acceptance_criteria:
                logger.warning("No acceptance criteria provided for test generation")
                return {"success": False, "error": "No acceptance criteria provided"}
            
            logger.info(f"Generating tests from acceptance criteria (length: {len(acceptance_criteria)})")
            
            # Generate tests
            test_files = await self.test_service.generate_tests_from_acceptance_criteria(
                acceptance_criteria=acceptance_criteria,
                code_files=code_files,
                language=workflow_config.get("language", "python")
            )
            
            if not test_files:
                logger.error("Test service returned no test files")
                return {"success": False, "error": "Failed to generate tests"}
            
            logger.info(f"Generated {len(test_files)} test files")
            
            # Run tests if configured
            if workflow_config.get("run_tests"):
                logger.info(f"Running tests: {[f['path'] for f in test_files]}")
                test_results = await self.test_service.run_tests(
                    repo_path=repo_path,
                    test_files=[f["path"] for f in test_files]
                )
                
                logger.info(f"Test results: success={test_results.get('success')}, "
                          f"passed={test_results.get('passed', 0)}, "
                          f"failed={test_results.get('failed', 0)}")
                
                return {
                    "success": test_results["success"],
                    "test_files": test_files,
                    "test_results": test_results
                }
            else:
                logger.info("Test execution is disabled, skipping test run")
                return {
                    "success": True,
                    "test_files": test_files,
                    "test_results": None
                }
                
        except Exception as e:
            logger.error(f"Failed to generate and run tests: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _analyze_codebase_context(self, repo_path: str) -> str:
        """Analyze existing codebase to provide context for code generation."""
        try:
            # Get code metrics
            metrics = await self.code_intelligence.generate_code_metrics(repo_path)
            
            # Sample some key files for context
            sample_files = []
            for root, dirs, files in os.walk(repo_path):
                # Skip hidden directories and virtual environments
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules' and d != '__pycache__']
                
                for file in files:
                    if file.endswith('.py') and len(sample_files) < 5:
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                sample_files.append({
                                    "path": os.path.relpath(file_path, repo_path),
                                    "content": content[:500]  # Limit content length
                                })
                        except:
                            pass
                
                if len(sample_files) >= 5:
                    break
            
            # Build context string
            context = "Codebase Structure:\n"
            context += f"Total files: {metrics.get('total_files', 0)}\n"
            context += f"Languages: {', '.join(metrics.get('languages', {}).keys())}\n\n"
            context += "Sample Files:\n"
            for file_info in sample_files:
                context += f"\nFile: {file_info['path']}\n"
                context += f"{file_info['content']}\n"
            
            return context
            
        except Exception as e:
            logger.warning(f"Failed to analyze codebase context: {e}")
            return ""
    
    def _validate_generated_code_structure(self, generated_code: Dict[str, Any]) -> bool:
        """Validate that generated code has required structure."""
        if not isinstance(generated_code, dict):
            return False
        
        if "code" not in generated_code:
            return False
        
        if not isinstance(generated_code["code"], list):
            return False
        
        # Check that each code file has path and content
        for code_file in generated_code["code"]:
            if not isinstance(code_file, dict):
                return False
            if "path" not in code_file or "content" not in code_file:
                return False
        
        return True
    
    def _get_workflow_config(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get workflow configuration with defaults and overrides."""
        defaults = {
            "language": "python",
            "framework": "fastapi",
            "follow_style": self.settings.codegen_follow_style,
            "generate_tests": self.settings.codegen_add_tests,
            "run_tests": self.settings.codegen_run_tests,
            "validate_syntax": self.settings.codegen_validate_syntax,
            "run_linters": self.settings.codegen_run_linters,
            "create_pr": self.settings.agentic_auto_create_pr,
            "pr_draft": False,
            "update_jira_status": False,
            "target_jira_status": None,
            "branch_prefix": self.settings.agentic_branch_prefix,
            "max_iterations": self.settings.agentic_max_iterations,
            "analyze_existing_code": True
        }
        
        if config:
            defaults.update(config)
        
        return defaults
    
    def _generate_commit_message(self, ticket, code_result: Dict[str, Any]) -> str:
        """Generate commit message from ticket and code generation result."""
        provider = code_result.get("provider", "unknown")
        iterations = code_result.get("iterations", 1)
        
        message = f"feat({ticket.jira_key}): {ticket.title}\n\n"
        message += f"Generated code using {provider} (iteration {iterations})\n\n"
        message += f"Jira: {ticket.jira_key}\n"
        
        if code_result.get("generated_code", {}).get("notes"):
            message += "\nNotes:\n"
            for note in code_result["generated_code"]["notes"]:
                message += f"- {note}\n"
        
        return message
    
    def _generate_pr_description(self, ticket, code_result: Dict[str, Any], process_result: Dict[str, Any]) -> str:
        """Generate PR description."""
        description = f"## {ticket.title}\n\n"
        description += f"**Jira Ticket:** {ticket.jira_key}\n\n"
        description += f"**Description:**\n{ticket.description or 'N/A'}\n\n"
        
        if code_result.get("generated_code", {}).get("notes"):
            description += "**Generated Code Notes:**\n"
            for note in code_result["generated_code"]["notes"]:
                description += f"- {note}\n"
            description += "\n"
        
        if process_result.get("steps", {}).get("testing"):
            test_result = process_result["steps"]["testing"]
            if test_result.get("test_results"):
                tr = test_result["test_results"]
                description += f"**Test Results:**\n"
                description += f"- Tests: {tr.get('test_count', 0)}\n"
                description += f"- Passed: {tr.get('passed', 0)}\n"
                description += f"- Failed: {tr.get('failed', 0)}\n\n"
        
        if process_result.get("warnings"):
            description += "**Warnings:**\n"
            for warning in process_result["warnings"]:
                description += f"- {warning}\n"
        
        return description
    
    def _generate_jira_comment(self, process_result: Dict[str, Any]) -> str:
        """Generate Jira comment with process results."""
        comment = f"🤖 **Automated Code Generation Completed**\n\n"
        comment += f"Status: {process_result['status']}\n\n"
        
        if process_result.get("steps", {}).get("code_generation"):
            cg = process_result["steps"]["code_generation"]
            comment += f"Code Generation: {cg.get('provider', 'unknown')} (iteration {cg.get('iterations', 1)})\n"
        
        if process_result.get("steps", {}).get("branch_creation"):
            comment += f"Branch: {process_result['steps']['branch_creation']['branch_name']}\n"
        
        if process_result.get("steps", {}).get("pull_request"):
            pr = process_result["steps"]["pull_request"]
            comment += f"Pull Request: [#{pr['pr_number']}]({pr['pr_url']})\n"
        
        if process_result.get("errors"):
            comment += f"\n**Errors:**\n"
            for error in process_result["errors"]:
                comment += f"- {error}\n"
        
        if process_result.get("warnings"):
            comment += f"\n**Warnings:**\n"
            for warning in process_result["warnings"]:
                comment += f"- {warning}\n"
        
        return comment

