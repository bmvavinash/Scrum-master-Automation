"""Test endpoint to verify Bedrock configuration in the server context."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
import logging

from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bedrock-test", tags=["bedrock-test"])

llm_service = LLMService()


class TestRequest(BaseModel):
    prompt: str = "Say 'Hello' in one word."


@router.get("/status")
async def bedrock_status():
    """Check Bedrock configuration status."""
    return {
        "bedrock_client": "INITIALIZED" if llm_service.bedrock_client else "NOT INITIALIZED",
        "bedrock_bearer_token": "SET" if llm_service.bedrock_bearer_token else "NOT SET",
        "provider_priority": llm_service._get_provider_priority()
    }


@router.post("/test")
async def test_bedrock(request: TestRequest):
    """Test Bedrock with a simple prompt."""
    try:
        response = await llm_service._invoke_bedrock(request.prompt)
        return {
            "success": True,
            "response": response,
            "bedrock_client": "INITIALIZED" if llm_service.bedrock_client else "NOT INITIALIZED",
            "bedrock_bearer_token": "SET" if llm_service.bedrock_bearer_token else "NOT SET"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "bedrock_client": "INITIALIZED" if llm_service.bedrock_client else "NOT INITIALIZED",
            "bedrock_bearer_token": "SET" if llm_service.bedrock_bearer_token else "NOT SET"
        }


@router.post("/test-code-generation")
async def test_code_generation():
    """Test full code generation workflow."""
    try:
        description = "Create a simple hello world endpoint"
        context = {"language": "python", "framework": "fastapi"}
        
        result, provider = await llm_service.generate_code_with_fallback(
            description=description,
            context=context
        )
        
        return {
            "success": True,
            "provider": provider,
            "code_files": len(result.get("code", [])),
            "bedrock_client": "INITIALIZED" if llm_service.bedrock_client else "NOT INITIALIZED",
            "bedrock_bearer_token": "SET" if llm_service.bedrock_bearer_token else "NOT SET"
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "bedrock_client": "INITIALIZED" if llm_service.bedrock_client else "NOT INITIALIZED",
            "bedrock_bearer_token": "SET" if llm_service.bedrock_bearer_token else "NOT SET"
        }


