import json
from crewai.utilities.converter import Converter, ConverterError
from pydantic import ValidationError
import re
import json
import json5

def parse_json_string(content_string):
    """
    A robust, generic function to extract and parse JSON from problematic strings.
    
    Args:
        content_string: The string containing the JSON data, possibly with surrounding text
                        or formatting markers.
    
    Returns:
        The parsed JSON data as a Python dictionary/list, or None if parsing fails.
    """
    if not content_string:
        return None
    
    def find_complete_json(text):
        """Find the complete JSON object by counting braces."""
        start = text.find('{')
        if start == -1:
            return None
        
        count = 1
        pos = start + 1
        
        while count > 0 and pos < len(text):
            if text[pos] == '{':
                count += 1
            elif text[pos] == '}':
                count -= 1
            pos += 1
        
        if count == 0:
            return text[start:pos].strip()
        return None
    
    def try_parse_json(text):
        """Try to parse JSON using both json5 and json."""
        try:
            return json5.loads(text)
        except:
            try:
                return json.loads(text)
            except:
                return None
    
    # Try direct parsing first
    try:
        return json.loads(content_string)
    except:
        pass
    
    # Remove surrounding quotes if present
    if content_string.startswith("'") and content_string.endswith("'"):
        content_string = content_string[1:-1]
    elif content_string.startswith('"') and content_string.endswith('"'):
        content_string = content_string[1:-1]
    
    # Extract JSON from code blocks if present
    code_block_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n\s*```', content_string)
    if code_block_match:
        complete_json = find_complete_json(code_block_match.group(1))
        if complete_json:
            result = try_parse_json(complete_json)
            if result:
                return result
    
    # Look for JSON objects
    complete_json = find_complete_json(content_string)
    if complete_json:
        result = try_parse_json(complete_json)
        if result:
            return result
    
    # If we've tried everything and still failed, apply aggressive cleaning
    first_brace = content_string.find('{')
    last_brace = content_string.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        json_text = content_string[first_brace:last_brace+1]
        complete_json = find_complete_json(json_text)
        if complete_json:
            result = try_parse_json(complete_json)
            if result:
                return result
            
            # One final attempt with manual fixes for common issues
            try:
                fixed_text = re.sub(r':\s*([a-zA-Z][a-zA-Z0-9_]*)\s*([,}])', r': "\1"\2', complete_json)
                return json5.loads(fixed_text)
            except:
                pass
    
    return None


class CustomConverter(Converter):
    """Class that converts text into either pydantic or json."""

    def to_pydantic(self, current_attempt=1):
        """Convert text to pydantic."""
        try:
            response = self.llm.call(
                [
                    {"role": "system", "content": self.instructions},
                    {"role": "user", "content": self.text},
                ]
            )
            return self.model.model_validate(parse_json_string(response))
        except ValidationError as e:
            if current_attempt < self.max_attempts:
                return self.to_pydantic(current_attempt + 1)
            raise ConverterError(
                f"Failed to convert text into a Pydantic model due to the following validation error: {e}"
            )
        except Exception as e:
            if current_attempt < self.max_attempts:
                return self.to_pydantic(current_attempt + 1)
            raise ConverterError(
                f"Failed to convert text into a Pydantic model due to the following error: {e}"
            )

    def to_json(self, current_attempt=1):
        """Convert text to json."""
        try:
            return json.dumps(
                self.llm.call(
                    [
                        {"role": "system", "content": self.instructions},
                        {"role": "user", "content": self.text},
                    ]
                )
            )
        except Exception as e:
            if current_attempt < self.max_attempts:
                return self.to_json(current_attempt + 1)
            return ConverterError(f"Failed to convert text into JSON, error: {e}.")