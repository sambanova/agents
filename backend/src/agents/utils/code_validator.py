import ast
import html
import re
import uuid

import structlog

logger = structlog.get_logger(__name__)


def patch_plot_code_str(code_str):
    """
    Enhanced code patcher that:
    - Replaces plt.show() with plt.savefig() if matplotlib.pyplot is imported as plt
    - Handles HTML/CSS/JS file creation more robustly
    - Adds basic syntax validation
    Returns:
        - patched code as string
        - list of generated filenames
    """

    # Basic syntax validation
    try:
        # Try to parse the code to check for syntax errors
        ast.parse(code_str)
    except SyntaxError as e:
        # If there's a syntax error, try to provide a helpful message
        raise ValueError(f"Code contains syntax errors: {str(e)}")
    except Exception:
        # If parsing fails for other reasons, continue but log it
        pass

    class PlotPatcher(ast.NodeTransformer):
        def __init__(self):
            self.has_pyplot_import = False
            self.filenames = []
            self.has_file_operations = False
            super().__init__()

        def visit_Import(self, node):
            for alias in node.names:
                if alias.name == "matplotlib.pyplot" and alias.asname == "plt":
                    self.has_pyplot_import = True
            return self.generic_visit(node)

        def visit_ImportFrom(self, node):
            if node.module == "matplotlib" and any(
                alias.name == "pyplot" and alias.asname == "plt" for alias in node.names
            ):
                self.has_pyplot_import = True
            return self.generic_visit(node)

        def visit_Call(self, node):
            # Check for file writing operations
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                self.has_file_operations = True
                # Extract filename if it's a string literal
                if node.args and isinstance(node.args[0], ast.Constant):
                    filename = node.args[0].value
                    if isinstance(filename, str) and filename not in self.filenames:
                        self.filenames.append(filename)

            # Check for write operations on file objects
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "write":
                self.has_file_operations = True

            return self.generic_visit(node)

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call):
                func = node.value.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "show"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "plt"
                    and self.has_pyplot_import
                ):
                    filename = f"plot_{uuid.uuid4().hex[:8]}.png"
                    self.filenames.append(filename)
                    return ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="plt", ctx=ast.Load()),
                                attr="savefig",
                                ctx=ast.Load(),
                            ),
                            args=[ast.Constant(value=filename)],
                            keywords=[],
                        )
                    )
            return self.generic_visit(node)

    try:
        tree = ast.parse(code_str)
        patcher = PlotPatcher()
        patched_tree = patcher.visit(tree)
        ast.fix_missing_locations(patched_tree)

        patched_code = ast.unparse(patched_tree)  # Requires Python 3.9+

        # Post-processing: Add error handling for file operations
        if patcher.has_file_operations:
            # Wrap the code in try-except to handle file operation errors
            error_handled_code = f"""
try:
{chr(10).join("    " + line for line in patched_code.split(chr(10)) if line.strip())}
except Exception as e:
    print(f"Error during file operations: {{e}}")
    import traceback
    traceback.print_exc()
    raise e
"""
            patched_code = error_handled_code.strip()

        return patched_code, patcher.filenames

    except AttributeError:
        raise RuntimeError("ast.unparse requires Python 3.9+")
    except Exception as e:
        # If patching fails, return original code but still try to extract filenames
        filenames = extract_filenames_from_string(code_str)
        return code_str, filenames


def extract_filenames_from_string(code_str):
    """
    Fallback method to extract likely filenames from code string using regex.
    This helps when AST parsing fails.
    """
    filenames = []

    # Look for common file creation patterns
    patterns = [
        r'open\s*\(\s*["\']([^"\']+\.(html|css|js|txt|csv|json|xml))["\']',
        r'with\s+open\s*\(\s*["\']([^"\']+\.(html|css|js|txt|csv|json|xml))["\']',
        r'savefig\s*\(\s*["\']([^"\']+\.(png|jpg|jpeg|svg|pdf))["\']',
        r'to_html\s*\(\s*["\']([^"\']+\.html)["\']',
        r'to_csv\s*\(\s*["\']([^"\']+\.csv)["\']',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, code_str, re.IGNORECASE)
        for match in matches:
            filename = match[0] if isinstance(match, tuple) else match
            if filename not in filenames:
                filenames.append(filename)

    return filenames


def strip_markdown_code_blocks(code_str):
    """
    Enhanced function to strip markdown code block formatting from a code string.
    Handles multiple code block formats and common parsing issues that cause HTML generation problems.
    """
    if not isinstance(code_str, str):
        return str(code_str).strip() if code_str is not None else ""

    # Remove opening code block markers (```python, ```py, ```html, or just ```)
    code_str = re.sub(
        r"^```(?:python|py|html|css|javascript|js)?\s*\n?",
        "",
        code_str,
        flags=re.MULTILINE,
    )

    # Remove closing code block markers
    code_str = re.sub(r"\n?```\s*$", "", code_str, flags=re.MULTILINE)

    # Remove <|python_start|> and <|python_end|> tags
    code_str = re.sub(r"<\|python_start\|>\s*\n?", "", code_str, flags=re.MULTILINE)
    code_str = re.sub(r"\n?\s*<\|python_end\|>", "", code_str, flags=re.MULTILINE)

    # Handle tool_input tags more robustly - common source of HTML parsing errors
    code_str = re.sub(r"<tool_input[^>]*>", "", code_str, flags=re.MULTILINE)
    code_str = re.sub(r"</tool_input[^>]*>", "", code_str, flags=re.MULTILINE)

    # Remove incomplete tool tags that can break execution
    code_str = re.sub(r"<tool[^>]*>.*?</tool[^>]*>", "", code_str, flags=re.DOTALL)
    code_str = re.sub(r"</?tool[^>]*>", "", code_str, flags=re.MULTILINE)

    # Handle common XML/HTML artifacts that interfere with Python execution
    code_str = re.sub(r"<\?xml[^>]*\?>", "", code_str, flags=re.MULTILINE)
    code_str = re.sub(r"<!DOCTYPE[^>]*>", "", code_str, flags=re.MULTILINE)

    # Remove leading/trailing whitespace and empty lines
    code_str = code_str.strip()

    # Decode HTML entities (e.g., &lt; &gt;)
    if "&lt;" in code_str or "&gt;" in code_str or "&amp;" in code_str:
        code_str = html.unescape(code_str)

    # Remove any stray trailing '<' characters introduced by partial tag removal
    code_str = re.sub(r"<+$", "", code_str).rstrip()

    # Remove any remaining partial <tool or </tool tokens without closing bracket
    code_str = re.sub(r"</?tool[^>\n]*", "", code_str, flags=re.MULTILINE)
    # Collapse excessive blank lines
    code_str = re.sub(r"\n{3,}", "\n\n", code_str)

    # Validate that we still have executable code
    if not code_str or len(code_str.strip()) < 5:
        logger.warning(
            "Code block stripping resulted in very short or empty code, using fallback"
        )
        raise ValueError("Code block stripping resulted in very short or empty code")

    # Basic syntax validation for Python code
    lines = code_str.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]

    # If we have code but no Python-like content, it might be pure HTML/CSS
    has_python_keywords = any(
        keyword in code_str.lower()
        for keyword in [
            "import",
            "def",
            "class",
            "if",
            "for",
            "while",
            "print",
            "return",
        ]
    )

    if not has_python_keywords and len(non_empty_lines) > 0:
        # Check if this looks like HTML/CSS/JS content
        if any(
            tag in code_str.lower()
            for tag in ["<html", "<div", "<body", "<style", "function"]
        ):
            logger.info(
                "Detected non-Python code (HTML/CSS/JS), wrapping in file creation"
            )
            # Wrap in Python code to write the content to a file
            file_extension = "html"
            if "<style" in code_str.lower() or "css" in original_code.lower():
                file_extension = "css"
            elif (
                "function" in code_str.lower() or "javascript" in original_code.lower()
            ):
                file_extension = "js"

            wrapped_code = f'''
# Auto-generated wrapper for {file_extension.upper()} content
content = """
{code_str}
"""

filename = "generated_content.{file_extension}"
with open(filename, "w", encoding="utf-8") as f:
f.write(content)

print(f"{{file_extension.upper()}} content written to {{filename}}")
'''
            return wrapped_code.strip()

    return code_str


def validate_and_fix_html_content(content: str, filename: str) -> str:
    """
    Validates HTML content and attempts to fix common issues that prevent proper rendering.
    """
    try:
        # Basic HTML structure validation and enhancement
        content_lower = content.lower().strip()

        # Check if it's a complete HTML document
        has_doctype = content_lower.startswith("<!doctype")
        has_html_tag = "<html" in content_lower
        has_head_tag = "<head" in content_lower
        has_body_tag = "<body" in content_lower

        # If it's missing essential HTML structure, wrap it
        if not has_html_tag and not has_doctype:
            logger.info("Adding HTML structure to", filename=filename)

            # Detect if it's CSS or JavaScript
            if "<style" in content_lower or "css" in filename.lower():
                # Wrap CSS in proper HTML
                content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Generated CSS Content</title>
<style>
{content}
</style>
</head>
<body>
<h1>CSS Styles Applied</h1>
<p>This document contains the generated CSS styles.</p>
</body>
</html>"""
            elif (
                "<script" in content_lower
                or "javascript" in content_lower
                or filename.lower().endswith(".js")
            ):
                # Wrap JavaScript in proper HTML
                content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Generated JavaScript Content</title>
</head>
<body>
<h1>JavaScript Application</h1>
<div id="app"></div>
<script>
{content}
</script>
</body>
</html>"""
            else:
                # Wrap general HTML content
                content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Generated Content</title>
</head>
<body>
{content}
</body>
</html>"""

        # Fix common HTML issues
        # Ensure proper charset declaration
        if "charset" not in content_lower and "<head" in content_lower:
            content = content.replace("<head>", '<head>\n    <meta charset="UTF-8">')

        # Add viewport meta tag for mobile responsiveness
        if "viewport" not in content_lower and "<head" in content_lower:
            charset_pos = content.lower().find("charset")
            if charset_pos != -1:
                # Find end of charset meta tag
                next_tag = content.find(">", charset_pos)
                if next_tag != -1:
                    content = (
                        content[: next_tag + 1]
                        + '\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">'
                        + content[next_tag + 1 :]
                    )

        # Decode HTML entities if needed
        if "&lt;" in content or "&gt;" in content or "&amp;" in content:
            content = html.unescape(content)
            content_lower = content.lower().strip()

        logger.info("HTML content validated and enhanced", filename=filename)
        return content

    except Exception as e:
        logger.warning(
            "Could not validate/fix HTML content", filename=filename, error=e
        )
        return content  # Return original content if validation fails
