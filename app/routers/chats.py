"""Chat and Teams bot endpoints."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
from app.models.chat import ChatMessage, MessageType, CommandType, BotResponse, TeamsAdaptiveCard
from app.services.llm_service import LLMService
from app.services.jira_service import JiraService
from app.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])

# Initialize services
llm_service = LLMService()
jira_service = JiraService()


@router.post("/messages", response_model=ChatMessage)
async def create_message(
    message: ChatMessage,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new chat message."""
    
    try:
        message_dict = message.dict(by_alias=True, exclude={"id"})
        result = await db.chat_messages.insert_one(message_dict)
        message.id = str(result.inserted_id)
        
        logger.info(f"Created chat message: {message.id}")
        return message
        
    except Exception as e:
        logger.error(f"Failed to create chat message: {e}")
        raise HTTPException(status_code=500, detail="Failed to create chat message")


@router.get("/messages", response_model=List[ChatMessage])
async def get_messages(
    channel_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get chat messages with optional filters."""
    
    try:
        filter_dict = {}
        if channel_id:
            filter_dict["channel_id"] = channel_id
        if thread_id:
            filter_dict["thread_id"] = thread_id
        
        cursor = db.chat_messages.find(filter_dict).limit(limit).sort("created_at", -1)
        messages = []
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            messages.append(ChatMessage(**doc))
        
        return messages
        
    except Exception as e:
        logger.error(f"Failed to get chat messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat messages")


@router.post("/bot/process", response_model=BotResponse)
async def process_bot_message(
    message: str,
    sender_id: str,
    sender_name: str,
    channel_id: str,
    thread_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Process a message from Teams bot and generate response."""
    
    try:
        # Store the incoming message
        incoming_message = ChatMessage(
            message_type=MessageType.TEXT,
            content=message,
            sender_id=sender_id,
            sender_name=sender_name,
            channel_id=channel_id,
            thread_id=thread_id
        )
        
        message_dict = incoming_message.dict(by_alias=True, exclude={"id"})
        await db.chat_messages.insert_one(message_dict)
        
        # Process the message and generate response
        response = await process_message(message, sender_id, sender_name, channel_id)
        
        # Store the bot response
        bot_message = ChatMessage(
            message_type=MessageType.TEXT,
            content=response.message,
            sender_id="bot",
            sender_name="Scrum Bot",
            channel_id=channel_id,
            thread_id=thread_id
        )
        
        if background_tasks:
            background_tasks.add_task(store_bot_message, bot_message)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to process bot message: {e}")
        raise HTTPException(status_code=500, detail="Failed to process bot message")


@router.post("/bot/commands/{command_type}")
async def execute_bot_command(
    command_type: CommandType,
    args: Dict[str, Any],
    sender_id: str,
    sender_name: str,
    channel_id: str,
    background_tasks: BackgroundTasks = None
):
    """Execute a specific bot command."""
    
    try:
        response = await execute_command(command_type, args, sender_id, sender_name, channel_id)
        
        # Store command execution
        if background_tasks:
            background_tasks.add_task(store_command_execution, command_type, args, sender_id, channel_id)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to execute command {command_type}: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute command")


@router.get("/bot/help")
async def get_bot_help():
    """Get help information for bot commands."""
    
    help_text = """
🤖 **Scrum Automation Bot Commands**

**Meeting Commands:**
- `/schedule-standup` - Schedule a standup meeting
- `/get-status` - Get current sprint status
- `/get-velocity` - Get team velocity metrics

**Task Commands:**
- `/create-task <title>` - Create a new Jira task
- `/create-blocker <description>` - Create a blocker ticket
- `/get-tasks` - List current tasks

**Code Intelligence:**
- `/suggest-reviewer <file1,file2>` - Suggest code reviewer
- `/analyze-code <commit_sha>` - Analyze code changes
- `/get-metrics` - Get code quality metrics

**General:**
- `/help` - Show this help message
- `/insights` - Get AI-generated insights

**Examples:**
- `/create-task Fix login bug`
- `/create-blocker Database connection timeout`
- `/suggest-reviewer src/auth.py,src/user.py`
- `/get-velocity`
    """
    
    return {"help_text": help_text}


async def process_message(
    message: str, 
    sender_id: str, 
    sender_name: str, 
    channel_id: str
) -> BotResponse:
    """Process a message and generate appropriate response."""
    
    # Check if it's a command
    if message.startswith('/'):
        return await process_command(message, sender_id, sender_name, channel_id)
    
    # Check for keywords and generate contextual response
    message_lower = message.lower()
    
    if any(keyword in message_lower for keyword in ['standup', 'meeting', 'update']):
        return await handle_standup_related_message(message, sender_id, sender_name, channel_id)
    
    elif any(keyword in message_lower for keyword in ['task', 'ticket', 'jira']):
        return await handle_task_related_message(message, sender_id, sender_name, channel_id)
    
    elif any(keyword in message_lower for keyword in ['review', 'code', 'pr']):
        return await handle_code_related_message(message, sender_id, sender_name, channel_id)
    
    elif any(keyword in message_lower for keyword in ['velocity', 'sprint', 'metrics']):
        return await handle_velocity_related_message(message, sender_id, sender_name, channel_id)
    
    else:
        return BotResponse(
            message="I'm here to help with scrum automation! Try `/help` to see available commands.",
            should_notify=False
        )


async def process_command(
    message: str, 
    sender_id: str, 
    sender_name: str, 
    channel_id: str
) -> BotResponse:
    """Process a bot command."""
    
    parts = message.split(' ', 1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    if command == '/help':
        return BotResponse(message=get_help_message())
    
    elif command == '/create-task':
        return await handle_create_task_command(args, sender_id, sender_name, channel_id)
    
    elif command == '/create-blocker':
        return await handle_create_blocker_command(args, sender_id, sender_name, channel_id)
    
    elif command == '/schedule-standup':
        return await handle_schedule_standup_command(args, sender_id, sender_name, channel_id)
    
    elif command == '/get-status':
        return await handle_get_status_command(sender_id, sender_name, channel_id)
    
    elif command == '/get-velocity':
        return await handle_get_velocity_command(sender_id, sender_name, channel_id)
    
    elif command == '/suggest-reviewer':
        return await handle_suggest_reviewer_command(args, sender_id, sender_name, channel_id)
    
    elif command == '/analyze-code':
        return await handle_analyze_code_command(args, sender_id, sender_name, channel_id)
    
    elif command == '/get-metrics':
        return await handle_get_metrics_command(sender_id, sender_name, channel_id)
    
    elif command == '/insights':
        return await handle_get_insights_command(sender_id, sender_name, channel_id)
    
    else:
        return BotResponse(
            message=f"Unknown command: {command}. Type `/help` for available commands.",
            should_notify=False
        )


async def handle_create_task_command(args: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle create task command."""
    
    if not args:
        return BotResponse(
            message="Please provide a task title. Usage: `/create-task <title>`",
            should_notify=False
        )
    
    try:
        # Create Jira ticket
        ticket = await jira_service.create_ticket(
            title=args,
            description=f"Created by {sender_name} via Teams bot",
            assignee=sender_id
        )
        
        if ticket:
            return BotResponse(
                message=f"✅ Created task: {ticket.jira_key} - {ticket.title}",
                should_notify=True,
                notification_type="task_created"
            )
        else:
            return BotResponse(
                message="❌ Failed to create task. Please check Jira configuration.",
                should_notify=True,
                notification_type="error"
            )
    
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        return BotResponse(
            message="❌ Failed to create task. Please try again later.",
            should_notify=True,
            notification_type="error"
        )


async def handle_create_blocker_command(args: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle create blocker command."""
    
    if not args:
        return BotResponse(
            message="Please provide a blocker description. Usage: `/create-blocker <description>`",
            should_notify=False
        )
    
    try:
        # Create Jira ticket with blocker label
        ticket = await jira_service.create_ticket(
            title=f"BLOCKER: {args}",
            description=f"Blocking issue reported by {sender_name} via Teams bot",
            assignee=sender_id,
            labels=["blocker", "urgent"]
        )
        
        if ticket:
            return BotResponse(
                message=f"🚨 Created blocker: {ticket.jira_key} - {ticket.title}",
                should_notify=True,
                notification_type="blocker_created"
            )
        else:
            return BotResponse(
                message="❌ Failed to create blocker. Please check Jira configuration.",
                should_notify=True,
                notification_type="error"
            )
    
    except Exception as e:
        logger.error(f"Failed to create blocker: {e}")
        return BotResponse(
            message="❌ Failed to create blocker. Please try again later.",
            should_notify=True,
            notification_type="error"
        )


async def handle_schedule_standup_command(args: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle schedule standup command."""
    
    # This would integrate with meeting scheduling
    return BotResponse(
        message="📅 Standup scheduling feature coming soon! For now, you can manually schedule meetings.",
        should_notify=False
    )


async def handle_get_status_command(sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle get status command."""
    
    # This would get current sprint status
    return BotResponse(
        message="📊 Sprint status feature coming soon! Check your Jira board for current status.",
        should_notify=False
    )


async def handle_get_velocity_command(sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle get velocity command."""
    
    # This would get velocity metrics
    return BotResponse(
        message="📈 Velocity metrics feature coming soon! Check the dashboard for detailed metrics.",
        should_notify=False
    )


async def handle_suggest_reviewer_command(args: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle suggest reviewer command."""
    
    if not args:
        return BotResponse(
            message="Please provide file paths. Usage: `/suggest-reviewer <file1,file2>`",
            should_notify=False
        )
    
    file_paths = [path.strip() for path in args.split(',')]
    
    # This would integrate with code intelligence service
    return BotResponse(
        message=f"🔍 Code reviewer suggestion for files: {', '.join(file_paths)} - Feature coming soon!",
        should_notify=False
    )


async def handle_analyze_code_command(args: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle analyze code command."""
    
    if not args:
        return BotResponse(
            message="Please provide a commit SHA. Usage: `/analyze-code <commit_sha>`",
            should_notify=False
        )
    
    # This would integrate with code intelligence service
    return BotResponse(
        message=f"🔬 Code analysis for commit {args} - Feature coming soon!",
        should_notify=False
    )


async def handle_get_metrics_command(sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle get metrics command."""
    
    return BotResponse(
        message="📊 Code quality metrics - Check the dashboard for detailed metrics!",
        should_notify=False
    )


async def handle_get_insights_command(sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle get insights command."""
    
    return BotResponse(
        message="🧠 AI insights - Check the dashboard for AI-generated insights and predictions!",
        should_notify=False
    )


async def handle_standup_related_message(message: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle standup-related messages."""
    
    return BotResponse(
        message="I can help with standup meetings! Try `/schedule-standup` or `/get-status` for more options.",
        should_notify=False
    )


async def handle_task_related_message(message: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle task-related messages."""
    
    return BotResponse(
        message="I can help with tasks! Try `/create-task <title>` or `/create-blocker <description>` to create tickets.",
        should_notify=False
    )


async def handle_code_related_message(message: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle code-related messages."""
    
    return BotResponse(
        message="I can help with code reviews! Try `/suggest-reviewer <files>` or `/analyze-code <commit>` for code intelligence features.",
        should_notify=False
    )


async def handle_velocity_related_message(message: str, sender_id: str, sender_name: str, channel_id: str) -> BotResponse:
    """Handle velocity-related messages."""
    
    return BotResponse(
        message="I can help with velocity metrics! Try `/get-velocity` or check the dashboard for detailed analytics.",
        should_notify=False
    )


def get_help_message() -> str:
    """Get help message for bot commands."""
    
    return """
🤖 **Scrum Automation Bot Commands**

**Meeting Commands:**
- `/schedule-standup` - Schedule a standup meeting
- `/get-status` - Get current sprint status
- `/get-velocity` - Get team velocity metrics

**Task Commands:**
- `/create-task <title>` - Create a new Jira task
- `/create-blocker <description>` - Create a blocker ticket
- `/get-tasks` - List current tasks

**Code Intelligence:**
- `/suggest-reviewer <file1,file2>` - Suggest code reviewer
- `/analyze-code <commit_sha>` - Analyze code changes
- `/get-metrics` - Get code quality metrics

**General:**
- `/help` - Show this help message
- `/insights` - Get AI-generated insights

**Examples:**
- `/create-task Fix login bug`
- `/create-blocker Database connection timeout`
- `/suggest-reviewer src/auth.py,src/user.py`
- `/get-velocity`
    """


async def execute_command(
    command_type: CommandType, 
    args: Dict[str, Any], 
    sender_id: str, 
    sender_name: str, 
    channel_id: str
) -> BotResponse:
    """Execute a specific command."""
    
    if command_type == CommandType.CREATE_TASK:
        title = args.get("title", "")
        return await handle_create_task_command(title, sender_id, sender_name, channel_id)
    
    elif command_type == CommandType.CREATE_BLOCKER:
        description = args.get("description", "")
        return await handle_create_blocker_command(description, sender_id, sender_name, channel_id)
    
    else:
        return BotResponse(
            message=f"Command {command_type.value} not implemented yet.",
            should_notify=False
        )


async def store_bot_message(message: ChatMessage):
    """Background task to store bot message."""
    
    try:
        from app.database import get_database
        db = get_database()
        
        message_dict = message.dict(by_alias=True, exclude={"id"})
        await db.chat_messages.insert_one(message_dict)
        
    except Exception as e:
        logger.error(f"Failed to store bot message: {e}")


async def store_command_execution(
    command_type: CommandType, 
    args: Dict[str, Any], 
    sender_id: str, 
    channel_id: str
):
    """Background task to store command execution."""
    
    try:
        from app.database import get_database
        from datetime import datetime
        db = get_database()
        
        execution_record = {
            "command_type": command_type.value,
            "args": args,
            "sender_id": sender_id,
            "channel_id": channel_id,
            "executed_at": datetime.utcnow()
        }
        
        await db.command_executions.insert_one(execution_record)
        
    except Exception as e:
        logger.error(f"Failed to store command execution: {e}")
