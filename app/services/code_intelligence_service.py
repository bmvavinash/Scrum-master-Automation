"""Code Intelligence service for analyzing code and suggesting reviewers."""

import logging
import os
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import git
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class CodeIntelligenceService:
    """Service for code intelligence features."""
    
    def __init__(self):
        self.llm_service = LLMService()
        self._git_repos = {}  # Cache for git repositories
    
    async def analyze_code_changes(
        self, 
        repository_path: str, 
        commit_sha: str,
        file_paths: List[str] = None
    ) -> Dict[str, Any]:
        """Analyze code changes in a commit."""
        
        try:
            repo = self._get_git_repo(repository_path)
            commit = repo.commit(commit_sha)
            
            # Get file changes
            if file_paths:
                changes = [(path, commit.tree[path]) for path in file_paths if path in commit.tree]
            else:
                changes = list(commit.tree.traverse())
            
            # Analyze each changed file
            analysis_results = []
            total_lines_added = 0
            total_lines_removed = 0
            
            for file_path, tree_item in changes:
                if tree_item.type == 'blob':  # It's a file
                    file_analysis = await self._analyze_file(
                        repo, commit, str(file_path)
                    )
                    if file_analysis:
                        analysis_results.append(file_analysis)
                        total_lines_added += file_analysis.get('lines_added', 0)
                        total_lines_removed += file_analysis.get('lines_removed', 0)
            
            # Generate overall insights
            overall_analysis = await self._generate_overall_analysis(
                analysis_results, total_lines_added, total_lines_removed
            )
            
            return {
                'commit_sha': commit_sha,
                'commit_message': commit.message,
                'author': commit.author.name,
                'timestamp': commit.committed_datetime.isoformat(),
                'file_analyses': analysis_results,
                'overall_analysis': overall_analysis,
                'total_lines_added': total_lines_added,
                'total_lines_removed': total_lines_removed,
                'complexity_score': self._calculate_complexity_score(analysis_results)
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze code changes: {e}")
            return {}
    
    async def suggest_code_reviewer(
        self, 
        repository_path: str, 
        file_paths: List[str],
        team_members: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Suggest the best code reviewer for given files."""
        
        try:
            repo = self._get_git_repo(repository_path)
            
            # Get commit history for these files
            commit_history = []
            for file_path in file_paths:
                try:
                    commits = list(repo.iter_commits(paths=file_path, max_count=20))
                    for commit in commits:
                        commit_history.append({
                            'sha': commit.hexsha,
                            'author': commit.author.name,
                            'email': commit.author.email,
                            'message': commit.message,
                            'timestamp': commit.committed_datetime.isoformat(),
                            'files': [item.a_path for item in commit.diff(commit.parents[0]) if commit.parents]
                        })
                except Exception as e:
                    logger.warning(f"Failed to get history for {file_path}: {e}")
            
            # Use LLM to suggest reviewer
            suggestion = await self.llm_service.suggest_code_reviewer(
                file_paths, commit_history, team_members
            )
            
            # Add additional metrics
            suggestion['file_ownership'] = self._calculate_file_ownership(
                commit_history, team_members
            )
            suggestion['expertise_score'] = self._calculate_expertise_score(
                file_paths, commit_history, team_members
            )
            
            return suggestion
            
        except Exception as e:
            logger.error(f"Failed to suggest code reviewer: {e}")
            return {
                'primary_reviewer': team_members[0]['name'] if team_members else 'Unknown',
                'secondary_reviewer': team_members[1]['name'] if len(team_members) > 1 else None,
                'reasoning': 'Analysis failed',
                'expertise_areas': [],
                'file_ownership': {},
                'expertise_score': {}
            }
    
    async def detect_code_smells(
        self, 
        repository_path: str, 
        file_paths: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Detect code smells and quality issues."""
        
        try:
            repo = self._get_git_repo(repository_path)
            code_smells = []
            
            # Analyze files
            files_to_analyze = file_paths or self._get_all_code_files(repo)
            
            for file_path in files_to_analyze:
                try:
                    file_smells = await self._analyze_file_smells(repo, file_path)
                    if file_smells:
                        code_smells.extend(file_smells)
                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {e}")
            
            return code_smells
            
        except Exception as e:
            logger.error(f"Failed to detect code smells: {e}")
            return []
    
    async def generate_code_metrics(
        self, 
        repository_path: str, 
        file_paths: List[str] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive code metrics."""
        
        try:
            repo = self._get_git_repo(repository_path)
            
            # Get all commits
            commits = list(repo.iter_commits())
            
            # Calculate metrics
            metrics = {
                'total_commits': len(commits),
                'total_files': 0,
                'total_lines': 0,
                'languages': {},
                'file_complexity': {},
                'commit_frequency': self._calculate_commit_frequency(commits),
                'contributors': self._get_contributors(commits),
                'hotspots': self._find_hotspot_files(commits),
                'technical_debt_indicators': await self._assess_technical_debt(repo)
            }
            
            # Analyze files
            files_to_analyze = file_paths or self._get_all_code_files(repo)
            
            for file_path in files_to_analyze:
                try:
                    file_metrics = await self._analyze_file_metrics(repo, file_path)
                    if file_metrics:
                        metrics['total_files'] += 1
                        metrics['total_lines'] += file_metrics.get('lines', 0)
                        
                        # Language detection
                        language = file_metrics.get('language', 'unknown')
                        metrics['languages'][language] = metrics['languages'].get(language, 0) + 1
                        
                        # File complexity
                        metrics['file_complexity'][file_path] = file_metrics.get('complexity', 0)
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {e}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to generate code metrics: {e}")
            return {}
    
    def _get_git_repo(self, repository_path: str) -> git.Repo:
        """Get git repository object."""
        
        if repository_path not in self._git_repos:
            self._git_repos[repository_path] = git.Repo(repository_path)
        
        return self._git_repos[repository_path]
    
    async def _analyze_file(
        self, 
        repo: git.Repo, 
        commit: git.Commit, 
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """Analyze a specific file in a commit."""
        
        try:
            # Get file content
            file_content = commit.tree[file_path].data_stream.read().decode('utf-8')
            
            # Basic metrics
            lines = file_content.split('\n')
            total_lines = len(lines)
            non_empty_lines = len([line for line in lines if line.strip()])
            
            # Calculate complexity (simple cyclomatic complexity approximation)
            complexity = self._calculate_cyclomatic_complexity(file_content)
            
            # Detect language
            language = self._detect_language(file_path)
            
            # Get diff if possible
            lines_added = 0
            lines_removed = 0
            
            if commit.parents:
                try:
                    diff = commit.diff(commit.parents[0], paths=file_path)
                    for diff_item in diff:
                        if diff_item.a_path == file_path:
                            lines_added = len(diff_item.diff.decode('utf-8').split('\n'))
                            break
                except:
                    pass
            
            return {
                'file_path': file_path,
                'language': language,
                'total_lines': total_lines,
                'non_empty_lines': non_empty_lines,
                'complexity': complexity,
                'lines_added': lines_added,
                'lines_removed': lines_removed,
                'size_bytes': len(file_content.encode('utf-8'))
            }
            
        except Exception as e:
            logger.warning(f"Failed to analyze file {file_path}: {e}")
            return None
    
    def _calculate_cyclomatic_complexity(self, code: str) -> int:
        """Calculate cyclomatic complexity of code."""
        
        # Simple complexity calculation based on control flow statements
        complexity_keywords = [
            'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally',
            'with', 'and', 'or', 'case', 'when', 'switch', 'break', 'continue',
            'return', 'yield', 'async', 'await'
        ]
        
        complexity = 1  # Base complexity
        lines = code.split('\n')
        
        for line in lines:
            line_lower = line.lower().strip()
            for keyword in complexity_keywords:
                if keyword in line_lower:
                    complexity += 1
                    break
        
        return complexity
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        
        extension = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.sql': 'sql',
            '.sh': 'shell',
            '.bat': 'batch',
            '.ps1': 'powershell'
        }
        
        return language_map.get(extension, 'unknown')
    
    async def _generate_overall_analysis(
        self, 
        file_analyses: List[Dict[str, Any]], 
        total_added: int, 
        total_removed: int
    ) -> Dict[str, Any]:
        """Generate overall analysis of code changes."""
        
        if not file_analyses:
            return {}
        
        # Calculate aggregate metrics
        total_files = len(file_analyses)
        total_complexity = sum(analysis.get('complexity', 0) for analysis in file_analyses)
        avg_complexity = total_complexity / total_files if total_files > 0 else 0
        
        # Identify high-complexity files
        high_complexity_files = [
            analysis for analysis in file_analyses 
            if analysis.get('complexity', 0) > avg_complexity * 1.5
        ]
        
        # Language distribution
        languages = {}
        for analysis in file_analyses:
            lang = analysis.get('language', 'unknown')
            languages[lang] = languages.get(lang, 0) + 1
        
        return {
            'total_files_changed': total_files,
            'total_lines_added': total_added,
            'total_lines_removed': total_removed,
            'net_lines_changed': total_added - total_removed,
            'average_complexity': avg_complexity,
            'high_complexity_files': len(high_complexity_files),
            'language_distribution': languages,
            'risk_level': self._assess_risk_level(total_added, total_removed, avg_complexity)
        }
    
    def _assess_risk_level(
        self, 
        lines_added: int, 
        lines_removed: int, 
        avg_complexity: float
    ) -> str:
        """Assess risk level of changes."""
        
        total_changes = lines_added + lines_removed
        
        if total_changes > 1000 or avg_complexity > 20:
            return 'high'
        elif total_changes > 500 or avg_complexity > 10:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_complexity_score(self, file_analyses: List[Dict[str, Any]]) -> float:
        """Calculate overall complexity score."""
        
        if not file_analyses:
            return 0.0
        
        total_complexity = sum(analysis.get('complexity', 0) for analysis in file_analyses)
        total_lines = sum(analysis.get('total_lines', 0) for analysis in file_analyses)
        
        if total_lines == 0:
            return 0.0
        
        return total_complexity / total_lines
    
    def _calculate_file_ownership(
        self, 
        commit_history: List[Dict[str, Any]], 
        team_members: List[Dict[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate file ownership metrics."""
        
        ownership = {}
        
        for commit in commit_history:
            author = commit['author']
            files = commit.get('files', [])
            
            for file_path in files:
                if file_path not in ownership:
                    ownership[file_path] = {}
                
                if author not in ownership[file_path]:
                    ownership[file_path][author] = 0
                
                ownership[file_path][author] += 1
        
        # Calculate percentages
        for file_path, authors in ownership.items():
            total_commits = sum(authors.values())
            for author in authors:
                authors[author] = {
                    'commits': authors[author],
                    'percentage': (authors[author] / total_commits) * 100
                }
        
        return ownership
    
    def _calculate_expertise_score(
        self, 
        file_paths: List[str], 
        commit_history: List[Dict[str, Any]], 
        team_members: List[Dict[str, str]]
    ) -> Dict[str, float]:
        """Calculate expertise scores for team members."""
        
        expertise_scores = {}
        
        for member in team_members:
            member_name = member['name']
            score = 0.0
            
            # Count commits to these specific files
            file_commits = 0
            for commit in commit_history:
                if commit['author'] == member_name:
                    commit_files = commit.get('files', [])
                    for file_path in file_paths:
                        if file_path in commit_files:
                            file_commits += 1
            
            # Calculate score based on recent activity and file relevance
            recent_commits = [c for c in commit_history if c['author'] == member_name][-10:]
            recent_file_commits = sum(1 for c in recent_commits if any(f in file_paths for f in c.get('files', [])))
            
            score = (file_commits * 0.7) + (recent_file_commits * 0.3)
            expertise_scores[member_name] = score
        
        return expertise_scores
    
    def _get_all_code_files(self, repo: git.Repo) -> List[str]:
        """Get all code files in the repository."""
        
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.cs', 
            '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.scala', '.html', 
            '.css', '.scss', '.sass', '.sql', '.sh', '.bat', '.ps1'
        }
        
        code_files = []
        for item in repo.tree().traverse():
            if item.type == 'blob' and Path(item.path).suffix.lower() in code_extensions:
                code_files.append(item.path)
        
        return code_files
    
    def _calculate_commit_frequency(self, commits: List[git.Commit]) -> Dict[str, int]:
        """Calculate commit frequency by day of week."""
        
        frequency = {}
        for commit in commits:
            day = commit.committed_datetime.strftime('%A')
            frequency[day] = frequency.get(day, 0) + 1
        
        return frequency
    
    def _get_contributors(self, commits: List[git.Commit]) -> Dict[str, int]:
        """Get contributor statistics."""
        
        contributors = {}
        for commit in commits:
            author = commit.author.name
            contributors[author] = contributors.get(author, 0) + 1
        
        return contributors
    
    def _find_hotspot_files(self, commits: List[git.Commit]) -> List[Dict[str, Any]]:
        """Find frequently changed files (hotspots)."""
        
        file_changes = {}
        
        for commit in commits:
            if commit.parents:
                try:
                    for diff_item in commit.diff(commit.parents[0]):
                        file_path = diff_item.a_path
                        if file_path not in file_changes:
                            file_changes[file_path] = 0
                        file_changes[file_path] += 1
                except:
                    pass
        
        # Sort by change frequency
        hotspots = [
            {'file_path': path, 'change_count': count}
            for path, count in sorted(file_changes.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return hotspots[:10]  # Top 10 hotspots
    
    async def _assess_technical_debt(self, repo: git.Repo) -> Dict[str, Any]:
        """Assess technical debt indicators."""
        
        # This is a simplified assessment
        # In a real implementation, you'd use more sophisticated tools
        
        debt_indicators = {
            'large_files': 0,
            'complex_files': 0,
            'duplicate_code_suspected': 0,
            'test_coverage_low': 0
        }
        
        # Analyze files for debt indicators
        for item in repo.tree().traverse():
            if item.type == 'blob':
                try:
                    content = item.data_stream.read().decode('utf-8')
                    lines = content.split('\n')
                    
                    # Large files
                    if len(lines) > 1000:
                        debt_indicators['large_files'] += 1
                    
                    # Complex files (high cyclomatic complexity)
                    complexity = self._calculate_cyclomatic_complexity(content)
                    if complexity > 20:
                        debt_indicators['complex_files'] += 1
                    
                    # Test coverage (simplified check)
                    if not any('test' in item.path.lower() for test_indicator in ['test', 'spec', 'specs']):
                        debt_indicators['test_coverage_low'] += 1
                        
                except:
                    pass
        
        return debt_indicators
    
    async def _analyze_file_smells(self, repo: git.Repo, file_path: str) -> List[Dict[str, Any]]:
        """Analyze file for code smells."""
        
        try:
            content = repo.tree()[file_path].data_stream.read().decode('utf-8')
            smells = []
            
            lines = content.split('\n')
            
            # Long method detection
            if len(lines) > 100:
                smells.append({
                    'type': 'long_method',
                    'file_path': file_path,
                    'severity': 'medium',
                    'description': f'Method has {len(lines)} lines (consider breaking it down)'
                })
            
            # Duplicate code detection (simplified)
            line_counts = {}
            for line in lines:
                line = line.strip()
                if len(line) > 10:  # Ignore very short lines
                    line_counts[line] = line_counts.get(line, 0) + 1
            
            for line, count in line_counts.items():
                if count > 3:
                    smells.append({
                        'type': 'duplicate_code',
                        'file_path': file_path,
                        'severity': 'low',
                        'description': f'Line appears {count} times: {line[:50]}...'
                    })
            
            return smells
            
        except Exception as e:
            logger.warning(f"Failed to analyze smells in {file_path}: {e}")
            return []
    
    async def _analyze_file_metrics(self, repo: git.Repo, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze file for basic metrics."""
        
        try:
            content = repo.tree()[file_path].data_stream.read().decode('utf-8')
            lines = content.split('\n')
            
            return {
                'file_path': file_path,
                'lines': len(lines),
                'language': self._detect_language(file_path),
                'complexity': self._calculate_cyclomatic_complexity(content),
                'size_bytes': len(content.encode('utf-8'))
            }
            
        except Exception as e:
            logger.warning(f"Failed to analyze metrics for {file_path}: {e}")
            return None
