#!/usr/bin/env python3
"""Simple test script to verify the setup."""

import asyncio
import sys
from app.config import get_settings
from app.database import connect_to_mongo, close_mongo_connection
from app.services.llm_service import LLMService
from app.services.jira_service import JiraService
from app.services.git_service import GitService
from app.services.code_intelligence_service import CodeIntelligenceService

async def test_services():
    """Test all services to ensure they're working correctly."""
    
    print("🧪 Testing Scrum Automation Backend Setup...")
    print("=" * 50)
    
    # Test configuration
    print("1. Testing configuration...")
    try:
        settings = get_settings()
        print(f"   ✅ Configuration loaded successfully")
        print(f"   📊 Environment: {settings.environment}")
        print(f"   🐛 Debug mode: {settings.debug}")
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
        return False
    
    # Test database connection
    print("\n2. Testing database connection...")
    try:
        await connect_to_mongo()
        print("   ✅ Database connected successfully")
    except Exception as e:
        print(f"   ❌ Database connection error: {e}")
        return False
    
    # Test LLM service
    print("\n3. Testing LLM service...")
    try:
        llm_service = LLMService()
        print("   ✅ LLM service initialized successfully")
    except Exception as e:
        print(f"   ❌ LLM service error: {e}")
        print("   ⚠️  Note: This might be due to missing AWS credentials")
    
    # Test Jira service
    print("\n4. Testing Jira service...")
    try:
        jira_service = JiraService()
        if jira_service.jira_client:
            print("   ✅ Jira service initialized successfully")
        else:
            print("   ⚠️  Jira service initialized but not connected (missing credentials)")
    except Exception as e:
        print(f"   ❌ Jira service error: {e}")
        print("   ⚠️  Note: This might be due to missing Jira credentials")
    
    # Test Git service
    print("\n5. Testing Git service...")
    try:
        git_service = GitService()
        if git_service.github_client:
            print("   ✅ Git service initialized successfully")
        else:
            print("   ⚠️  Git service initialized but not connected (missing credentials)")
    except Exception as e:
        print(f"   ❌ Git service error: {e}")
        print("   ⚠️  Note: This might be due to missing GitHub credentials")
    
    # Test Code Intelligence service
    print("\n6. Testing Code Intelligence service...")
    try:
        code_service = CodeIntelligenceService()
        print("   ✅ Code Intelligence service initialized successfully")
    except Exception as e:
        print(f"   ❌ Code Intelligence service error: {e}")
    
    # Test database collections
    print("\n7. Testing database collections...")
    try:
        from app.database import get_database
        db = get_database()
        
        # List collections
        collections = await db.list_collection_names()
        print(f"   ✅ Found {len(collections)} collections:")
        for collection in collections:
            print(f"      - {collection}")
    except Exception as e:
        print(f"   ❌ Database collections error: {e}")
    
    # Close database connection
    await close_mongo_connection()
    
    print("\n" + "=" * 50)
    print("🎉 Setup test completed!")
    print("\n📝 Next steps:")
    print("   1. Configure your .env file with proper credentials")
    print("   2. Run: python -m app.main")
    print("   3. Visit: http://localhost:8000/docs")
    print("   4. Test the Teams bot integration")
    
    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_services())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Unexpected error: {e}")
        sys.exit(1)
