"""Microsoft Teams bot service."""

import logging
from typing import Dict, Any, Optional
from botbuilder.core import TurnContext, ActivityHandler, MessageFactory
from botbuilder.schema import ChannelAccount, Activity, ActivityTypes
from app.models.chat import TeamsAdaptiveCard, BotResponse
from app.services.llm_service import LLMService
from app.services.jira_service import JiraService
import json

logger = logging.getLogger(__name__)


class ScrumBot(ActivityHandler):
    """Microsoft Teams bot for scrum automation."""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.jira_service = JiraService()
    
    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages."""
        
        try:
            user_message = turn_context.activity.text
            user_id = turn_context.activity.from_property.id
            user_name = turn_context.activity.from_property.name
            channel_id = turn_context.activity.conversation.id
            
            logger.info(f"Received message from {user_name}: {user_message}")
            
            # Process the message
            response = await self.process_message(user_message, user_id, user_name, channel_id)
            
            # Send response
            if response.card:
                await turn_context.send_activity(MessageFactory.attachment(self.create_adaptive_card_attachment(response.card)))
            else:
                await turn_context.send_activity(MessageFactory.text(response.message))
            
            # Send additional attachments if any
            for attachment in response.attachments:
                await turn_context.send_activity(MessageFactory.attachment(attachment))
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await turn_context.send_activity(MessageFactory.text("Sorry, I encountered an error processing your message."))
    
    async def on_members_added_activity(self, members_added: list, turn_context: TurnContext):
        """Handle when members are added to the conversation."""
        
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome_message = self.create_welcome_card()
                await turn_context.send_activity(MessageFactory.attachment(self.create_adaptive_card_attachment(welcome_message)))
    
    async def process_message(self, message: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Process incoming message and generate response."""
        
        # Check if it's a command
        if message.startswith('/'):
            return await self.process_command(message, user_id, user_name, channel_id)
        
        # Check for keywords and generate contextual response
        message_lower = message.lower()
        
        if any(keyword in message_lower for keyword in ['standup', 'meeting', 'update']):
            return await self.handle_standup_related_message(message, user_id, user_name, channel_id)
        
        elif any(keyword in message_lower for keyword in ['task', 'ticket', 'jira']):
            return await self.handle_task_related_message(message, user_id, user_name, channel_id)
        
        elif any(keyword in message_lower for keyword in ['review', 'code', 'pr']):
            return await self.handle_code_related_message(message, user_id, user_name, channel_id)
        
        elif any(keyword in message_lower for keyword in ['velocity', 'sprint', 'metrics']):
            return await self.handle_velocity_related_message(message, user_id, user_name, channel_id)
        
        else:
            return BotResponse(
                message="I'm here to help with scrum automation! Try `/help` to see available commands.",
                should_notify=False
            )
    
    async def process_command(self, message: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Process bot commands."""
        
        parts = message.split(' ', 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if command == '/help':
            return BotResponse(
                message="",
                card=self.create_help_card()
            )
        
        elif command == '/create-task':
            return await self.handle_create_task_command(args, user_id, user_name, channel_id)
        
        elif command == '/create-blocker':
            return await self.handle_create_blocker_command(args, user_id, user_name, channel_id)
        
        elif command == '/schedule-standup':
            return await self.handle_schedule_standup_command(args, user_id, user_name, channel_id)
        
        elif command == '/get-status':
            return await self.handle_get_status_command(user_id, user_name, channel_id)
        
        elif command == '/get-velocity':
            return await self.handle_get_velocity_command(user_id, user_name, channel_id)
        
        elif command == '/suggest-reviewer':
            return await self.handle_suggest_reviewer_command(args, user_id, user_name, channel_id)
        
        elif command == '/analyze-code':
            return await self.handle_analyze_code_command(args, user_id, user_name, channel_id)
        
        elif command == '/get-metrics':
            return await self.handle_get_metrics_command(user_id, user_name, channel_id)
        
        elif command == '/insights':
            return await self.handle_get_insights_command(user_id, user_name, channel_id)
        
        else:
            return BotResponse(
                message=f"Unknown command: {command}. Type `/help` for available commands.",
                should_notify=False
            )
    
    async def handle_create_task_command(self, args: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle create task command."""
        
        if not args:
            return BotResponse(
                message="Please provide a task title. Usage: `/create-task <title>`",
                should_notify=False
            )
        
        try:
            # Create Jira ticket
            ticket = await self.jira_service.create_ticket(
                title=args,
                description=f"Created by {user_name} via Teams bot",
                assignee=user_id
            )
            
            if ticket:
                card = self.create_task_created_card(ticket)
                return BotResponse(
                    message=f"✅ Created task: {ticket.jira_key}",
                    card=card,
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
    
    async def handle_create_blocker_command(self, args: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle create blocker command."""
        
        if not args:
            return BotResponse(
                message="Please provide a blocker description. Usage: `/create-blocker <description>`",
                should_notify=False
            )
        
        try:
            # Create Jira ticket with blocker label
            ticket = await self.jira_service.create_ticket(
                title=f"BLOCKER: {args}",
                description=f"Blocking issue reported by {user_name} via Teams bot",
                assignee=user_id,
                labels=["blocker", "urgent"]
            )
            
            if ticket:
                card = self.create_blocker_created_card(ticket)
                return BotResponse(
                    message=f"🚨 Created blocker: {ticket.jira_key}",
                    card=card,
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
    
    async def handle_schedule_standup_command(self, args: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle schedule standup command."""
        
        card = self.create_standup_scheduling_card()
        return BotResponse(
            message="📅 Standup scheduling feature coming soon!",
            card=card,
            should_notify=False
        )
    
    async def handle_get_status_command(self, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle get status command."""
        
        card = self.create_sprint_status_card()
        return BotResponse(
            message="📊 Sprint status",
            card=card,
            should_notify=False
        )
    
    async def handle_get_velocity_command(self, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle get velocity command."""
        
        card = self.create_velocity_card()
        return BotResponse(
            message="📈 Velocity metrics",
            card=card,
            should_notify=False
        )
    
    async def handle_suggest_reviewer_command(self, args: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle suggest reviewer command."""
        
        if not args:
            return BotResponse(
                message="Please provide file paths. Usage: `/suggest-reviewer <file1,file2>`",
                should_notify=False
            )
        
        file_paths = [path.strip() for path in args.split(',')]
        card = self.create_reviewer_suggestion_card(file_paths)
        
        return BotResponse(
            message=f"🔍 Code reviewer suggestion for {len(file_paths)} files",
            card=card,
            should_notify=False
        )
    
    async def handle_analyze_code_command(self, args: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle analyze code command."""
        
        if not args:
            return BotResponse(
                message="Please provide a commit SHA. Usage: `/analyze-code <commit_sha>`",
                should_notify=False
            )
        
        card = self.create_code_analysis_card(args)
        return BotResponse(
            message=f"🔬 Code analysis for commit {args}",
            card=card,
            should_notify=False
        )
    
    async def handle_get_metrics_command(self, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle get metrics command."""
        
        card = self.create_metrics_card()
        return BotResponse(
            message="📊 Code quality metrics",
            card=card,
            should_notify=False
        )
    
    async def handle_get_insights_command(self, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle get insights command."""
        
        card = self.create_insights_card()
        return BotResponse(
            message="🧠 AI insights",
            card=card,
            should_notify=False
        )
    
    async def handle_standup_related_message(self, message: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle standup-related messages."""
        
        return BotResponse(
            message="I can help with standup meetings! Try `/schedule-standup` or `/get-status` for more options.",
            should_notify=False
        )
    
    async def handle_task_related_message(self, message: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle task-related messages."""
        
        return BotResponse(
            message="I can help with tasks! Try `/create-task <title>` or `/create-blocker <description>` to create tickets.",
            should_notify=False
        )
    
    async def handle_code_related_message(self, message: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle code-related messages."""
        
        return BotResponse(
            message="I can help with code reviews! Try `/suggest-reviewer <files>` or `/analyze-code <commit>` for code intelligence features.",
            should_notify=False
        )
    
    async def handle_velocity_related_message(self, message: str, user_id: str, user_name: str, channel_id: str) -> BotResponse:
        """Handle velocity-related messages."""
        
        return BotResponse(
            message="I can help with velocity metrics! Try `/get-velocity` or check the dashboard for detailed analytics.",
            should_notify=False
        )
    
    def create_adaptive_card_attachment(self, card: TeamsAdaptiveCard) -> Dict[str, Any]:
        """Create adaptive card attachment."""
        
        return {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": card.dict()
        }
    
    def create_welcome_card(self) -> TeamsAdaptiveCard:
        """Create welcome card for new members."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "🤖 Welcome to Scrum Automation Bot!",
                    "weight": "Bolder",
                    "size": "Large"
                },
                {
                    "type": "TextBlock",
                    "text": "I'm here to help automate your scrum processes with AI-powered features.",
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "Try `/help` to see all available commands!",
                    "wrap": True
                }
            ]
        )
    
    def create_help_card(self) -> TeamsAdaptiveCard:
        """Create help card with available commands."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "🤖 Scrum Automation Bot Commands",
                    "weight": "Bolder",
                    "size": "Large"
                },
                {
                    "type": "TextBlock",
                    "text": "**Meeting Commands:**",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "• `/schedule-standup` - Schedule a standup meeting\n• `/get-status` - Get current sprint status\n• `/get-velocity` - Get team velocity metrics",
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "**Task Commands:**",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "• `/create-task <title>` - Create a new Jira task\n• `/create-blocker <description>` - Create a blocker ticket",
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "**Code Intelligence:**",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "• `/suggest-reviewer <files>` - Suggest code reviewer\n• `/analyze-code <commit>` - Analyze code changes\n• `/get-metrics` - Get code quality metrics",
                    "wrap": True
                }
            ]
        )
    
    def create_task_created_card(self, ticket) -> TeamsAdaptiveCard:
        """Create card for task creation confirmation."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "✅ Task Created Successfully",
                    "weight": "Bolder",
                    "color": "Good"
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "Ticket Key", "value": ticket.jira_key},
                        {"title": "Title", "value": ticket.title},
                        {"title": "Status", "value": ticket.status.value},
                        {"title": "Priority", "value": ticket.priority.value}
                    ]
                }
            ],
            actions=[
                {
                    "type": "Action.OpenUrl",
                    "title": "View in Jira",
                    "url": f"https://your-domain.atlassian.net/browse/{ticket.jira_key}"
                }
            ]
        )
    
    def create_blocker_created_card(self, ticket) -> TeamsAdaptiveCard:
        """Create card for blocker creation confirmation."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "🚨 Blocker Created",
                    "weight": "Bolder",
                    "color": "Attention"
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "Ticket Key", "value": ticket.jira_key},
                        {"title": "Title", "value": ticket.title},
                        {"title": "Status", "value": ticket.status.value},
                        {"title": "Priority", "value": ticket.priority.value}
                    ]
                }
            ],
            actions=[
                {
                    "type": "Action.OpenUrl",
                    "title": "View in Jira",
                    "url": f"https://your-domain.atlassian.net/browse/{ticket.jira_key}"
                }
            ]
        )
    
    def create_standup_scheduling_card(self) -> TeamsAdaptiveCard:
        """Create card for standup scheduling."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "📅 Standup Scheduling",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "This feature is coming soon! For now, you can manually schedule meetings through your calendar.",
                    "wrap": True
                }
            ]
        )
    
    def create_sprint_status_card(self) -> TeamsAdaptiveCard:
        """Create card for sprint status."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "📊 Sprint Status",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "Sprint status feature coming soon! Check your Jira board for current status.",
                    "wrap": True
                }
            ]
        )
    
    def create_velocity_card(self) -> TeamsAdaptiveCard:
        """Create card for velocity metrics."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "📈 Velocity Metrics",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "Velocity metrics feature coming soon! Check the dashboard for detailed metrics.",
                    "wrap": True
                }
            ]
        )
    
    def create_reviewer_suggestion_card(self, file_paths: list) -> TeamsAdaptiveCard:
        """Create card for reviewer suggestion."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "🔍 Code Reviewer Suggestion",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": f"Files to review: {', '.join(file_paths)}",
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "Code reviewer suggestion feature coming soon!",
                    "wrap": True
                }
            ]
        )
    
    def create_code_analysis_card(self, commit_sha: str) -> TeamsAdaptiveCard:
        """Create card for code analysis."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "🔬 Code Analysis",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": f"Commit: {commit_sha}",
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "Code analysis feature coming soon!",
                    "wrap": True
                }
            ]
        )
    
    def create_metrics_card(self) -> TeamsAdaptiveCard:
        """Create card for code metrics."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "📊 Code Quality Metrics",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "Code quality metrics feature coming soon! Check the dashboard for detailed metrics.",
                    "wrap": True
                }
            ]
        )
    
    def create_insights_card(self) -> TeamsAdaptiveCard:
        """Create card for AI insights."""
        
        return TeamsAdaptiveCard(
            body=[
                {
                    "type": "TextBlock",
                    "text": "🧠 AI Insights",
                    "weight": "Bolder"
                },
                {
                    "type": "TextBlock",
                    "text": "AI insights feature coming soon! Check the dashboard for AI-generated insights and predictions.",
                    "wrap": True
                }
            ]
        )
