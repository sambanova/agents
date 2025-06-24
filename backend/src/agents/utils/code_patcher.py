import ast
import uuid
import re


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
            error_handled_code = f'''
try:
{chr(10).join("    " + line for line in patched_code.split(chr(10)) if line.strip())}
except Exception as e:
    print(f"Error during file operations: {{e}}")
    import traceback
    traceback.print_exc()
'''
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
