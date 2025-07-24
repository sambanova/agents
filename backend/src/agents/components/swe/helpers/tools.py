import json


def tools_to_str(tools: list) -> str:
    tool_descriptions = "\n---\n".join(
        [
            f"Tool Name: {tool.name}\n "
            f"Tool Description: {tool.description} "
            for tool in tools
        ]
    )
    return tool_descriptions