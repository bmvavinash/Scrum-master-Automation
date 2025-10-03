"""Meeting and standup related endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from datetime import datetime, date
from app.models.meeting import Meeting, MeetingType, MeetingStatus, ParticipantUpdate, MeetingSummary
from app.services.llm_service import LLMService
from app.services.jira_service import JiraService
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["meetings"])

# Initialize services
llm_service = LLMService()
jira_service = JiraService()


@router.post("/", response_model=Meeting)
async def create_meeting(
    meeting: Meeting,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new meeting."""
    
    try:
        meeting_dict = meeting.dict(by_alias=True, exclude={"id"})
        result = await db.meetings.insert_one(meeting_dict)
        meeting.id = str(result.inserted_id)
        
        logger.info(f"Created meeting: {meeting.id}")
        return meeting
        
    except Exception as e:
        logger.error(f"Failed to create meeting: {e}")
        raise HTTPException(status_code=500, detail="Failed to create meeting")


@router.get("/", response_model=List[Meeting])
async def get_meetings(
    meeting_type: Optional[MeetingType] = None,
    status: Optional[MeetingStatus] = None,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get meetings with optional filters."""
    
    try:
        filter_dict = {}
        if meeting_type:
            filter_dict["meeting_type"] = meeting_type.value
        if status:
            filter_dict["status"] = status.value
        
        cursor = db.meetings.find(filter_dict).limit(limit).sort("created_at", -1)
        meetings = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            meetings.append(Meeting(**doc))
        
        return meetings
        
    except Exception as e:
        logger.error(f"Failed to get meetings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get meetings")


@router.get("/{meeting_id}", response_model=Meeting)
async def get_meeting(
    meeting_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific meeting by ID."""
    
    try:
        from bson import ObjectId
        
        doc = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        doc["_id"] = str(doc["_id"])
        return Meeting(**doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get meeting {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get meeting")


@router.post("/{meeting_id}/updates", response_model=Meeting)
async def add_participant_update(
    meeting_id: str,
    update: ParticipantUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Add a participant update to a meeting."""
    
    try:
        from bson import ObjectId
        
        # Check if meeting exists
        meeting_doc = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        if not meeting_doc:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Add the update
        update_dict = update.dict()
        await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$push": {"participant_updates": update_dict}}
        )
        
        # Get updated meeting
        updated_doc = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        updated_doc["_id"] = str(updated_doc["_id"])
        
        return Meeting(**updated_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add participant update: {e}")
        raise HTTPException(status_code=500, detail="Failed to add participant update")


@router.post("/{meeting_id}/summarize", response_model=MeetingSummary)
async def generate_meeting_summary(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Generate AI summary for a meeting."""
    
    try:
        from bson import ObjectId
        
        # Get meeting
        meeting_doc = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        if not meeting_doc:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = Meeting(**meeting_doc)
        
        if not meeting.participant_updates:
            raise HTTPException(status_code=400, detail="No participant updates to summarize")
        
        # Convert updates to dict format for LLM
        updates_data = [update.dict() for update in meeting.participant_updates]
        
        # Generate summary using LLM
        summary = await llm_service.generate_meeting_summary(
            updates_data, 
            meeting.meeting_type.value
        )
        
        # Update meeting with summary
        await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {"summary": summary.dict()}}
        )
        
        # Create Jira tickets for action items in background
        if summary.action_items:
            background_tasks.add_task(
                create_jira_tickets_for_action_items,
                meeting_id,
                summary.action_items
            )
        
        logger.info(f"Generated summary for meeting {meeting_id}")
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate meeting summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate meeting summary")


@router.put("/{meeting_id}/status", response_model=Meeting)
async def update_meeting_status(
    meeting_id: str,
    status: MeetingStatus,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update meeting status."""
    
    try:
        from bson import ObjectId
        
        result = await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {"status": status.value, "updated_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Get updated meeting
        updated_doc = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        updated_doc["_id"] = str(updated_doc["_id"])
        
        return Meeting(**updated_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update meeting status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update meeting status")


@router.delete("/{meeting_id}")
async def delete_meeting(
    meeting_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a meeting."""
    
    try:
        from bson import ObjectId
        
        result = await db.meetings.delete_one({"_id": ObjectId(meeting_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        logger.info(f"Deleted meeting {meeting_id}")
        return {"message": "Meeting deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete meeting: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete meeting")


@router.get("/{meeting_id}/action-items", response_model=List[dict])
async def get_meeting_action_items(
    meeting_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get action items from a meeting."""
    
    try:
        from bson import ObjectId
        
        meeting_doc = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        if not meeting_doc:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = Meeting(**meeting_doc)
        
        if not meeting.summary or not meeting.summary.action_items:
            return []
        
        return [item.dict() for item in meeting.summary.action_items]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get action items: {e}")
        raise HTTPException(status_code=500, detail="Failed to get action items")


async def create_jira_tickets_for_action_items(
    meeting_id: str, 
    action_items: List[dict]
):
    """Background task to create Jira tickets for action items."""
    
    try:
        for item in action_items:
            ticket = await jira_service.create_ticket(
                title=item["title"],
                description=item.get("description", ""),
                assignee=item.get("assignee"),
                priority=item.get("priority", "medium")
            )
            
            if ticket:
                logger.info(f"Created Jira ticket {ticket.jira_key} for action item: {item['title']}")
            
    except Exception as e:
        logger.error(f"Failed to create Jira tickets for meeting {meeting_id}: {e}")
