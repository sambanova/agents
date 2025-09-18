import httpx
import json
import os

# Test the gpt-oss-120b API call structure
api_key = os.getenv("SAMBANOVA_API_KEY", "test-key")

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello, just testing. Reply with a simple greeting."}
]

print("Testing gpt-oss-120b API call...")
print(f"API Key present: {bool(api_key and api_key != 'test-key')}")
print(f"Request payload:")
print(json.dumps({
    "model": "gpt-oss-120b",
    "messages": messages,
    "stream": False,
    "max_tokens": 100,
    "temperature": 0
}, indent=2))

if api_key and api_key != "test-key":
    # Make actual call
    client = httpx.Client(timeout=30.0)
    response = client.post(
        "https://api.sambanova.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-oss-120b",
            "messages": messages,
            "stream": False,
            "max_tokens": 100,
            "temperature": 0
        }
    )
    
    print(f"\nResponse status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Response structure:")
        print(json.dumps(result, indent=2))
        
        # Check content extraction
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0].get("message", {}).get("content")
            print(f"\nExtracted content: {content}")
            print(f"Content type: {type(content)}")
    else:
        print(f"Error response: {response.text}")
else:
    print("\nNo API key found - set SAMBANOVA_API_KEY environment variable to test")
