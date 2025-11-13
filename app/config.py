"""Configuration management for the Scrum Automation application."""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # MongoDB Configuration
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "scrum_automation"
    
    # Jira Configuration
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    
    # Microsoft Teams Bot Configuration
    teams_app_id: str = ""
    teams_app_password: str = ""
    teams_tenant_id: str = ""
    
    # AWS Bedrock Configuration
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    
    # GitHub Configuration
    github_token: str = ""
    github_webhook_secret: str = ""
    github_repo_owner: str = ""  # Repository owner (e.g., "username" or "org")
    github_repo_name: str = ""  # Repository name
    github_repo_path: str = ""  # Local path to clone repository (optional)
    github_base_branch: str = "main"  # Base branch for creating feature branches
    
    # LLM Configuration (Agentic Code Generation)
    cursor_api_key: str = ""  # Cursor API key (optional)
    cursor_api_url: str = "https://api.cursor.sh"  # Cursor API URL
    amazon_q_app_id: str = ""  # Amazon Q Developer App ID (optional)
    llm_provider_priority: str = "bedrock,cursor,amazon_q"  # Comma-separated priority order
    max_llm_retries: int = 3  # Maximum retries per LLM provider
    llm_timeout_seconds: int = 300  # Timeout for LLM requests
    
    # Agentic Workflow Configuration
    agentic_enabled: bool = True  # Enable agentic code generation
    agentic_auto_create_pr: bool = False  # Auto-create PR (configurable per ticket)
    agentic_auto_merge: bool = False  # Auto-merge PR (never recommended, but configurable)
    agentic_branch_prefix: str = "feature"  # Branch prefix (e.g., "feature", "bugfix")
    agentic_max_iterations: int = 5  # Maximum iterations to fix code (prevent infinite loops)
    agentic_test_timeout: int = 300  # Test execution timeout in seconds
    
    # Code Generation Configuration
    codegen_follow_style: bool = True  # Follow existing code style
    codegen_add_tests: bool = True  # Generate tests from acceptance criteria
    codegen_run_tests: bool = True  # Run tests after code generation
    codegen_validate_syntax: bool = True  # Validate syntax before commit
    codegen_run_linters: bool = True  # Run linters before commit
    
    # AWS Bedrock Bearer Token (alternative authentication)
    aws_bearer_token_bedrock: str = ""  # Bearer token for Bedrock API
    
    # Application Configuration
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    # API Configuration
    api_v1_prefix: str = "/api/v1"
    
    # Security / Networking
    allowed_hosts: str = "*"  # Comma-separated, e.g. "example.com,ec2-52-21-62-175.compute-1.amazonaws.com,localhost"
    cors_origins: str = "*"   # Comma-separated origins or "*"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
