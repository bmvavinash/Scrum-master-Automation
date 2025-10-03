"""Velocity and sprint metrics endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from app.models.velocity import Sprint, VelocityMetrics, TeamMemberMetrics, PredictionInsight, SprintStatus
from app.services.llm_service import LLMService
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/velocity", tags=["velocity"])

# Initialize service
llm_service = LLMService()


@router.post("/sprints", response_model=Sprint)
async def create_sprint(
    sprint: Sprint,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new sprint."""
    
    try:
        sprint_dict = sprint.dict(by_alias=True, exclude={"id"})
        result = await db.sprints.insert_one(sprint_dict)
        sprint.id = str(result.inserted_id)
        
        logger.info(f"Created sprint: {sprint.id}")
        return sprint
        
    except Exception as e:
        logger.error(f"Failed to create sprint: {e}")
        raise HTTPException(status_code=500, detail="Failed to create sprint")


@router.get("/sprints", response_model=List[Sprint])
async def get_sprints(
    status: Optional[SprintStatus] = None,
    team_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get sprints with optional filters."""
    
    try:
        filter_dict = {}
        if status:
            filter_dict["status"] = status.value
        if team_id:
            filter_dict["team_members"] = team_id
        
        cursor = db.sprints.find(filter_dict).limit(limit).sort("start_date", -1)
        sprints = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            sprints.append(Sprint(**doc))
        
        return sprints
        
    except Exception as e:
        logger.error(f"Failed to get sprints: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sprints")


@router.get("/sprints/{sprint_id}", response_model=Sprint)
async def get_sprint(
    sprint_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific sprint by ID."""
    
    try:
        from bson import ObjectId
        
        doc = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Sprint not found")
        
        doc["_id"] = str(doc["_id"])
        return Sprint(**doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sprint {sprint_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sprint")


@router.put("/sprints/{sprint_id}/status", response_model=Sprint)
async def update_sprint_status(
    sprint_id: str,
    status: SprintStatus,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update sprint status."""
    
    try:
        from bson import ObjectId
        
        result = await db.sprints.update_one(
            {"_id": ObjectId(sprint_id)},
            {"$set": {"status": status.value, "updated_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Sprint not found")
        
        # Get updated sprint
        updated_doc = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
        updated_doc["_id"] = str(updated_doc["_id"])
        
        return Sprint(**updated_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update sprint status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update sprint status")


@router.post("/sprints/{sprint_id}/calculate-velocity", response_model=VelocityMetrics)
async def calculate_velocity_metrics(
    sprint_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Calculate velocity metrics for a sprint."""
    
    try:
        from bson import ObjectId
        
        # Get sprint
        sprint_doc = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
        if not sprint_doc:
            raise HTTPException(status_code=404, detail="Sprint not found")
        
        sprint = Sprint(**sprint_doc)
        
        # Calculate metrics
        metrics = await calculate_sprint_metrics(sprint, db)
        
        # Store metrics
        metrics_dict = metrics.dict(by_alias=True, exclude={"id"})
        result = await db.velocity_metrics.insert_one(metrics_dict)
        metrics.id = str(result.inserted_id)
        
        # Generate AI insights in background
        background_tasks.add_task(generate_velocity_insights, sprint_id, metrics)
        
        logger.info(f"Calculated velocity metrics for sprint {sprint_id}")
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate velocity metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate velocity metrics")


@router.get("/sprints/{sprint_id}/metrics", response_model=VelocityMetrics)
async def get_sprint_metrics(
    sprint_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get velocity metrics for a sprint."""
    
    try:
        from bson import ObjectId
        
        doc = await db.velocity_metrics.find_one({"sprint_id": sprint_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Velocity metrics not found")
        
        doc["_id"] = str(doc["_id"])
        return VelocityMetrics(**doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sprint metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sprint metrics")


@router.get("/sprints/{sprint_id}/member-metrics", response_model=List[TeamMemberMetrics])
async def get_member_metrics(
    sprint_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get individual member metrics for a sprint."""
    
    try:
        cursor = db.team_member_metrics.find({"sprint_id": sprint_id})
        metrics = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            metrics.append(TeamMemberMetrics(**doc))
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get member metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get member metrics")


@router.get("/insights", response_model=List[PredictionInsight])
async def get_velocity_insights(
    team_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
    limit: int = 20,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get AI-generated velocity insights."""
    
    try:
        filter_dict = {}
        if team_id:
            filter_dict["team_id"] = team_id
        if sprint_id:
            filter_dict["sprint_id"] = sprint_id
        
        cursor = db.prediction_insights.find(filter_dict).limit(limit).sort("calculated_at", -1)
        insights = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            insights.append(PredictionInsight(**doc))
        
        return insights
        
    except Exception as e:
        logger.error(f"Failed to get velocity insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to get velocity insights")


@router.get("/dashboard")
async def get_velocity_dashboard(
    team_id: Optional[str] = None,
    days: int = 30,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get comprehensive velocity dashboard data."""
    
    try:
        # Get recent sprints
        since_date = datetime.utcnow() - timedelta(days=days)
        since_date_str = since_date.date().isoformat()
        
        sprint_filter = {"start_date": {"$gte": since_date_str}}
        if team_id:
            sprint_filter["team_members"] = team_id
        
        cursor = db.sprints.find(sprint_filter).sort("start_date", -1)
        sprints = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            sprints.append(Sprint(**doc))
        
        # Get velocity metrics for these sprints
        sprint_ids = [sprint.id for sprint in sprints]
        velocity_cursor = db.velocity_metrics.find({"sprint_id": {"$in": sprint_ids}})
        velocity_metrics = []
        
        async for doc in velocity_cursor:
            doc["_id"] = str(doc["_id"])
            velocity_metrics.append(VelocityMetrics(**doc))
        
        # Get recent insights
        insights_cursor = db.prediction_insights.find(
            {"team_id": team_id} if team_id else {}
        ).limit(10).sort("calculated_at", -1)
        insights = []
        
        async for doc in insights_cursor:
            doc["_id"] = str(doc["_id"])
            insights.append(PredictionInsight(**doc))
        
        # Calculate summary statistics
        total_sprints = len(sprints)
        avg_velocity = sum(m.velocity for m in velocity_metrics) / len(velocity_metrics) if velocity_metrics else 0
        total_story_points = sum(m.completed_story_points for m in velocity_metrics)
        avg_cycle_time = sum(m.average_cycle_time for m in velocity_metrics) / len(velocity_metrics) if velocity_metrics else 0
        
        return {
            "summary": {
                "total_sprints": total_sprints,
                "average_velocity": round(avg_velocity, 2),
                "total_story_points_completed": total_story_points,
                "average_cycle_time_days": round(avg_cycle_time, 2)
            },
            "sprints": [sprint.dict() for sprint in sprints],
            "velocity_metrics": [metrics.dict() for metrics in velocity_metrics],
            "insights": [insight.dict() for insight in insights]
        }
        
    except Exception as e:
        logger.error(f"Failed to get velocity dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get velocity dashboard")


async def calculate_sprint_metrics(sprint: Sprint, db: AsyncIOMotorDatabase) -> VelocityMetrics:
    """Calculate velocity metrics for a sprint."""
    
    try:
        # Get Jira tickets for this sprint
        jira_cursor = db.jira_tickets.find({
            "project_key": {"$exists": True},  # Assuming we have project mapping
            "created_at": {"$gte": sprint.start_date, "$lte": sprint.end_date}
        })
        
        planned_points = 0
        completed_points = 0
        blockers_count = 0
        bugs_count = 0
        
        async for ticket_doc in jira_cursor:
            story_points = ticket_doc.get("story_points", 0)
            status = ticket_doc.get("status", "")
            ticket_type = ticket_doc.get("ticket_type", "")
            
            planned_points += story_points
            
            if status.lower() in ["done", "completed"]:
                completed_points += story_points
            
            if "blocker" in ticket_doc.get("labels", []):
                blockers_count += 1
            
            if ticket_type.lower() == "bug":
                bugs_count += 1
        
        # Calculate velocity
        velocity = completed_points if sprint.status == SprintStatus.COMPLETED else 0
        
        # Calculate cycle time (simplified)
        cycle_time = 5.0  # Default, would be calculated from actual data
        
        # Calculate burndown data (simplified)
        burndown_data = []
        current_date = sprint.start_date
        remaining_points = planned_points
        
        while current_date <= sprint.end_date:
            # Simplified burndown calculation
            days_elapsed = (current_date - sprint.start_date).days
            total_days = (sprint.end_date - sprint.start_date).days
            
            if total_days > 0:
                expected_remaining = planned_points * (1 - (days_elapsed / total_days))
                burndown_data.append({
                    "date": current_date.isoformat(),
                    "remaining_points": max(0, expected_remaining),
                    "completed_points": planned_points - expected_remaining
                })
            
            current_date += timedelta(days=1)
        
        return VelocityMetrics(
            team_id="default_team",  # Would be passed as parameter
            sprint_id=sprint.id,
            sprint_name=sprint.name,
            planned_story_points=planned_points,
            completed_story_points=completed_points,
            velocity=velocity,
            average_cycle_time=cycle_time,
            average_lead_time=cycle_time + 2,  # Simplified
            burndown_data=burndown_data,
            blockers_count=blockers_count,
            bugs_count=bugs_count,
            technical_debt_hours=bugs_count * 4,  # Simplified
            team_satisfaction=None
        )
        
    except Exception as e:
        logger.error(f"Failed to calculate sprint metrics: {e}")
        # Return default metrics
        return VelocityMetrics(
            team_id="default_team",
            sprint_id=sprint.id,
            sprint_name=sprint.name,
            planned_story_points=0,
            completed_story_points=0,
            velocity=0,
            average_cycle_time=0,
            average_lead_time=0
        )


async def generate_velocity_insights(sprint_id: str, metrics: VelocityMetrics):
    """Background task to generate AI velocity insights."""
    
    try:
        # Get team member metrics
        from app.database import get_database
        db = get_database()
        
        member_cursor = db.team_member_metrics.find({"sprint_id": sprint_id})
        team_metrics = []
        
        async for doc in member_cursor:
            team_metrics.append(doc)
        
        # Generate insights using LLM
        insights = await llm_service.generate_velocity_insights(
            metrics.dict(), 
            team_metrics
        )
        
        # Store insights
        for insight in insights:
            insight_dict = insight.dict(by_alias=True, exclude={"id"})
            insight_dict["sprint_id"] = sprint_id
            insight_dict["team_id"] = metrics.team_id
            await db.prediction_insights.insert_one(insight_dict)
        
        logger.info(f"Generated {len(insights)} insights for sprint {sprint_id}")
        
    except Exception as e:
        logger.error(f"Failed to generate velocity insights: {e}")
