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
        """Find the complete JSON object by counting braces, skipping string literals."""
        start = text.find('{')
        if start == -1:
            return None

        count = 1
        pos = start + 1
        in_string = False
        escape_next = False

        while count > 0 and pos < len(text):
            char = text[pos]
            if escape_next:
                escape_next = False
            elif char == '\\':
                escape_next = True
            elif char == '"':
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    count += 1
                elif char == '}':
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

    # Try full first-to-last brace span first, repairing extra } if needed
    first_brace_early = content_string.find('{')
    last_brace_early = content_string.rfind('}')
    if first_brace_early != -1 and last_brace_early != -1 and last_brace_early > first_brace_early:
        full_span = content_string[first_brace_early:last_brace_early+1]
        try:
            return json.loads(full_span)
        except json.JSONDecodeError as e:
            if 'Extra data' in e.msg and e.pos > 0:
                # Remove the } just before the extra data position
                fix_pos = e.pos - 1
                if full_span[fix_pos] == '}':
                    fixed = full_span[:fix_pos] + full_span[fix_pos+1:]
                    result = try_parse_json(fixed)
                    if result:
                        return result

    # Look for JSON objects
    complete_json = find_complete_json(content_string)
    if complete_json:
        result = try_parse_json(complete_json)
        if result:
            return result

    # Try to repair JSON with extra closing brace (common with reasoning models)
    # Pattern: {"key1":...,"stock_price_data":[...]},"news":{...}}
    # The LLM closes the root object too early, then continues with more fields
    first_brace = content_string.find('{')
    last_brace = content_string.rfind('}')

    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        json_text = content_string[first_brace:last_brace+1]

        # Try parsing the full span - if it fails with "Extra data",
        # there's an extra } that prematurely closes the root object
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            if 'Extra data' in str(e) and e.pos > 0:
                # Remove the extra } at the error position and retry
                fixed = json_text[:e.pos] + json_text[e.pos+1:]
                result = try_parse_json(fixed)
                if result:
                    return result

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