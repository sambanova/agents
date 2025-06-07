import asyncio
from src.utils.file_storage import put_file, get_file_data_url

async def test():
    print("Testing file storage...")
    
    # Test storing a simple file
    await put_file('test_user', 'test_id', data=b'Hello World!', title='test.txt', format='txt')
    print("✓ File stored successfully")
    
    # Test retrieving as data URL
    url = await get_file_data_url('test_user', 'test_id')
    print(f"✓ Data URL retrieved: {url[:100]}...")
    
    print("File storage test passed!")

if __name__ == "__main__":
    asyncio.run(test()) 