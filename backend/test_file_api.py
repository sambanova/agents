import asyncio
import requests
from src.utils.file_storage import put_file, file_metadata

async def test_file_api():
    print("Testing file API...")
    
    # Create a test file
    test_file_id = "test-123"
    test_content = b"Hello, this is a test image!"
    
    # Store the file
    await put_file("test_user", test_file_id, data=test_content, title="test.png", format="png")
    print(f"✓ File stored with ID: {test_file_id}")
    print(f"✓ File metadata: {file_metadata.get(test_file_id)}")
    
    # Test the API endpoint (assuming server is running on localhost:8000)
    try:
        response = requests.get(f"http://localhost:8000/api/files/{test_file_id}")
        print(f"✓ API Response status: {response.status_code}")
        if response.status_code == 200:
            print(f"✓ API Response content type: {response.headers.get('content-type')}")
            print(f"✓ API Response content length: {len(response.content)}")
        else:
            print(f"✗ API Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("⚠️  Could not connect to server - make sure backend is running on localhost:8000")
    except Exception as e:
        print(f"✗ API Test error: {e}")

if __name__ == "__main__":
    asyncio.run(test_file_api()) 