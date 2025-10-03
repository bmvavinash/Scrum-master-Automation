"""LLM service for AI-powered features using AWS Bedrock."""

import boto3
import json
import logging
from typing import List, Dict, Any, Optional
from app.config import get_settings
from app.models.meeting import MeetingSummary, ActionItem
from app.models.velocity import PredictionInsight

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM operations using AWS Bedrock."""
    
    def __init__(self):
        self.settings = get_settings()
        self.bedrock_client = None
        self._initialize_bedrock()
    
    def _initialize_bedrock(self):
        """Initialize AWS Bedrock client."""
        try:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                region_name=self.settings.aws_region
            )
            logger.info("Bedrock client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            raise
    
    async def generate_meeting_summary(
        self, 
        participant_updates: List[Dict[str, Any]],
        meeting_type: str = "standup"
    ) -> MeetingSummary:
        """Generate AI summary from meeting participant updates."""
        
        prompt = self._build_meeting_summary_prompt(participant_updates, meeting_type)
        
        try:
            response = await self._invoke_bedrock(prompt)
            summary_data = self._parse_meeting_summary_response(response)
            
            return MeetingSummary(**summary_data)
            
        except Exception as e:
            logger.error(f"Failed to generate meeting summary: {e}")
            # Return a basic summary if AI fails
            return self._create_fallback_summary(participant_updates)
    
    async def extract_action_items(self, text: str) -> List[ActionItem]:
        """Extract action items from text using AI."""
        
        prompt = f"""
        Extract action items from the following text. Return a JSON array of action items with the following structure:
        {{
            "title": "Action item title",
            "description": "Detailed description",
            "assignee": "Person responsible",
            "due_date": "YYYY-MM-DD or null",
            "priority": "low/medium/high/critical"
        }}
        
        Text: {text}
        """
        
        try:
            response = await self._invoke_bedrock(prompt)
            action_items_data = json.loads(response)
            
            return [ActionItem(**item) for item in action_items_data]
            
        except Exception as e:
            logger.error(f"Failed to extract action items: {e}")
            return []
    
    async def generate_velocity_insights(
        self, 
        velocity_data: Dict[str, Any],
        team_metrics: List[Dict[str, Any]]
    ) -> List[PredictionInsight]:
        """Generate velocity insights and predictions."""
        
        prompt = self._build_velocity_insights_prompt(velocity_data, team_metrics)
        
        try:
            response = await self._invoke_bedrock(prompt)
            insights_data = json.loads(response)
            
            return [PredictionInsight(**insight) for insight in insights_data]
            
        except Exception as e:
            logger.error(f"Failed to generate velocity insights: {e}")
            return []
    
    async def suggest_code_reviewer(
        self, 
        file_paths: List[str], 
        commit_history: List[Dict[str, Any]],
        team_members: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Suggest the best code reviewer based on file history and expertise."""
        
        prompt = f"""
        Based on the file paths and commit history, suggest the best code reviewer from the team members.
        
        File paths: {file_paths}
        Recent commits: {commit_history[:10]}  # Last 10 commits
        Team members: {team_members}
        
        Return JSON with:
        {{
            "primary_reviewer": "name",
            "secondary_reviewer": "name",
            "reasoning": "explanation",
            "expertise_areas": ["area1", "area2"]
        }}
        """
        
        try:
            response = await self._invoke_bedrock(prompt)
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"Failed to suggest code reviewer: {e}")
            return {
                "primary_reviewer": team_members[0]["name"] if team_members else "Unknown",
                "secondary_reviewer": team_members[1]["name"] if len(team_members) > 1 else None,
                "reasoning": "AI suggestion unavailable",
                "expertise_areas": []
            }
    
    async def analyze_code_quality(
        self, 
        code_changes: List[Dict[str, Any]],
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze code quality and provide recommendations."""
        
        prompt = f"""
        Analyze the following code changes and metrics for quality issues and improvements:
        
        Code changes: {code_changes}
        Metrics: {metrics}
        
        Return JSON with:
        {{
            "quality_score": 0.0-1.0,
            "issues": ["issue1", "issue2"],
            "recommendations": ["rec1", "rec2"],
            "complexity_concerns": ["concern1", "concern2"],
            "test_coverage_concerns": ["concern1", "concern2"]
        }}
        """
        
        try:
            response = await self._invoke_bedrock(prompt)
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"Failed to analyze code quality: {e}")
            return {
                "quality_score": 0.5,
                "issues": [],
                "recommendations": ["AI analysis unavailable"],
                "complexity_concerns": [],
                "test_coverage_concerns": []
            }
    
    async def _invoke_bedrock(self, prompt: str) -> str:
        """Invoke AWS Bedrock with the given prompt."""
        
        body = {
            "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
            "max_tokens_to_sample": 4000,
            "temperature": 0.1,
            "top_p": 0.9,
        }
        
        response = self.bedrock_client.invoke_model(
            modelId=self.settings.bedrock_model_id,
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['completion']
    
    def _build_meeting_summary_prompt(
        self, 
        participant_updates: List[Dict[str, Any]], 
        meeting_type: str
    ) -> str:
        """Build prompt for meeting summary generation."""
        
        updates_text = "\n".join([
            f"{update.get('participant_name', 'Unknown')}: "
            f"Yesterday: {update.get('yesterday_work', 'N/A')}, "
            f"Today: {update.get('today_plan', 'N/A')}, "
            f"Blockers: {', '.join(update.get('blockers', []))}"
            for update in participant_updates
        ])
        
        return f"""
        Analyze this {meeting_type} meeting and provide a comprehensive summary.
        
        Participant Updates:
        {updates_text}
        
        Return a JSON object with:
        {{
            "key_points": ["point1", "point2"],
            "action_items": [
                {{
                    "title": "Action title",
                    "description": "Description",
                    "assignee": "Person name",
                    "due_date": "YYYY-MM-DD or null",
                    "priority": "medium"
                }}
            ],
            "blockers": ["blocker1", "blocker2"],
            "progress_summary": "Overall progress summary",
            "team_mood": "positive/neutral/negative",
            "velocity_insights": {{
                "estimated_completion": "date or null",
                "risk_factors": ["risk1", "risk2"]
            }}
        }}
        """
    
    def _build_velocity_insights_prompt(
        self, 
        velocity_data: Dict[str, Any], 
        team_metrics: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for velocity insights generation."""
        
        return f"""
        Analyze the following sprint velocity data and team metrics to generate insights and predictions:
        
        Velocity Data: {velocity_data}
        Team Metrics: {team_metrics}
        
        Return a JSON array of insights:
        [
            {{
                "type": "deadline_risk|bottleneck|velocity_trend|quality_risk",
                "confidence": 0.0-1.0,
                "description": "Detailed description",
                "recommendations": ["rec1", "rec2"],
                "affected_items": ["item1", "item2"],
                "predicted_date": "YYYY-MM-DD or null",
                "severity": "low|medium|high|critical"
            }}
        ]
        """
    
    def _parse_meeting_summary_response(self, response: str) -> Dict[str, Any]:
        """Parse the meeting summary response from Bedrock."""
        try:
            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            json_str = response[start_idx:end_idx]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse meeting summary response: {e}")
            return self._create_fallback_summary_data()
    
    def _create_fallback_summary(self, participant_updates: List[Dict[str, Any]]) -> MeetingSummary:
        """Create a fallback summary when AI fails."""
        return MeetingSummary(
            key_points=["Meeting completed", "Updates collected"],
            action_items=[],
            blockers=[update.get('blockers', []) for update in participant_updates if update.get('blockers')],
            progress_summary="Updates collected from all participants",
            team_mood="neutral"
        )
    
    def _create_fallback_summary_data(self) -> Dict[str, Any]:
        """Create fallback summary data."""
        return {
            "key_points": ["Meeting completed"],
            "action_items": [],
            "blockers": [],
            "progress_summary": "Updates collected",
            "team_mood": "neutral",
            "velocity_insights": {}
        }
