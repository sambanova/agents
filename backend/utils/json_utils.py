import json
import re
from typing import Optional, Union, Dict, Any

def extract_json_from_string(content: str, get_last: bool = True) -> Optional[Dict[str, Any]]:
    """
    Attempts to extract and parse a JSON object from a string that may contain markdown,
    explanatory text, or code blocks.
    
    Args:
        content (str): The input string that may contain a JSON object
        get_last (bool): If True, returns the last valid JSON found; if False, returns the first one
        
    Returns:
        Optional[Dict[str, Any]]: The parsed JSON object if found and valid, None otherwise
        
    """
    if not isinstance(content, str):
        return None
        
    # Clean the input string
    content = content.strip()
    
    # Try to find JSON in code blocks first
    code_block_pattern = r"```(?:json)?\s*({[\s\S]*?})\s*```"
    code_blocks = re.findall(code_block_pattern, content)
    
    # Process code blocks based on get_last parameter
    if code_blocks:
        blocks_to_try = [code_blocks[-1]] if get_last else [code_blocks[0]]
        for block in blocks_to_try:
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                pass
    
    # If no valid JSON in code blocks, try to find any {...} pattern
    # Using a more precise pattern that matches balanced braces
    def find_json_objects(s: str) -> list[str]:
        objects = []
        stack = []
        start = -1
        
        for i, char in enumerate(s):
            if char == '{':
                if not stack:
                    start = i
                stack.append(char)
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack and start != -1:
                        objects.append(s[start:i+1])
                        start = -1
        
        return objects
    
    # Find all potential JSON objects with balanced braces
    matches = find_json_objects(content)
    
    # Try each potential JSON match based on get_last parameter
    if matches:
        matches_to_try = [matches[-1]] if get_last else [matches[0]]
        for match in matches_to_try:
            try:
                # Clean the match by removing markdown code block syntax
                cleaned = match.replace("```json", "").replace("```", "").strip()
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue
            
    # If the entire content looks like a JSON object, try that
    if content.startswith("{") and content.endswith("}"):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
            
    return None 