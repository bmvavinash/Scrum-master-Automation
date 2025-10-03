"""Database connection and configuration."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

class Database:
    """Database connection manager."""
    
    client: AsyncIOMotorClient = None
    database: AsyncIOMotorDatabase = None


db = Database()


async def connect_to_mongo():
    """Create database connection."""
    settings = get_settings()
    
    try:
        db.client = AsyncIOMotorClient(settings.mongodb_url)
        db.database = db.client[settings.mongodb_database]
        
        # Test the connection
        await db.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        
    except Exception as e:
        logger.warning(f"Failed to connect to MongoDB: {e}")
        logger.warning("Running without database - some features may not work")
        # Don't raise in development mode to allow testing without MongoDB
        if settings.environment == "production":
            raise


async def close_mongo_connection():
    """Close database connection."""
    if db.client:
        db.client.close()
        logger.info("Disconnected from MongoDB")


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance."""
    return db.database
