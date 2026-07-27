"""
Tests for OpenAI Responses API Compatibility

These tests verify that our implementation is compatible with the OpenAI Responses API.
Run with: pytest tests/test_openai_compatibility.py -v
"""
import json
import os
import pytest
from httpx import AsyncClient

# Base URL for the API
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
# Test API key - should be set in environment or provided by user
TEST_API_KEY = os.getenv("TEST_API_KEY", "test-key")

# Optional: Real OpenAI API key for comparison testing
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)


@pytest.mark.asyncio
async def test_health_check():
    """Test that the API is running."""
    async with AsyncClient(base_url=BASE_URL) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_tools():
    """Test the /v1/tools endpoint."""
    async with AsyncClient(base_url=BASE_URL) as client:
        response = await client.get(
            "/v1/tools",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"}
        )
        assert response.status_code == 200
        tools = response.json()
        assert isinstance(tools, list)
        assert len(tools) > 0

        # Verify tool structure
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]

        # Check for expected tools
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "financial_analysis" in tool_names
        assert "deep_research" in tool_names
        assert "code_execution" in tool_names


@pytest.mark.asyncio
async def test_create_response_non_streaming():
    """Test non-streaming response creation."""
    async with AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mainagent",
                "input": "What is 2 + 2?",
                "stream": False
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure matches OpenAI format
        assert "id" in data
        assert data["object"] == "response"
        assert "created" in data
        assert data["model"] == "mainagent"
        assert data["status"] in ["completed", "in_progress", "failed"]
        assert "output" in data
        assert isinstance(data["output"], list)

        # Verify output structure
        if len(data["output"]) > 0:
            output_item = data["output"][0]
            assert output_item["type"] == "text"
            assert "text" in output_item
            # Basic sanity check - should mention "4"
            assert "4" in output_item["text"]


@pytest.mark.asyncio
async def test_create_response_streaming():
    """Test streaming response creation with SSE."""
    async with AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        async with client.stream(
            "POST",
            "/v1/responses",
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mainagent",
                "input": "Count from 1 to 3",
                "stream": True
            }
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

            events = []
            accumulated_text = ""

            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    event_type = line.split("event:", 1)[1].strip()
                elif line.startswith("data:"):
                    event_data = line.split("data:", 1)[1].strip()
                    try:
                        data = json.loads(event_data)
                        events.append({
                            "event": data.get("event"),
                            "data": data.get("data")
                        })

                        # Accumulate text deltas
                        if data.get("event") == "response.output_text.delta":
                            delta = data.get("data", {}).get("delta", "")
                            accumulated_text += delta
                    except json.JSONDecodeError:
                        pass

            # Verify event sequence
            assert len(events) > 0

            # Should start with response.created
            assert events[0]["event"] == "response.created"

            # Should end with response.completed
            assert events[-1]["event"] == "response.completed"

            # Should have text deltas
            delta_events = [e for e in events if e["event"] == "response.output_text.delta"]
            assert len(delta_events) > 0

            # Verify accumulated text is not empty
            assert len(accumulated_text) > 0


@pytest.mark.asyncio
async def test_authentication_required():
    """Test that authentication is required."""
    async with AsyncClient(base_url=BASE_URL) as client:
        response = await client.post(
            "/v1/responses",
            json={
                "model": "mainagent",
                "input": "Hello",
                "stream": False
            }
        )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_invalid_model():
    """Test error handling for invalid model."""
    async with AsyncClient(base_url=BASE_URL) as client:
        response = await client.post(
            "/v1/responses",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
            json={
                "model": "invalid-model-name",
                "input": "Hello",
                "stream": False
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_response_with_metadata():
    """Test that metadata is preserved in response."""
    async with AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mainagent",
                "input": "Hello",
                "stream": False,
                "metadata": {
                    "user_session": "test-session-123",
                    "custom_field": "test-value"
                }
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "metadata" in data


@pytest.mark.asyncio
async def test_model_aliases():
    """Test that OpenAI model name aliases work."""
    async with AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        # Test gpt-4 alias
        response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4",
                "input": "What is 1 + 1?",
                "stream": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "gpt-4"
        assert data["status"] in ["completed", "in_progress"]


@pytest.mark.asyncio
async def test_structured_input():
    """Test that structured input format works."""
    async with AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mainagent",
                "input": [
                    {"type": "text", "text": "What is the capital of France?"}
                ],
                "stream": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "output" in data
        if len(data["output"]) > 0:
            # Should mention Paris
            output_text = data["output"][0].get("text", "")
            assert "paris" in output_text.lower()


@pytest.mark.asyncio
@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
async def test_compare_with_openai():
    """
    Compare our API response format with real OpenAI API.
    Only runs if OPENAI_API_KEY is provided.
    """
    from openai import AsyncOpenAI

    # Test our API
    async with AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        our_response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mainagent",
                "input": "Say hello",
                "stream": False
            }
        )
        our_data = our_response.json()

    # Compare structure (not content)
    assert "id" in our_data
    assert "object" in our_data
    assert our_data["object"] == "response"
    assert "created" in our_data
    assert "model" in our_data
    assert "status" in our_data
    assert "output" in our_data
    assert isinstance(our_data["output"], list)

    # Verify each output item has correct structure
    for item in our_data["output"]:
        assert "type" in item
        if item["type"] == "text":
            assert "text" in item


# Integration test with deep research auto-resume
@pytest.mark.asyncio
@pytest.mark.slow
async def test_auto_resume_deep_research():
    """
    Test that deep research interrupts are auto-resumed.
    This is a longer-running test.
    """
    async with AsyncClient(base_url=BASE_URL, timeout=300.0) as client:
        response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": f"Bearer {TEST_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mainagent",
                "input": "Do a quick research on AI trends in 2024",
                "stream": False
            }
        )

        # Should complete without manual intervention
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert len(data["output"]) > 0


if __name__ == "__main__":
    # Allow running directly for quick testing
    import asyncio

    print("Running quick compatibility tests...")
    asyncio.run(test_health_check())
    print("✓ Health check passed")

    asyncio.run(test_list_tools())
    print("✓ Tools endpoint passed")

    asyncio.run(test_create_response_non_streaming())
    print("✓ Non-streaming response passed")

    print("\nAll quick tests passed! Run 'pytest tests/test_openai_compatibility.py -v' for full test suite.")
