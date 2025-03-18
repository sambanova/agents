from typing import Optional

def format_api_error_message(error: Exception, agent_type: str = "") -> str:
    """
    Formats error messages for API-related errors consistently across different agents.
    
    Args:
        error: The exception that was raised
        agent_type: Optional string indicating the agent type for customized error messages
    
    Returns:
        A user-friendly error message
    """
    error_message = str(error).lower()
    
    # Handle rate limit errors
    if "rate limit exceeded" in error_message or "too many requests" in error_message:
        return "Rate limit exceeded. Please try again later."
    
    # Return agent-specific default error messages
    if agent_type:
        return f"Unable to assist with {agent_type}, try again later."
    
    # Generic fallback
    return "Unable to assist with this request, try again later." 