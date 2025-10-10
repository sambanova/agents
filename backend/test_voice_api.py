#!/usr/bin/env python3
"""
Quick test script for voice API endpoints.
This tests the Hume AI voice integration.
"""
import asyncio
import os
from agents.services.voice_service import HumeVoiceService
from agents.storage.redis_service import SecureRedisService
from dotenv import load_dotenv

load_dotenv()

async def test_voice_service():
    """Test the voice service can generate tokens."""
    print("Testing Hume Voice Service...")
    print("=" * 50)

    # Initialize Redis (needed for voice service)
    redis_client = SecureRedisService()

    # Initialize voice service
    voice_service = HumeVoiceService(redis_client)

    # Check if credentials are configured
    print(f"API Key configured: {bool(voice_service.api_key)}")
    print(f"Secret Key configured: {bool(voice_service.secret_key)}")
    print()

    if not voice_service.api_key or not voice_service.secret_key:
        print("❌ Hume credentials not configured!")
        print("Please set HUME_API_KEY and HUME_SECRET_KEY in .env")
        return

    # Test token generation
    print("Testing token generation...")
    try:
        token_data = await voice_service.generate_access_token()

        if token_data:
            print("✅ Token generated successfully!")
            print(f"Access Token (first 20 chars): {token_data['access_token'][:20]}...")
            print(f"Expires in: {token_data['expires_in']} seconds")
        else:
            print("❌ Failed to generate token")
    except Exception as e:
        print(f"❌ Error generating token: {str(e)}")

    print()

    # Test user context generation
    print("Testing user context generation...")
    try:
        test_user_id = "test_user_123"
        test_conversation_id = "conv_456"

        context = await voice_service.get_user_context(test_user_id, test_conversation_id)

        print("✅ User context generated successfully!")
        print(f"System prompt length: {len(context['system_prompt'])} chars")
        print(f"Context length: {len(context['context'])} chars")
        print(f"Variables: {context['variables']}")
    except Exception as e:
        print(f"❌ Error generating context: {str(e)}")

    print()

    # Test session settings
    print("Testing session settings...")
    try:
        session_settings = voice_service.get_session_settings(
            system_prompt="Test system prompt",
            context="Test context",
            variables={"user_id": "123"},
            voice_name="ITO"
        )

        print("✅ Session settings generated successfully!")
        print(f"Voice: {session_settings['voice']['name']}")
        print(f"Audio encoding: {session_settings['audio']['encoding']}")
        print(f"Sample rate: {session_settings['audio']['sample_rate']}")
    except Exception as e:
        print(f"❌ Error generating session settings: {str(e)}")

    print()
    print("=" * 50)
    print("Voice service tests complete!")

if __name__ == "__main__":
    asyncio.run(test_voice_service())
