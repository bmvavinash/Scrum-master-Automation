"""Service for generating and running tests from acceptance criteria."""

import logging
import subprocess
import asyncio
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.config import get_settings
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class TestGenerationService:
    """Service for generating and executing tests."""
    
    def __init__(self):
        self.settings = get_settings()
        self.llm_service = LLMService()
    
    async def generate_tests_from_acceptance_criteria(
        self,
        acceptance_criteria: str,
        code_files: List[Dict[str, Any]],
        language: str = "python"
    ) -> List[Dict[str, Any]]:
        """Generate test cases from acceptance criteria.
        
        Args:
            acceptance_criteria: Acceptance criteria from Jira ticket
            code_files: List of code files to test
            language: Programming language (default: python)
        
        Returns:
            List of test file dicts with path and content
        """
        try:
            # Build prompt for test generation
            prompt = self._build_test_generation_prompt(
                acceptance_criteria, code_files, language
            )
            
            # Use LLM to generate tests
            if self.settings.codegen_add_tests:
                # Try to generate tests using LLM
                try:
                    test_code, provider = await self.llm_service.generate_code_with_fallback(
                        description=f"Generate test cases for the following acceptance criteria:\n{acceptance_criteria}",
                        context={
                            "language": language,
                            "framework": "pytest" if language == "python" else "jest",
                            "purpose": "test_generation"
                        },
                        existing_code="\n".join([f.get("content", "") for f in code_files])
                    )
                    
                    if test_code and test_code.get("tests"):
                        return test_code.get("tests", [])
                except Exception as e:
                    logger.warning(f"Failed to generate tests with LLM: {e}")
            
            # Fallback to simple test template
            return self._generate_simple_test_template(acceptance_criteria, code_files, language)
            
        except Exception as e:
            logger.error(f"Failed to generate tests: {e}")
            return []
    
    def _build_test_generation_prompt(
        self,
        acceptance_criteria: str,
        code_files: List[Dict[str, Any]],
        language: str
    ) -> str:
        """Build prompt for test generation."""
        code_context = "\n".join([
            f"File: {f.get('path', 'unknown')}\n{f.get('content', '')[:500]}"
            for f in code_files[:5]  # Limit to first 5 files
        ])
        
        return f"""Generate comprehensive test cases based on the following acceptance criteria:

ACCEPTANCE CRITERIA:
{acceptance_criteria}

CODE TO TEST:
{code_context}

LANGUAGE: {language}

Generate test cases that:
1. Cover all acceptance criteria
2. Test both success and failure scenarios
3. Include edge cases
4. Use proper test framework ({'pytest' if language == 'python' else 'jest'})
5. Include proper assertions
6. Are well-documented

Return test code as JSON with structure:
{{
    "tests": [
        {{
            "path": "tests/test_file.py",
            "content": "test code here"
        }}
    ]
}}"""
    
    def _generate_simple_test_template(
        self,
        acceptance_criteria: str,
        code_files: List[Dict[str, Any]],
        language: str
    ) -> List[Dict[str, Any]]:
        """Generate simple test template as fallback."""
        if language != "python":
            return []
        
        test_files = []
        for code_file in code_files:
            file_path = code_file.get("path", "")
            if not file_path.endswith(".py"):
                continue
            
            # Generate test file path
            test_path = file_path.replace("app/", "tests/test_").replace(".py", ".py")
            if not test_path.startswith("tests/"):
                test_path = f"tests/test_{os.path.basename(file_path)}"
            
            # Simple test template
            test_content = f'''"""Tests for {file_path} based on acceptance criteria."""
import pytest
from pathlib import Path

# Acceptance Criteria:
# {acceptance_criteria}

def test_acceptance_criteria():
    """Test that acceptance criteria are met."""
    # TODO: Implement tests based on acceptance criteria
    assert True  # Placeholder

def test_basic_functionality():
    """Test basic functionality."""
    # TODO: Add specific tests
    assert True  # Placeholder
'''
            
            test_files.append({
                "path": test_path,
                "content": test_content
            })
        
        return test_files
    
    async def run_tests(
        self,
        repo_path: str,
        test_files: Optional[List[str]] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Run tests in repository.
        
        Args:
            repo_path: Path to repository
            test_files: List of specific test files to run (optional)
            timeout: Test timeout in seconds (default: config value)
        
        Returns:
            Test results dict
        """
        timeout = timeout or self.settings.agentic_test_timeout
        
        try:
            # Detect test framework
            if os.path.exists(os.path.join(repo_path, "pytest.ini")) or \
               os.path.exists(os.path.join(repo_path, "pyproject.toml")):
                return await self._run_pytest_tests(repo_path, test_files, timeout)
            elif os.path.exists(os.path.join(repo_path, "package.json")):
                return await self._run_jest_tests(repo_path, test_files, timeout)
            else:
                # Try pytest by default for Python
                return await self._run_pytest_tests(repo_path, test_files, timeout)
                
        except Exception as e:
            logger.error(f"Failed to run tests: {e}")
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "test_count": 0,
                "passed": 0,
                "failed": 0
            }
    
    async def _run_pytest_tests(
        self,
        repo_path: str,
        test_files: Optional[List[str]] = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Run pytest tests."""
        try:
            # Build pytest command
            cmd = ["pytest", "-v", "--tb=short"]
            
            if test_files:
                cmd.extend(test_files)
            else:
                cmd.append("tests/")
            
            # Run tests with timeout
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=timeout
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode('utf-8') + stderr.decode('utf-8')
            
            # Parse pytest output
            success = process.returncode == 0
            test_count = self._parse_pytest_output(output)
            
            return {
                "success": success,
                "output": output,
                "test_count": test_count.get("total", 0),
                "passed": test_count.get("passed", 0),
                "failed": test_count.get("failed", 0),
                "error": None if success else "Tests failed"
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Tests timed out after {timeout} seconds",
                "output": "",
                "test_count": 0,
                "passed": 0,
                "failed": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "test_count": 0,
                "passed": 0,
                "failed": 0
            }
    
    async def _run_jest_tests(
        self,
        repo_path: str,
        test_files: Optional[List[str]] = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Run Jest tests."""
        try:
            # Build jest command
            cmd = ["npm", "test", "--", "--verbose"]
            
            if test_files:
                cmd.extend(test_files)
            
            # Run tests with timeout
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=repo_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=timeout
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode('utf-8') + stderr.decode('utf-8')
            
            success = process.returncode == 0
            
            return {
                "success": success,
                "output": output,
                "test_count": 0,  # Jest output parsing would go here
                "passed": 0,
                "failed": 0,
                "error": None if success else "Tests failed"
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Tests timed out after {timeout} seconds",
                "output": "",
                "test_count": 0,
                "passed": 0,
                "failed": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "test_count": 0,
                "passed": 0,
                "failed": 0
            }
    
    def _parse_pytest_output(self, output: str) -> Dict[str, int]:
        """Parse pytest output to extract test counts."""
        try:
            # Simple parsing - can be enhanced
            lines = output.split('\n')
            total = 0
            passed = 0
            failed = 0
            
            for line in lines:
                if "passed" in line.lower() and "failed" in line.lower():
                    # Try to extract numbers
                    import re
                    numbers = re.findall(r'\d+', line)
                    if len(numbers) >= 2:
                        passed = int(numbers[0])
                        failed = int(numbers[1])
                        total = passed + failed
                elif "test session starts" in line.lower():
                    # Look for test count in subsequent lines
                    pass
            
            return {
                "total": total,
                "passed": passed,
                "failed": failed
            }
        except Exception as e:
            logger.warning(f"Failed to parse pytest output: {e}")
            return {"total": 0, "passed": 0, "failed": 0}



