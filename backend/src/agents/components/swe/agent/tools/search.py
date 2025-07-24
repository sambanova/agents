import os
import re

from langchain_core.tools import tool


def search_in_file(file_path, search_term, context=2):
    """
    Search for search_term (case-insensitive) in a given file.
    Returns a list of tuples (line_number, snippet_lines, file_path) for each match,
    where snippet_lines is a list of (line_number, line) tuples that includes
    context lines before and after the matched line.
    """
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Could not read {file_path}: {e}")
        return results

    # Get absolute path
    abs_path = os.path.abspath(file_path)

    # compile a case-insensitive regex pattern for the search term
    pattern = re.compile(re.escape(search_term), re.IGNORECASE)

    matches_found = False
    for i, line in enumerate(lines):
        if pattern.search(line):
            matches_found = True
            # Determine the snippet range: include 'context' lines before and after
            start = max(i - context, 0)
            end = min(i + context + 1, len(lines))
            snippet = [(j+1, lines[j].rstrip('\n')) for j in range(start, end)]
            results.append((i+1, snippet, abs_path))  # i+1 for the matching line number
    
    return results

def search_directory(directory, search_term, extension=None, context=2):
    """
    Recursively search through files in a given directory for the search_term.
    Only searches files with the specified extension if provided.
    
    Args:
        directory (str): Directory path to search
        search_term (str): Term to search for
        extension (str, optional): File extension to filter by (e.g., '.py', '.txt')
        context (int): Number of context lines to include before and after match
        
    Returns:
        str: Formatted string containing all search results
    """
    output = []
    for root, _, files in os.walk(directory):
        for file in files:
            if extension and not file.endswith(extension):
                continue
                
            file_path = os.path.join(root, file)
            matches = search_in_file(file_path, search_term, context)
            if matches:
                for match_line, snippet, abs_path in matches:  # Updated to unpack abs_path
                    output.append(f"\nFile: {abs_path}")  # Using abs_path instead of file_path
                    output.append(f"Match found at line: {match_line}")
                    for line_number, code in snippet:
                        output.append(f"{line_number:4} | {code}")
                    output.append("-" * 50)
    
    return "\n".join(output) if output else "No matches found."

def get_full_path(partial_path: str) -> str:
    """
    Convert partial path to full path if it's part of the current working directory path.
    Returns the original path if it's already absolute or not found in current path.
    """
    if os.path.isabs(partial_path):
        return partial_path
        
    cwd = os.path.abspath(os.getcwd())
    if partial_path in cwd:
        # If the partial path is found within the current working directory path
        parts = cwd.split(partial_path)
        return parts[0] + partial_path
    
    return partial_path

@tool(parse_docstring=True)
def search_keyword_in_directory(directory: str, search_term: str, context: int = 2):
    """
    A search tool that searchs for a keyword in all Python files contents in the specified directory. this tool is like cmd+f in your IDE. search_term MUST be at least 3 characters long.
    
    Args:
        directory: Directory path to search (can be partial or full path)
        search_term: Term to search for in files contents (case-insensitive)
        context: Number of context lines to include before and after match (default: 2)
    """
    full_directory = get_full_path(directory)
    return search_directory(full_directory, search_term, extension=".py", context=context)

# List of available tools
search_tools = [search_keyword_in_directory]
search_tools_map = {tool.name: tool for tool in search_tools}

if __name__ == "__main__":
    # Example usage
    directory = "./workspace_repo/browser-use"  # Current directory
    search_term = "screenshot"  # Search for function definitions
    
    # Example 1: Search all Python files
    print("Searching for 'def' in Python files:")
    results = search_keyword_in_directory.invoke({"directory": directory, "search_term":search_term})
    print(results)
    #
    # # Example 2: Search all files with custom extension
    # print("\nSearching for 'def' in all .txt files:")
    # results = search_directory(directory, search_term, extension=".py", context=3)
    # print(results)
    #
    # # Example 3: Search single file
    # print("\nSearching in a specific file:")
    # file_path = "../../agent/tools/search.py"  # This file itself
    # results = search_in_file(file_path, "search", context=1)
    # for line_num, snippet, abs_path in results:
    #     print(f"\nMatch at line {line_num}:")
    #     for snip_num, line in snippet:
    #         print(f"{snip_num:4} | {line}")


