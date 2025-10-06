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
