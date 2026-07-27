import unittest
from backend.utils.json_utils import extract_json_from_string

class TestJsonUtils(unittest.TestCase):
    def test_extract_json_from_markdown_text(self):
        test_input = '''Based on the provided rules and the user query "get me the latest news on ukrain", I will classify the query and extract parameters.

**Classification:** assistant

**Parameters:**

{
  "type": "assistant",
  "parameters": {
    "query": "get me the latest news on Tesla"
  }
}

Note: The query is classified as "assistant" because it is a general query that does not fit into other specific categories.'''

        expected_output = {
            "type": "assistant",
            "parameters": {
                "query": "get me the latest news on ukrain"
            }
        }
        
        result = extract_json_from_string(test_input)
        self.assertEqual(result, expected_output)
        
    def test_extract_json_from_code_block(self):
        test_input = '''Here's the JSON:
        ```json
        {
            "type": "test",
            "value": 123
        }
        ```
        End of JSON'''
        
        expected_output = {
            "type": "test",
            "value": 123
        }
        
        result = extract_json_from_string(test_input)
        self.assertEqual(result, expected_output)
        
    def test_invalid_input(self):
        # Test non-string input
        self.assertIsNone(extract_json_from_string(None))
        
        # Test string without JSON
        self.assertIsNone(extract_json_from_string("No JSON here"))
        
        # Test invalid JSON
        self.assertIsNone(extract_json_from_string("{invalid json}"))

if __name__ == '__main__':
    unittest.main() 