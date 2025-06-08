import ast
import uuid


def patch_plot_code_str(code_str):
    """
    Patches code string:
    - Replaces plt.show() with plt.savefig("plot_<uuid>.png") if plt.plot() was called
    Returns:
        - patched code as string
        - list of generated filenames
    """

    class PlotPatcher(ast.NodeTransformer):
        def __init__(self):
            self.has_plot_call = False
            self.filenames = []
            super().__init__()

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute):
                if (
                    node.func.attr == "plot"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "plt"
                ):
                    self.has_plot_call = True
            return self.generic_visit(node)

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call):
                func = node.value.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "show"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "plt"
                    and self.has_plot_call
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

    tree = ast.parse(code_str)
    patcher = PlotPatcher()
    patched_tree = patcher.visit(tree)
    ast.fix_missing_locations(patched_tree)

    try:
        patched_code = ast.unparse(patched_tree)  # Requires Python 3.9+
    except AttributeError:
        raise RuntimeError("ast.unparse requires Python 3.9+")

    return patched_code, patcher.filenames 