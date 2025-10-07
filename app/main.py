"""Main FastAPI application for Scrum Automation."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from contextlib import asynccontextmanager

from app.config import get_settings
from app.database import connect_to_mongo, close_mongo_connection
from app.routers import meetings, jira, git, velocity, code_intelligence, chats, teams_bot, git_hooks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Scrum Automation API...")
    await connect_to_mongo()
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Scrum Automation API...")
    await close_mongo_connection()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Scrum Automation API",
    description="AI-powered scrum automation with Jira, Teams, and Git integration",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Add middleware
allowed_origins = (
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.cors_origins and settings.cors_origins != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

allowed_hosts = (
    [h.strip() for h in settings.allowed_hosts.split(",") if h.strip()]
    if settings.allowed_hosts and settings.allowed_hosts != "*"
    else ["*"]
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error"
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Scrum Automation API",
        "version": "1.0.0",
        "docs": "/docs" if settings.debug else "Documentation not available in production",
        "health": "/health"
    }


# Include routers
app.include_router(meetings.router, prefix=settings.api_v1_prefix)
app.include_router(jira.router, prefix=settings.api_v1_prefix)
app.include_router(git.router, prefix=settings.api_v1_prefix)
app.include_router(velocity.router, prefix=settings.api_v1_prefix)
app.include_router(code_intelligence.router, prefix=settings.api_v1_prefix)
app.include_router(chats.router, prefix=settings.api_v1_prefix)
app.include_router(git_hooks.router, prefix=settings.api_v1_prefix)
app.include_router(teams_bot.router)


# Additional utility endpoints
@app.get(f"{settings.api_v1_prefix}/status")
async def get_api_status():
    """Get API status and configuration."""
    return {
        "api_version": "v1",
        "environment": settings.environment,
        "debug": settings.debug,
        "features": {
            "jira_integration": bool(settings.jira_url and settings.jira_email and settings.jira_api_token),
            "teams_bot": bool(settings.teams_app_id and settings.teams_app_password),
            "git_integration": bool(settings.github_token),
            "llm_service": bool(settings.aws_access_key_id and settings.aws_secret_access_key),
            "code_intelligence": True
        },
        "endpoints": {
            "meetings": f"{settings.api_v1_prefix}/meetings",
            "jira": f"{settings.api_v1_prefix}/jira",
            "git": f"{settings.api_v1_prefix}/git",
            "git_hooks": f"{settings.api_v1_prefix}/git-hooks",
            "velocity": f"{settings.api_v1_prefix}/velocity",
            "code_intelligence": f"{settings.api_v1_prefix}/code-intelligence",
            "chats": f"{settings.api_v1_prefix}/chats"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
