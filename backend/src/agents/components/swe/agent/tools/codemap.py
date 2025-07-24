from typing import Optional

from langchain_core.tools import tool
from tree_sitter_languages import get_language, get_parser

@tool(parse_docstring=True)
def get_code_definitions(file_path: str) -> str:
    """
    Extract function and class definitions from a file.
    Shows signatures with their actual source file line numbers and ... between definitions.

    Args:
        file_path: Path to the source file to analyze
    """
    # Determine language
    suffix = file_path.split(".")[-1]
    lang_map = {
        "py": "python",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "typescript"
    }
    lang = lang_map.get(suffix)
    if not lang:
        return f"Unsupported file type: {suffix}"

    # Initialize parser
    language = get_language(lang)
    parser = get_parser(lang)

    # Read file content
    with open(file_path, "rb") as f:
        code = f.read()
    tree = parser.parse(code)

    # Define query for functions and classes
    query_str = """
    (class_definition
        name: (identifier) @name.definition.class
        body: (block 
            (function_definition
                name: (identifier) @name.definition.method
                parameters: (parameters) @params.definition.method)?) @body.definition.class)

    (function_definition
        name: (identifier) @name.definition.function
        parameters: (parameters) @params.definition.function
        body: (block) @body.definition.function)
    """

    query = language.query(query_str)
    captures = query.captures(tree.root_node)

    # Process captures to extract definitions
    output_lines = [f"\n{file_path}:\n"]
    current_def = {}
    in_class = False
    last_line_number = 0
    
    for node, tag in captures:
        current_line = node.start_point[0] + 1
        
        # Add ... between definitions if there's a gap
        if last_line_number > 0 and current_line > last_line_number + 1:
            output_lines.append("...")

        if tag == "name.definition.class":
            in_class = True
            output_lines.append(f"{current_line}| class {node.text.decode('utf-8')}:")
            last_line_number = current_line
        elif tag == "name.definition.method" and in_class:
            method_name = node.text.decode('utf-8')
            current_def['method_name'] = method_name
            current_def['line'] = current_line
        elif tag == "params.definition.method" and in_class:
            params = node.text.decode('utf-8')
            line_num = current_def['line']
            output_lines.append(f"{line_num}|     def {current_def['method_name']}{params}:")
            last_line_number = line_num
        elif tag == "body.definition.method":
            line_num = node.start_point[0] + 1
            output_lines.append(f"{line_num}|         ...")
            last_line_number = line_num
        elif tag == "body.definition.class":
            in_class = False
        elif tag == "name.definition.function":
            current_def['name'] = node.text.decode('utf-8')
            current_def['line'] = current_line
        elif tag == "params.definition.function":
            params = node.text.decode('utf-8')
            line_num = current_def['line']
            output_lines.append(f"{line_num}| def {current_def['name']}{params}:")
            last_line_number = line_num
        elif tag == "body.definition.function":
            line_num = node.start_point[0] + 1
            output_lines.append(f"{line_num}|     ...")
            last_line_number = line_num

    return "\n".join(output_lines)

@tool(parse_docstring=True)
def get_function_implementation(file_path: str, function_name: str) -> Optional[str]:
    """
    Extract the implementation of a specific function or method from a file.

    Args:
        file_path: Path to the source file
        function_name: Name of the function to find
    """
    # Determine language
    suffix = file_path.split(".")[-1]
    lang_map = {
        "py": "python",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "typescript"
    }
    lang = lang_map.get(suffix)
    if not lang:
        return None

    # Initialize parser
    language = get_language(lang)
    parser = get_parser(lang)

    # Read file content
    with open(file_path, "rb") as f:
        code = f.read()
    tree = parser.parse(code)

    # Define query for functions and methods
    query_str = """
    (function_definition
        name: (identifier) @name.function
        parameters: (parameters) @params.function
        body: (block) @body.function)

    (class_definition
        body: (block 
            (function_definition
                name: (identifier) @name.method
                parameters: (parameters) @params.method
                body: (block) @body.method)))
    """

    query = language.query(query_str)
    captures = query.captures(tree.root_node)

    # Find the specific function
    current_def = {}
    for node, tag in captures:
        if tag in ["name.function", "name.method"]:
            if node.text.decode('utf-8') == function_name:
                current_def['name'] = node.text.decode('utf-8')
                current_def['line'] = node.start_point[0] + 1
        elif tag in ["params.function", "params.method"] and current_def.get('name') == function_name:
            current_def['params'] = node.text.decode('utf-8')
        elif tag in ["body.function", "body.method"] and current_def.get('name') == function_name:
            # Extract the full implementation
            implementation = code[node.start_byte:node.end_byte].decode('utf-8')
            lines = implementation.split('\n')
            
            # Format output
            output_lines = [f"\n{file_path}:\n"]
            start_line = current_def['line']
            
            # Add function signature
            output_lines.append(f"{start_line}| def {current_def['name']}{current_def['params']}:")
            
            # Add implementation lines with correct line numbers
            for i, line in enumerate(lines):
                line_num = start_line + i + 1
                # Handle indentation
                indent = '    ' if not line.strip() else line[:len(line) - len(line.lstrip())]
                output_lines.append(f"{line_num}|{indent}{line.lstrip()}")
            
            return "\n".join(output_lines)

    return None

@tool(parse_docstring=True)
def get_code_definitions_multi(file_paths: list[str]) -> str:
    """
    Extract function and class definitions from multiple files.
    Shows signatures with their actual source file line numbers and ... between definitions.
    
    Args:
        file_paths: List of file paths to analyze
     """
    all_definitions = []
    
    for file_path in file_paths:
        definitions = get_code_definitions(file_path)
        if definitions and not definitions.startswith("Unsupported"):
            all_definitions.append(definitions)
    
    return "\n".join(all_definitions)

@tool(parse_docstring=True)
def get_raw_file_content(file_path: str) -> str:
    """
    Get the raw content of the file. good for a non-code files
    
    Args:
        file_path: file path to read
     """
    with open(file_path, "rb") as f:
        return f.read().decode('utf-8')

# List of available tools
codemap_tools = [get_code_definitions, get_function_implementation, get_code_definitions_multi, get_raw_file_content]
codemap_tools_map = {tool.name: tool for tool in codemap_tools}

def main():
    # Example usage
    file_path = "../../agent/tools/codemap.py"  # Using this file as an example
    code_map = get_code_definitions.invoke({"file_path":file_path})
    print(code_map)

    # Get specific function implementation
    implementation = get_function_implementation.invoke({"file_path":file_path, "function_name":"get_code_definitions"})
    print(implementation)
    
    # Example of multi-file definitions
    files = ["../../agent/tools/codemap.py", "../../agent/tools/search.py"]
    multi_defs = get_code_definitions_multi.invoke({"file_paths":files})
    print(multi_defs)

if __name__ == "__main__":
    main()



