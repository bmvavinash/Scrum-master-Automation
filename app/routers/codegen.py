"""Code generation endpoints based on Jira-like ticket descriptions."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.llm_service import LLMService
from app.services.jira_service import JiraService

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/codegen", tags=["codegen"])


class TicketDescriptionIn(BaseModel):
    ticket_key: str = Field(..., description="Ticket key like SCRUM-123 or a synthetic key")
    title: str = Field(..., description="Short title of the ticket")
    description: str = Field(..., description="Detailed, actionable description")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional generation context")


class TicketDescriptionOut(BaseModel):
    ticket_key: str
    title: str
    description: str
    context: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    _id: Optional[str] = None


llm_service = LLMService()
jira_service = JiraService()


@router.post("/description", response_model=TicketDescriptionOut)
async def write_ticket_description(
    payload: TicketDescriptionIn,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create or update a stored ticket description used for code generation."""
    try:
        now = datetime.utcnow()
        doc = {
            "ticket_key": payload.ticket_key,
            "title": payload.title,
            "description": payload.description,
            "context": payload.context or {},
            "updated_at": now,
        }

        existing = await db.codegen_descriptions.find_one({"ticket_key": payload.ticket_key})
        if existing:
            await db.codegen_descriptions.update_one(
                {"_id": existing["_id"]}, {"$set": doc}
            )
            created_at = existing.get("created_at", now)
            doc_out = {**doc, "created_at": created_at, "_id": str(existing["_id"]) }
        else:
            doc["created_at"] = now
            result = await db.codegen_descriptions.insert_one(doc)
            doc_out = {**doc, "_id": str(result.inserted_id)}

        return TicketDescriptionOut(**doc_out)  # type: ignore[arg-type]
    except Exception as e:
        logger.error(f"Failed to write ticket description: {e}")
        raise HTTPException(status_code=500, detail="Failed to write description")


@router.get("/description/{ticket_key}", response_model=TicketDescriptionOut)
async def read_ticket_description(
    ticket_key: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Read a stored ticket description by ticket key."""
    try:
        doc = await db.codegen_descriptions.find_one({"ticket_key": ticket_key})
        if not doc:
            raise HTTPException(status_code=404, detail="Description not found")
        doc["_id"] = str(doc["_id"])  # stringify for response model
        return TicketDescriptionOut(**doc)  # type: ignore[arg-type]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read ticket description: {e}")
        raise HTTPException(status_code=500, detail="Failed to read description")


class CodegenRequest(BaseModel):
    ticket_key: str = Field(..., description="Key of the stored ticket description")
    override_description: Optional[str] = Field(default=None, description="Use this instead of stored description")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Generation context or constraints")


@router.post("/generate")
async def generate_code_from_ticket(
    req: CodegenRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Generate code using the LLM based on a ticket's description."""
    try:
        description_text = req.override_description
        stored_context: Dict[str, Any] = {}
        title = ""

        if not description_text:
            doc = await db.codegen_descriptions.find_one({"ticket_key": req.ticket_key})
            if not doc:
                raise HTTPException(status_code=404, detail="Description not found")
            description_text = doc.get("description", "")
            stored_context = doc.get("context", {}) or {}
            title = doc.get("title", "")

        context = {**stored_context, **(req.context or {})}
        generation = await llm_service.generate_code_from_description(description_text or "", context)

        # Persist generation artifact for auditability
        out_doc = {
            "ticket_key": req.ticket_key,
            "title": title,
            "description": description_text,
            "context": context,
            "generation": generation,
            "generated_at": datetime.utcnow(),
        }
        result = await db.codegen_artifacts.insert_one(out_doc)
        out_doc["_id"] = str(result.inserted_id)
        return out_doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate code: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate code")


@router.post("/dummy")
async def create_dummy_ticket_description(
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Convenience endpoint: create a dummy Jira-like description for demo/testing."""
    try:
        payload = TicketDescriptionIn(
            ticket_key="SCRUM-DEMO-001",
            title="Add endpoint to manage user notes",
            description=(
                "Create two REST APIs in FastAPI: POST /api/v1/notes to create a note with fields "
                "{title: string[1..120], body: string[1..5000]} and GET /api/v1/notes/{id} to fetch a note by id. "
                "Persist in MongoDB collection 'notes'. Validate inputs, return 201 on create with resource id, "
                "and 404 for missing notes. Include Pydantic models and basic tests."
            ),
            context={"language": "python", "framework": "fastapi", "db": "mongodb"}
        )
        # Upsert via existing logic
        now = datetime.utcnow()
        doc = {
            "ticket_key": payload.ticket_key,
            "title": payload.title,
            "description": payload.description,
            "context": payload.context,
            "created_at": now,
            "updated_at": now,
        }
        await db.codegen_descriptions.update_one(
            {"ticket_key": payload.ticket_key},
            {"$set": doc},
            upsert=True,
        )
        found = await db.codegen_descriptions.find_one({"ticket_key": payload.ticket_key})
        found["_id"] = str(found["_id"])  # type: ignore[index]
        return found
    except Exception as e:
        logger.error(f"Failed to create dummy description: {e}")
        raise HTTPException(status_code=500, detail="Failed to create dummy description")


class JiraCodegenRequest(BaseModel):
    ticket_key: str = Field(..., description="Existing Jira ticket key, e.g., SCRUM-123")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional generation context")
    post_mode: str = Field(default="comment", description="How to store code back: comment|none")
    override_description: Optional[str] = Field(default=None, description="If provided, use this text instead of Jira description")
    update_jira_description: bool = Field(default=False, description="If true and override provided, update Jira description before generation")


def _build_adf_code_comment(title: str, generation: Dict[str, Any]) -> Dict[str, Any]:
    """Create an Atlassian Document Format payload containing code blocks for each file."""
    files = generation.get("code", []) or []
    notes = generation.get("notes", []) or []

    content = [
        {"type": "paragraph", "content": [{"type": "text", "text": f"Code snippet: {title}"}]}
    ]
    for file in files:
        path = file.get("path", "generated.txt")
        code = file.get("content", "")
        # Code block node
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": f"File: {path}"}]
        })
        content.append({
            "type": "codeBlock",
            "attrs": {"language": generation.get("language", "text")},
            "content": [{"type": "text", "text": code}]
        })
    if notes:
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": "Notes:"}]
        })
        for n in notes:
            content.append({
                "type": "bulletList",
                "content": [{
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(n)}]}]
                }]
            })

    return {"type": "doc", "version": 1, "content": content}


@router.post("/jira/generate")
async def generate_from_jira(
    req: JiraCodegenRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Fetch real Jira description, generate code, and optionally post back to Jira as a code snippet comment."""
    try:
        ticket = await jira_service.get_ticket(req.ticket_key)
        if not ticket:
            raise HTTPException(status_code=404, detail="Jira ticket not found or Jira not configured")

        description_text = (req.override_description or "").strip() or (ticket.description or "")
        if req.override_description and req.update_jira_description:
            try:
                await jira_service.update_ticket_description(req.ticket_key, req.override_description)
            except Exception:
                logger.warning("Failed to update Jira description prior to generation")
        context = req.context or {}
        generation = await llm_service.generate_code_from_description(description_text, context)

        # Persist generation artifact
        out_doc = {
            "ticket_key": req.ticket_key,
            "title": ticket.title,
            "description": description_text,
            "context": context,
            "generation": generation,
            "source": "jira",
            "generated_at": datetime.utcnow(),
        }
        result = await db.codegen_artifacts.insert_one(out_doc)
        out_doc["_id"] = str(result.inserted_id)

        # Optionally post to Jira as ADF comment
        posted = False
        if req.post_mode == "comment":
            adf = _build_adf_code_comment(ticket.title, generation)
            posted = await jira_service.add_comment_adf(req.ticket_key, adf)
            out_doc["jira_comment_posted"] = posted

        return out_doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed Jira-based code generation: {e}")
        raise HTTPException(status_code=500, detail="Failed Jira-based code generation")


