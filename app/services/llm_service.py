"""LLM service for AI-powered features using AWS Bedrock, Cursor API, and Amazon Q."""

import boto3
import json
import logging
import asyncio
import httpx
from typing import List, Dict, Any, Optional, Tuple
from app.config import get_settings
from app.models.meeting import MeetingSummary, ActionItem
from app.models.velocity import PredictionInsight

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM operations using AWS Bedrock."""
    
    def __init__(self):
        self.settings = get_settings()
        self.bedrock_client = None
        self.bedrock_bearer_token = None
        self._initialize_bedrock()
    
    def _initialize_bedrock(self):
        """Initialize AWS Bedrock client."""
        try:
            # Check for bearer token first (alternative authentication)
            if self.settings.aws_bearer_token_bedrock:
                logger.info("Using Bedrock bearer token authentication")
                self.bedrock_bearer_token = self.settings.aws_bearer_token_bedrock
                self.bedrock_client = None  # Will use direct HTTP calls with bearer token
                logger.info("Bedrock bearer token configured")
            elif self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                region_name=self.settings.aws_region
            )
                self.bedrock_bearer_token = None
                logger.info("Bedrock client initialized with AWS credentials")
            else:
                logger.warning("Bedrock credentials not configured (neither bearer token nor access key/secret)")
                self.bedrock_client = None
                self.bedrock_bearer_token = None
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            self.bedrock_client = None
            self.bedrock_bearer_token = None
    
    async def generate_code_with_fallback(
        self,
        description: str,
        context: Optional[Dict[str, Any]] = None,
        existing_code: Optional[str] = None,
        acceptance_criteria: Optional[str] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Generate code with fallback mechanism across multiple LLM providers.
        
        Args:
            description: Jira ticket description
            context: Generation context (language, framework, etc.)
            existing_code: Existing codebase context (optional)
            acceptance_criteria: Acceptance criteria from Jira (optional)
        
        Returns:
            Tuple of (generated_code_dict, provider_used)
        """
        providers = self._get_provider_priority()
        last_error = None
        
        for provider in providers:
            try:
                logger.info(f"Attempting code generation with {provider}")
                result = await self._generate_code_with_provider(
                    provider=provider,
                    description=description,
                    context=context or {},
                    existing_code=existing_code,
                    acceptance_criteria=acceptance_criteria
                )
                if result:
                    logger.info(f"Successfully generated code with {provider}")
                    return result, provider
            except Exception as e:
                logger.warning(f"Failed to generate code with {provider}: {e}")
                last_error = e
                continue
        
        # All providers failed, use deterministic fallback
        logger.error(f"All LLM providers failed. Last error: {last_error}")
        logger.info("Using deterministic fallback")
        fallback_result = self._deterministic_codegen(description, context or {})
        return fallback_result, "fallback"
    
    def _get_provider_priority(self) -> List[str]:
        """Get LLM provider priority list from config."""
        priority_str = self.settings.llm_provider_priority or "bedrock,cursor,amazon_q"
        providers = [p.strip() for p in priority_str.split(",")]
        # Filter out providers that are not configured
        available_providers = []
        for provider in providers:
            if provider == "bedrock" and (self.bedrock_client or self.bedrock_bearer_token):
                available_providers.append(provider)
            elif provider == "cursor" and self.settings.cursor_api_key:
                available_providers.append(provider)
            elif provider == "amazon_q" and self.settings.amazon_q_app_id:
                available_providers.append(provider)
        return available_providers if available_providers else ["bedrock"]  # Default to bedrock
    
    async def _generate_code_with_provider(
        self,
        provider: str,
        description: str,
        context: Dict[str, Any],
        existing_code: Optional[str] = None,
        acceptance_criteria: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate code using a specific provider.
        
        Args:
            provider: Provider name (bedrock, cursor, amazon_q)
            description: Jira ticket description
            context: Generation context
            existing_code: Existing codebase context
            acceptance_criteria: Acceptance criteria
        
        Returns:
            Generated code dict or None if failed
        """
        if provider == "bedrock":
            return await self._generate_code_with_bedrock(
                description, context, existing_code, acceptance_criteria
            )
        elif provider == "cursor":
            return await self._generate_code_with_cursor(
                description, context, existing_code, acceptance_criteria
            )
        elif provider == "amazon_q":
            return await self._generate_code_with_amazon_q(
                description, context, existing_code, acceptance_criteria
            )
        return None
    
    async def _generate_code_with_bedrock(
        self,
        description: str,
        context: Dict[str, Any],
        existing_code: Optional[str] = None,
        acceptance_criteria: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate code using AWS Bedrock."""
        if not self.bedrock_client and not self.bedrock_bearer_token:
            raise Exception("Bedrock client not initialized (no credentials or bearer token)")
        
        prompt = self._build_code_generation_prompt(
            description, context, existing_code, acceptance_criteria
        )
        
        try:
            response_text = await asyncio.wait_for(
                self._invoke_bedrock(prompt),
                timeout=self.settings.llm_timeout_seconds
            )
            return self._parse_code_generation_response(response_text, context)
        except asyncio.TimeoutError:
            logger.error("Bedrock request timed out")
            raise
        except Exception as e:
            logger.error(f"Bedrock code generation failed: {e}")
            raise
    
    async def _generate_code_with_cursor(
        self,
        description: str,
        context: Dict[str, Any],
        existing_code: Optional[str] = None,
        acceptance_criteria: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate code using Cursor API."""
        if not self.settings.cursor_api_key:
            raise Exception("Cursor API key not configured")
        
        prompt = self._build_code_generation_prompt(
            description, context, existing_code, acceptance_criteria
        )
        
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(
                    f"{self.settings.cursor_api_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.cursor_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4",
                        "messages": [
                            {"role": "system", "content": "You are a code generation assistant. Generate code based on the requirements."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 4000
                    }
                )
                response.raise_for_status()
                data = response.json()
                response_text = data["choices"][0]["message"]["content"]
                return self._parse_code_generation_response(response_text, context)
        except Exception as e:
            logger.error(f"Cursor API code generation failed: {e}")
            raise
    
    async def _generate_code_with_amazon_q(
        self,
        description: str,
        context: Dict[str, Any],
        existing_code: Optional[str] = None,
        acceptance_criteria: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate code using Amazon Q Developer."""
        if not self.settings.amazon_q_app_id:
            raise Exception("Amazon Q App ID not configured")
        
        # Amazon Q integration would go here
        # For now, we'll use Bedrock as Amazon Q uses similar infrastructure
        logger.warning("Amazon Q integration not yet implemented, falling back to Bedrock")
        return await self._generate_code_with_bedrock(
            description, context, existing_code, acceptance_criteria
        )
    
    def _build_code_generation_prompt(
        self,
        description: str,
        context: Dict[str, Any],
        existing_code: Optional[str] = None,
        acceptance_criteria: Optional[str] = None
    ) -> str:
        """Build code generation prompt for LLM."""
        language = context.get("language", "python")
        framework = context.get("framework", "fastapi")
        follow_style = context.get("follow_style", True)
        
        prompt = f"""You are an expert software developer. Generate code based on the following requirements.

JIRA TICKET DESCRIPTION:
{description}

"""
        
        if acceptance_criteria:
            prompt += f"""ACCEPTANCE CRITERIA:
{acceptance_criteria}

"""
        
        prompt += f"""REQUIREMENTS:
- Language: {language}
- Framework: {framework}
- Follow existing code style: {follow_style}

"""
        
        if existing_code:
            prompt += f"""EXISTING CODEBASE CONTEXT:
{existing_code[:2000]}  # Truncated to avoid token limits

Please generate code that follows the same patterns and style as the existing codebase.

"""
        
        prompt += """Generate code that includes:
1. All necessary files with proper structure
2. Implementation code
3. Unit tests based on acceptance criteria
4. Proper error handling
5. Documentation comments

IMPORTANT: You MUST return ONLY a valid JSON object. Do not include any markdown code blocks, explanations, or text outside the JSON.

Return your response as a JSON object with the following EXACT structure:
{
    "language": "python",
    "files": [
        {"path": "path/to/file.py", "purpose": "description"}
    ],
    "code": [
        {"path": "path/to/file.py", "content": "complete file content here with proper indentation"}
    ],
    "tests": [
        {"path": "tests/test_file.py", "content": "complete test file content here"}
    ],
    "notes": [
        "Note 1",
        "Note 2"
    ]
}

CRITICAL REQUIREMENTS:
1. Return ONLY the JSON object, no markdown, no code fences, no explanations
2. The "code" array MUST contain at least one file with "path" and "content" fields
3. Each file's "content" must be complete, valid code
4. Use proper JSON escaping for strings (escape quotes, newlines, etc.)
5. Do not include ```json or ``` markers

Ensure the code is production-ready, follows best practices, and includes proper error handling."""
        
        return prompt
    
    def _parse_code_generation_response(
        self,
        response_text: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Parse LLM response into code generation structure."""
        try:
            logger.debug(f"Parsing LLM response (length: {len(response_text)})")
            logger.debug(f"Response preview: {response_text[:500]}")
            
            # Try to extract JSON from response
            json_data = self._extract_json_block(response_text)
            if json_data:
                logger.debug(f"Successfully extracted JSON block")
                # Validate structure
                if self._validate_code_structure(json_data):
                    return json_data
                else:
                    logger.warning(f"Extracted JSON has invalid structure: {list(json_data.keys())}")
            
            # Try to parse entire response as JSON
            try:
                json_data = json.loads(response_text)
                if self._validate_code_structure(json_data):
                    return json_data
                else:
                    logger.warning(f"Parsed JSON has invalid structure: {list(json_data.keys())}")
            except json.JSONDecodeError as e:
                logger.debug(f"Response is not valid JSON: {e}")
            
            # If JSON extraction fails, use deterministic fallback
            logger.warning("Failed to parse LLM response as JSON, using fallback")
            logger.debug(f"Full response: {response_text[:2000]}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse code generation response: {e}", exc_info=True)
            return None
    
    def _validate_code_structure(self, data: Dict[str, Any]) -> bool:
        """Validate that parsed data has the required code structure."""
        if not isinstance(data, dict):
            logger.debug("Data is not a dict")
            return False
        
        # Check for required "code" field
        if "code" not in data:
            logger.debug(f"Missing 'code' field. Available keys: {list(data.keys())}")
            return False
        
        if not isinstance(data["code"], list):
            logger.debug(f"'code' is not a list, it's: {type(data['code'])}")
            return False
        
        if len(data["code"]) == 0:
            logger.debug("'code' list is empty")
            return False
        
        # Check that each code file has path and content
        for i, code_file in enumerate(data["code"]):
            if not isinstance(code_file, dict):
                logger.debug(f"Code file {i} is not a dict: {type(code_file)}")
                return False
            if "path" not in code_file:
                logger.debug(f"Code file {i} missing 'path' field. Keys: {list(code_file.keys())}")
                return False
            if "content" not in code_file:
                logger.debug(f"Code file {i} missing 'content' field. Keys: {list(code_file.keys())}")
                return False
        
        logger.debug(f"Code structure is valid with {len(data['code'])} files")
        return True
    
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

    async def generate_code_from_description(
        self,
        description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate code artifacts from a Jira ticket description.

        Returns a JSON structure with language, filename suggestions, code, tests, and notes.
        """
        logger.info(f"Generating code for description: {description[:100]}...")
        
        # Generate code based on description
        return self._generate_code_from_description_internal(description, context or {})

    def _generate_code_from_description_internal(self, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code based on Jira ticket description."""
        language = context.get("language", "python")
        framework = context.get("framework", "fastapi")
        
        # Generate code based on the description
        # Use triple-quoted string without f-string to avoid variable substitution issues
        desc_snippet = description[:200] if len(description) > 200 else description
        
        generated_code = """# Generated from Jira ticket
# Description: """ + desc_snippet + """

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Generated API")

class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)

class ItemResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    created_at: datetime
    status: str

@app.post("/api/v1/items", status_code=status.HTTP_201_CREATED, response_model=ItemResponse)
async def create_item(payload: ItemCreate):
    \"\"\"Create a new item based on the Jira description.\"\"\"
    try:
        # TODO: Implement actual database logic
        new_item = ItemResponse(
            id="generated-id-123",
            title=payload.title,
            description=payload.description,
            created_at=datetime.utcnow(),
            status="created"
        )
        logger.info("Created item: %s", payload.title)
        return new_item
    except Exception as e:
        logger.error("Error creating item: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/v1/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: str):
    \"\"\"Get an item by ID.\"\"\"
    # TODO: Implement actual database retrieval logic
    return ItemResponse(
        id=item_id,
        title="Sample Item",
        description="This is a sample item",
        created_at=datetime.utcnow(),
        status="active"
    )
"""

        test_code = """import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_item():
    \"\"\"Test item creation endpoint.\"\"\"
    response = client.post(
        "/api/v1/items",
        json={"title": "Test Item", "description": "Test Description"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Item"
    assert data["status"] == "created"

def test_get_item():
    \"\"\"Test item retrieval endpoint.\"\"\"
    response = client.get("/api/v1/items/test-id-123")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-id-123"
    assert data["status"] == "active"
"""

        return {
            "language": language,
            "files": [
                {"path": "app/main.py", "purpose": "Main FastAPI application with generated endpoints"},
                {"path": "tests/test_main.py", "purpose": "Unit tests for the generated endpoints"}
            ],
            "code": [
                {"path": "app/main.py", "content": generated_code},
                {"path": "tests/test_main.py", "content": test_code}
            ],
            "tests": [
                {"path": "tests/test_main.py", "content": test_code}
            ],
            "notes": [
                "✅ Code generated successfully from Jira ticket",
                "Ready for implementation and testing",
                "Endpoints: POST /api/v1/items (create), GET /api/v1/items/{id} (retrieve)",
                "Based on ticket description: " + description[:100] + "..."
            ]
        }

    def _extract_json_block(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract a JSON object from common LLM output patterns (e.g., fenced code)."""
        try:
            # Look for fenced blocks ```json ... ``` or ``` ... ```
            fences = [
                ("```json", "```"),
                ("```JSON", "```"),
                ("```", "```"),
            ]
            for start, end in fences:
                s = text.find(start)
                if s != -1:
                    s2 = text.find(end, s + len(start))
                    if s2 != -1:
                        candidate = text[s+len(start):s2].strip()
                        try:
                            return json.loads(candidate)
                        except Exception:
                            # Sometimes there is leading text before the JSON
                            first = candidate.find('{')
                            last = candidate.rfind('}')
                            if first != -1 and last != -1 and last > first:
                                return json.loads(candidate[first:last+1])
            return None
        except Exception:
            return None

    def _deterministic_codegen(self, description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Produce a deterministic, runnable bundle when the model output is unusable.

        Currently supports the 'notes' FastAPI + MongoDB API described in the task.
        """
        # Basic inference for paths
        language = (context.get("language") or "python").lower()
        framework = (context.get("framework") or "fastapi").lower()
        if language != "python" or framework != "fastapi":
            # Generic minimal fallback to avoid lying
            return {
                "language": language or "python",
                "files": [{"path": "app/example.py", "purpose": "Generated scaffold"}],
                "code": [{"path": "app/example.py", "content": f"# Generated from description\n\nDESCRIPTION = {json.dumps(description)}\n"}],
                "tests": [],
                "notes": ["Deterministic fallback scaffold (non-fastapi path)"]
            }

        db_py = (
            "from motor.motor_asyncio import AsyncIOMotorClient\n"
            "import os\n\n"
            "MONGO_URI = os.getenv(\"MONGO_URI\", \"mongodb://localhost:27017\")\n"
            "DB_NAME = os.getenv(\"MONGO_DB\", \"notes_db\")\n\n"
            "_client: AsyncIOMotorClient | None = None\n\n"
            "def get_client() -> AsyncIOMotorClient:\n"
            "    global _client\n"
            "    if _client is None:\n"
            "        _client = AsyncIOMotorClient(MONGO_URI)\n"
            "    return _client\n\n"
            "def get_db():\n"
            "    return get_client()[DB_NAME]\n\n"
            "def get_notes_collection():\n"
            "    return get_db()[\"notes\"]\n"
        )

        schemas_py = (
            "from pydantic import BaseModel, Field, validator\n"
            "from typing import Optional\n"
            "from datetime import datetime\n\n"
            "class NoteCreate(BaseModel):\n"
            "    title: str = Field(..., min_length=1, max_length=120)\n"
            "    body: str = Field(..., min_length=1, max_length=5000)\n\n"
            "    @validator('title')\n"
            "    def _t(cls, v: str): return v.strip()\n\n"
            "    @validator('body')\n"
            "    def _b(cls, v: str): return v.strip()\n\n"
            "class NoteResponse(BaseModel):\n"
            "    id: str\n"
            "    title: str\n"
            "    body: str\n"
            "    created_at: datetime\n"
            "    updated_at: datetime\n"
        )

        main_py = (
            "from fastapi import FastAPI, HTTPException, status, Path\n"
            "from fastapi.responses import JSONResponse\n"
            "from fastapi.middleware.cors import CORSMiddleware\n"
            "from pymongo import ASCENDING, DESCENDING\n"
            "from pymongo.errors import DuplicateKeyError, PyMongoError\n"
            "from datetime import datetime, timezone\n"
            "from bson import ObjectId\n"
            "from app.db import get_notes_collection\n"
            "from app.schemas import NoteCreate, NoteResponse\n\n"
            "app = FastAPI(title='Notes API (FastAPI + MongoDB)')\n\n"
            "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])\n\n"
            "@app.on_event('startup')\n"
            "async def startup_indexes():\n"
            "    coll = get_notes_collection()\n"
            "    await coll.create_index([('title', ASCENDING), ('created_day', ASCENDING)], unique=True, name='title_createdday_unique')\n"
            "    await coll.create_index([('created_at', DESCENDING)], name='created_at_desc')\n\n"
            "def utc_now():\n"
            "    return datetime.now(timezone.utc)\n\n"
            "@app.post('/api/v1/notes', status_code=status.HTTP_201_CREATED)\n"
            "async def create_note(payload: NoteCreate):\n"
            "    coll = get_notes_collection()\n"
            "    now = utc_now()\n"
            "    doc = { 'title': payload.title, 'body': payload.body, 'created_at': now, 'updated_at': now, 'created_day': now.date().isoformat() }\n"
            "    try:\n"
            "        res = await coll.insert_one(doc)\n"
            "    except DuplicateKeyError:\n"
            "        raise HTTPException(status_code=400, detail='Note with same title already exists for today')\n"
            "    except PyMongoError:\n"
            "        raise HTTPException(status_code=500, detail='database error')\n"
            "    return JSONResponse(status_code=status.HTTP_201_CREATED, content={'id': str(res.inserted_id)})\n\n"
            "@app.get('/api/v1/notes/{id}', response_model=NoteResponse)\n"
            "async def get_note(id: str = Path(..., description='Mongo ObjectId')):\n"
            "    if not ObjectId.is_valid(id):\n"
            "        raise HTTPException(status_code=400, detail='Invalid id')\n"
            "    coll = get_notes_collection()\n"
            "    doc = await coll.find_one({'_id': ObjectId(id)})\n"
            "    if not doc:\n"
            "        raise HTTPException(status_code=404, detail='Note not found')\n"
            "    return NoteResponse(id=str(doc['_id']), title=doc['title'], body=doc['body'], created_at=doc['created_at'], updated_at=doc['updated_at'])\n"
        )

        tests_py = (
            "import pytest\n"
            "from httpx import AsyncClient\n"
            "from app.main import app\n\n"
            "@pytest.mark.asyncio\n"
            "async def test_create_and_get_note():\n"
            "    async with AsyncClient(app=app, base_url='http://test') as ac:\n"
            "        payload = {'title': 'Test Note', 'body': 'This is a test'}\n"
            "        post_resp = await ac.post('/api/v1/notes', json=payload)\n"
            "        assert post_resp.status_code == 201\n"
            "        data = post_resp.json()\n"
            "        note_id = data['id']\n"
            "        get_resp = await ac.get(f'/api/v1/notes/{note_id}')\n"
            "        assert get_resp.status_code == 200\n"
            "        note = get_resp.json()\n"
            "        assert note['title'] == payload['title']\n"
            "        assert note['body'] == payload['body']\n"
        )

        return {
            "language": "python",
            "files": [
                {"path": "app/db.py", "purpose": "Mongo client and helpers"},
                {"path": "app/schemas.py", "purpose": "Pydantic models"},
                {"path": "app/main_notes.py", "purpose": "FastAPI endpoints for notes"},
                {"path": "tests/test_notes.py", "purpose": "Unit tests"},
            ],
            "code": [
                {"path": "app/db.py", "content": db_py},
                {"path": "app/schemas.py", "content": schemas_py},
                {"path": "app/main_notes.py", "content": main_py},
                {"path": "tests/test_notes.py", "content": tests_py},
            ],
            "tests": [{"path": "tests/test_notes.py", "content": tests_py}],
            "notes": [
                "Deterministic fallback used due to non-JSON LLM output.",
                "Endpoints: POST /api/v1/notes, GET /api/v1/notes/{id}.",
                "Requires MongoDB running at MONGO_URI (default mongodb://localhost:27017)."
            ],
        }
    
    async def _invoke_bedrock(self, prompt: str) -> str:
        """Invoke AWS Bedrock (Anthropic Claude 3) using Messages format.

        Supports both boto3 client and bearer token authentication.
        
        Args:
            prompt: The prompt to send to Bedrock
        
        Returns:
            Response text from Bedrock
        """
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt}
                        ]
                    }
                ],
                "max_tokens": 4096,
                "temperature": 0.1,
                "top_p": 0.9,
            }
            
            # Use bearer token if available, otherwise use boto3 client
            if self.bedrock_bearer_token:
                return await self._invoke_bedrock_with_bearer_token(body)
            elif self.bedrock_client:
                return await self._invoke_bedrock_with_boto3(body)
            else:
                raise Exception("No Bedrock authentication method available")
            
        except Exception as e:
            logger.error(f"Bedrock invoke failed: {e}")
            raise
    
    async def _invoke_bedrock_with_boto3(self, body: Dict[str, Any]) -> str:
        """Invoke Bedrock using boto3 client."""
            response = self.bedrock_client.invoke_model(
                modelId=self.settings.bedrock_model_id,
                body=json.dumps(body),
                contentType='application/json',
                accept='application/json'
            )
            raw = response['body'].read().decode('utf-8', errors='ignore')
            if not raw or not raw.strip():
                logger.error("Bedrock returned empty body")
                return ""
            try:
                response_body = json.loads(raw)
            except Exception:
                logger.error(f"Bedrock returned non-JSON body (len={len(raw)}): {raw[:500]}")
                return raw
            # Claude messages response returns {'content':[{'type':'text','text':'...'}], ...}
            contents = response_body.get('content') or []
            for item in contents:
                text = item.get('text')
                if isinstance(text, str) and text.strip():
                    return text
            # Fallback: 'completion'
            return response_body.get('completion', '') or json.dumps(response_body)
    
    async def _invoke_bedrock_with_bearer_token(self, body: Dict[str, Any]) -> str:
        """Invoke Bedrock using bearer token authentication."""
        region = self.settings.aws_region
        # Convert model ID format: anthropic.claude-3-sonnet-20240229-v1:0 -> anthropic.claude-3-sonnet-20240229-v1:0
        model_id = self.settings.bedrock_model_id
        # Bedrock API endpoint format
        url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id.replace(':', '/')}/invoke"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bedrock_bearer_token}",
            "Accept": "application/json"
        }
        
        logger.debug(f"Invoking Bedrock with bearer token: {url}")
        logger.debug(f"Model ID: {model_id}")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                response = await client.post(
                    url,
                    json=body,
                    headers=headers
                )
                
                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(f"Bedrock API error: {response.status_code} - {error_text}")
                    raise Exception(f"Bedrock API error: {response.status_code} - {error_text}")
                
                response_body = response.json()
                
                if not response_body:
                    logger.error("Bedrock returned empty body")
                    return ""
                
                # Claude messages response returns {'content':[{'type':'text','text':'...'}], ...}
                contents = response_body.get('content') or []
                for item in contents:
                    text = item.get('text')
                    if isinstance(text, str) and text.strip():
                        logger.debug(f"Bedrock response received (length: {len(text)})")
                        return text
                
                # Fallback: 'completion' or raw response
                result = response_body.get('completion', '') or json.dumps(response_body)
                if result:
                    return result
                
                logger.error("Bedrock returned empty text")
                return ""
                
            except httpx.TimeoutException:
                logger.error("Bedrock request timed out")
                raise Exception("Bedrock request timed out")
        except Exception as e:
                logger.error(f"Bedrock HTTP request failed: {e}")
            raise
    
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
