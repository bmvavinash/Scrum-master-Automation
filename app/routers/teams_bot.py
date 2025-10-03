"""Microsoft Teams bot endpoints."""

from fastapi import APIRouter, Request, HTTPException, Depends
from botbuilder.core import TurnContext, BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity
from app.services.teams_service import ScrumBot
from app.config import get_settings
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["teams-bot"])

# Initialize bot and adapter
settings = get_settings()

bot_adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.teams_app_id,
    app_password=settings.teams_app_password
)

adapter = BotFrameworkAdapter(bot_adapter_settings)
bot = ScrumBot()


@router.post("/messages")
async def teams_messages(request: Request):
    """Handle incoming messages from Microsoft Teams."""
    
    try:
        # Get the request body
        body = await request.body()
        activity = Activity().deserialize(json.loads(body.decode("utf-8")))
        
        # Create auth header
        auth_header = request.headers.get("Authorization", "")
        
        # Process the activity
        response = await adapter.process_activity(activity, auth_header, bot.on_turn)
        
        if response:
            return response
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing Teams message: {e}")
        raise HTTPException(status_code=500, detail="Failed to process Teams message")


@router.get("/health")
async def teams_bot_health():
    """Health check for Teams bot."""
    
    return {
        "status": "healthy",
        "bot_id": settings.teams_app_id,
        "features": {
            "jira_integration": bool(settings.jira_url and settings.jira_email and settings.jira_api_token),
            "llm_service": bool(settings.aws_access_key_id and settings.aws_secret_access_key)
        }
    }
