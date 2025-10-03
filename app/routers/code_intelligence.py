"""Code Intelligence endpoints for analyzing code and suggesting reviewers."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
from app.services.code_intelligence_service import CodeIntelligenceService
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/code-intelligence", tags=["code-intelligence"])

# Initialize service
code_intelligence_service = CodeIntelligenceService()


@router.post("/analyze-commit")
async def analyze_commit(
    repository_path: str,
    commit_sha: str,
    file_paths: Optional[List[str]] = None,
    background_tasks: BackgroundTasks = None
):
    """Analyze code changes in a specific commit."""
    
    try:
        analysis = await code_intelligence_service.analyze_code_changes(
            repository_path, commit_sha, file_paths
        )
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Commit not found or analysis failed")
        
        # Store analysis in database
        if background_tasks:
            background_tasks.add_task(store_analysis, analysis)
        
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze commit: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze commit")


@router.post("/suggest-reviewer")
async def suggest_code_reviewer(
    repository_path: str,
    file_paths: List[str],
    team_members: List[Dict[str, str]]
):
    """Suggest the best code reviewer for given files."""
    
    try:
        suggestion = await code_intelligence_service.suggest_code_reviewer(
            repository_path, file_paths, team_members
        )
        
        return suggestion
        
    except Exception as e:
        logger.error(f"Failed to suggest code reviewer: {e}")
        raise HTTPException(status_code=500, detail="Failed to suggest code reviewer")


@router.post("/detect-smells")
async def detect_code_smells(
    repository_path: str,
    file_paths: Optional[List[str]] = None,
    background_tasks: BackgroundTasks = None
):
    """Detect code smells and quality issues."""
    
    try:
        smells = await code_intelligence_service.detect_code_smells(
            repository_path, file_paths
        )
        
        # Store smells in database
        if background_tasks and smells:
            background_tasks.add_task(store_code_smells, smells, repository_path)
        
        return {
            "repository_path": repository_path,
            "smells_detected": len(smells),
            "smells": smells
        }
        
    except Exception as e:
        logger.error(f"Failed to detect code smells: {e}")
        raise HTTPException(status_code=500, detail="Failed to detect code smells")


@router.get("/metrics")
async def get_code_metrics(
    repository_path: str,
    file_paths: Optional[List[str]] = None
):
    """Get comprehensive code metrics for a repository."""
    
    try:
        metrics = await code_intelligence_service.generate_code_metrics(
            repository_path, file_paths
        )
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get code metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get code metrics")


@router.get("/analysis/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get stored analysis by ID."""
    
    try:
        from bson import ObjectId
        
        doc = await db.code_analyses.find_one({"_id": ObjectId(analysis_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        doc["_id"] = str(doc["_id"])
        return doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analysis")


@router.get("/analyses")
async def get_analyses(
    repository_path: Optional[str] = None,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get stored analyses with optional filters."""
    
    try:
        filter_dict = {}
        if repository_path:
            filter_dict["repository_path"] = repository_path
        
        cursor = db.code_analyses.find(filter_dict).limit(limit).sort("timestamp", -1)
        analyses = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            analyses.append(doc)
        
        return analyses
        
    except Exception as e:
        logger.error(f"Failed to get analyses: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analyses")


@router.get("/smells")
async def get_code_smells(
    repository_path: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get stored code smells with optional filters."""
    
    try:
        filter_dict = {}
        if repository_path:
            filter_dict["repository_path"] = repository_path
        if severity:
            filter_dict["severity"] = severity
        
        cursor = db.code_smells.find(filter_dict).limit(limit).sort("detected_at", -1)
        smells = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            smells.append(doc)
        
        return smells
        
    except Exception as e:
        logger.error(f"Failed to get code smells: {e}")
        raise HTTPException(status_code=500, detail="Failed to get code smells")


@router.get("/dashboard")
async def get_code_intelligence_dashboard(
    repository_path: Optional[str] = None,
    days: int = 30,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get comprehensive code intelligence dashboard."""
    
    try:
        from datetime import datetime, timedelta
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Get recent analyses
        analysis_filter = {"timestamp": {"$gte": since_date}}
        if repository_path:
            analysis_filter["repository_path"] = repository_path
        
        analysis_cursor = db.code_analyses.find(analysis_filter).sort("timestamp", -1)
        analyses = []
        
        async for doc in analysis_cursor:
            doc["_id"] = str(doc["_id"])
            analyses.append(doc)
        
        # Get code smells
        smell_filter = {"detected_at": {"$gte": since_date}}
        if repository_path:
            smell_filter["repository_path"] = repository_path
        
        smell_cursor = db.code_smells.find(smell_filter).sort("detected_at", -1)
        smells = []
        
        async for doc in smell_cursor:
            doc["_id"] = str(doc["_id"])
            smells.append(doc)
        
        # Calculate summary statistics
        total_analyses = len(analyses)
        total_smells = len(smells)
        
        # Group smells by severity
        severity_counts = {}
        for smell in smells:
            severity = smell.get("severity", "unknown")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Calculate average complexity
        avg_complexity = 0
        if analyses:
            total_complexity = sum(analysis.get("overall_analysis", {}).get("average_complexity", 0) for analysis in analyses)
            avg_complexity = total_complexity / len(analyses)
        
        # Get language distribution
        language_dist = {}
        for analysis in analyses:
            lang_dist = analysis.get("overall_analysis", {}).get("language_distribution", {})
            for lang, count in lang_dist.items():
                language_dist[lang] = language_dist.get(lang, 0) + count
        
        return {
            "summary": {
                "total_analyses": total_analyses,
                "total_smells": total_smells,
                "average_complexity": round(avg_complexity, 2),
                "severity_distribution": severity_counts,
                "language_distribution": language_dist
            },
            "recent_analyses": analyses[:10],
            "recent_smells": smells[:20],
            "trends": {
                "complexity_trend": calculate_complexity_trend(analyses),
                "smell_trend": calculate_smell_trend(smells)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get code intelligence dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard")


@router.post("/analyze-pull-request")
async def analyze_pull_request(
    repository_path: str,
    pr_number: int,
    team_members: List[Dict[str, str]],
    background_tasks: BackgroundTasks = None
):
    """Analyze a pull request and suggest reviewers."""
    
    try:
        # This would integrate with Git service to get PR details
        # For now, we'll simulate the analysis
        
        # Get PR files (this would come from Git service)
        file_paths = []  # Would be populated from actual PR data
        
        # Suggest reviewers
        reviewer_suggestion = await code_intelligence_service.suggest_code_reviewer(
            repository_path, file_paths, team_members
        )
        
        # Analyze code quality
        code_quality = await code_intelligence_service.analyze_code_quality(
            [], {}  # Would be populated with actual PR data
        )
        
        analysis_result = {
            "pr_number": pr_number,
            "repository_path": repository_path,
            "reviewer_suggestion": reviewer_suggestion,
            "code_quality": code_quality,
            "recommendations": generate_pr_recommendations(reviewer_suggestion, code_quality)
        }
        
        # Store analysis
        if background_tasks:
            background_tasks.add_task(store_pr_analysis, analysis_result)
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"Failed to analyze pull request: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze pull request")


async def store_analysis(analysis: Dict[str, Any]):
    """Background task to store analysis in database."""
    
    try:
        from app.database import get_database
        db = get_database()
        
        analysis["timestamp"] = datetime.utcnow()
        await db.code_analyses.insert_one(analysis)
        
        logger.info("Stored code analysis in database")
        
    except Exception as e:
        logger.error(f"Failed to store analysis: {e}")


async def store_code_smells(smells: List[Dict[str, Any]], repository_path: str):
    """Background task to store code smells in database."""
    
    try:
        from app.database import get_database
        from datetime import datetime
        db = get_database()
        
        for smell in smells:
            smell["repository_path"] = repository_path
            smell["detected_at"] = datetime.utcnow()
            await db.code_smells.insert_one(smell)
        
        logger.info(f"Stored {len(smells)} code smells in database")
        
    except Exception as e:
        logger.error(f"Failed to store code smells: {e}")


async def store_pr_analysis(analysis: Dict[str, Any]):
    """Background task to store PR analysis in database."""
    
    try:
        from app.database import get_database
        from datetime import datetime
        db = get_database()
        
        analysis["timestamp"] = datetime.utcnow()
        await db.pr_analyses.insert_one(analysis)
        
        logger.info("Stored PR analysis in database")
        
    except Exception as e:
        logger.error(f"Failed to store PR analysis: {e}")


def calculate_complexity_trend(analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculate complexity trend over time."""
    
    trend_data = []
    for analysis in analyses:
        complexity = analysis.get("overall_analysis", {}).get("average_complexity", 0)
        timestamp = analysis.get("timestamp", datetime.utcnow())
        
        trend_data.append({
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "complexity": complexity
        })
    
    # Sort by timestamp
    trend_data.sort(key=lambda x: x["timestamp"])
    return trend_data


def calculate_smell_trend(smells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Calculate code smell trend over time."""
    
    # Group by date
    daily_counts = {}
    for smell in smells:
        detected_at = smell.get("detected_at", datetime.utcnow())
        if isinstance(detected_at, str):
            detected_at = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
        
        date_key = detected_at.date().isoformat()
        daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
    
    # Convert to trend data
    trend_data = [
        {"date": date, "count": count}
        for date, count in sorted(daily_counts.items())
    ]
    
    return trend_data


def generate_pr_recommendations(
    reviewer_suggestion: Dict[str, Any], 
    code_quality: Dict[str, Any]
) -> List[str]:
    """Generate recommendations for a pull request."""
    
    recommendations = []
    
    # Reviewer recommendations
    if reviewer_suggestion.get("primary_reviewer"):
        recommendations.append(
            f"Consider {reviewer_suggestion['primary_reviewer']} as primary reviewer "
            f"({reviewer_suggestion.get('reasoning', 'based on expertise')})"
        )
    
    # Code quality recommendations
    quality_score = code_quality.get("quality_score", 0.5)
    if quality_score < 0.7:
        recommendations.append("Code quality score is below threshold - consider refactoring")
    
    issues = code_quality.get("issues", [])
    if issues:
        recommendations.append(f"Address the following issues: {', '.join(issues[:3])}")
    
    complexity_concerns = code_quality.get("complexity_concerns", [])
    if complexity_concerns:
        recommendations.append("Consider reducing complexity in identified areas")
    
    return recommendations
