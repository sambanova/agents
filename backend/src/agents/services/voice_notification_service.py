"""
Voice notification service for generating natural language summaries of agent actions.
This service monitors agent events and creates voice-friendly updates.
"""
import structlog
from typing import Dict, Optional

logger = structlog.get_logger(__name__)


class VoiceNotificationService:
    """
    Service for generating voice notifications from agent events.

    This service translates agent actions into natural, conversational
    voice updates that inform the user about what's happening.
    """

    def __init__(self):
        """Initialize the voice notification service."""
        # Mapping of agent types to voice-friendly descriptions
        self.agent_descriptions = {
            # Main agent types
            "react_subgraph_financial_analysis": "I'm analyzing financial data",
            "financial_analysis_end": "Financial analysis complete",
            "react_subgraph_deep_research": "I'm conducting deep research on this topic",
            "deep_research_end": "Research complete",
            "react_subgraph_data_science": "I'm running data science analysis",
            "data_science_end": "Data analysis complete",

            # Tool responses
            "tool_response": "I've gathered the information",
            "retrieval": "I'm searching through the documents",

            # Code execution
            "daytona_code_sandbox": "I'm running code in the sandbox",
            "code_execution": "Executing your code now",
            "code_result": "Code execution complete",

            # Search and research
            "search": "Searching the web",
            "web_search": "I'm searching online for relevant information",
            "exa_search": "Looking up the latest sources",

            # Financial specific
            "financial_competitor_finder": "Finding competitor information",
            "financial_aggregator": "Aggregating financial data",
            "fundamental_analysis": "Analyzing financial fundamentals",
            "technical_analysis": "Performing technical analysis",
            "risk_assessment": "Assessing risk factors",

            # Data processing
            "hypothesis_agent": "Generating analysis hypotheses",
            "process_agent": "Processing the data",
            "visualization_agent": "Creating visualizations",
            "quality_review": "Reviewing the results for quality",

            # Final responses
            "assistant_end": "Here's what I found",
            "human": "Processing your request",
        }

        # Tool-specific messages
        self.tool_messages = {
            "arxiv": "Searching academic papers",
            "search_tavily": "Searching the web with Tavily",
            "search_tavily_answer": "Getting direct answer from Tavily",
            "wikipedia": "Looking up Wikipedia articles",
            "retrieval": "Searching your documents",
            "financial_data": "Fetching financial data",
        }

    def get_voice_update(
        self,
        event_type: str,
        agent_type: Optional[str] = None,
        tool_name: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a voice-friendly update message from an agent event.

        Args:
            event_type: Type of event (agent_completion, tool_call, etc.)
            agent_type: Type of agent that generated the event
            tool_name: Name of tool being called (if applicable)
            content: Content of the message (optional, for context)

        Returns:
            Voice-friendly message string, or None if no notification needed
        """
        try:
            # Handle different event types
            if event_type == "agent_completion":
                # Agent finished a step
                if agent_type and agent_type in self.agent_descriptions:
                    return self.agent_descriptions[agent_type]

            elif event_type == "tool_call":
                # Agent is calling a tool
                if tool_name and tool_name in self.tool_messages:
                    return self.tool_messages[tool_name]
                elif tool_name:
                    return f"Using {tool_name}"

            elif event_type == "think":
                # Agent is thinking/reasoning
                # Parse the thinking content for specific actions
                if content and isinstance(content, str):
                    content_lower = content.lower()

                    if "searching" in content_lower:
                        return "Searching for information"
                    elif "analyzing" in content_lower:
                        return "Analyzing the data"
                    elif "calculating" in content_lower:
                        return "Running calculations"
                    elif "generating" in content_lower:
                        return "Generating the response"
                    elif "processing" in content_lower:
                        return "Processing your request"

            elif event_type == "stream_start":
                return "Starting to work on your request"

            elif event_type == "stream_complete":
                return "Task completed"

            # If we couldn't generate a specific message, return None
            # This prevents over-narration
            return None

        except Exception as e:
            logger.error(f"Error generating voice update: {str(e)}")
            return None

    def should_notify(
        self,
        event_type: str,
        agent_type: Optional[str] = None,
        last_notification_time: Optional[float] = None,
        min_interval: float = 3.0,
    ) -> bool:
        """
        Determine if a voice notification should be sent for this event.

        Args:
            event_type: Type of event
            agent_type: Agent type (if applicable)
            last_notification_time: Timestamp of last notification
            min_interval: Minimum seconds between notifications

        Returns:
            True if notification should be sent
        """
        try:
            import time

            # Always notify for major state changes
            major_events = [
                "stream_start",
                "stream_complete",
                "financial_analysis_end",
                "deep_research_end",
                "data_science_end",
                "assistant_end",
            ]

            if event_type in major_events or (agent_type and agent_type in major_events):
                return True

            # For other events, enforce minimum interval to avoid over-narration
            if last_notification_time is not None:
                time_since_last = time.time() - last_notification_time
                if time_since_last < min_interval:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking notification eligibility: {str(e)}")
            return False

    def format_final_response(self, content: str, metadata: Optional[Dict] = None) -> str:
        """
        Format a final response for voice delivery.

        Args:
            content: The response content
            metadata: Optional metadata about the response

        Returns:
            Voice-optimized response text
        """
        try:
            # For voice, we want to:
            # 1. Remove excessive markdown formatting
            # 2. Make it more conversational
            # 3. Add natural pauses

            # Remove code blocks for voice (user can see them in UI)
            import re
            content = re.sub(r"```[\s\S]*?```", "[Code snippet available in chat]", content)

            # Remove markdown headers that don't read well
            content = re.sub(r"#{1,6}\s+", "", content)

            # Replace bullet points with natural language
            content = re.sub(r"^\s*[-*]\s+", "", content, flags=re.MULTILINE)

            # Add metadata context if provided
            if metadata:
                if metadata.get("has_charts"):
                    content += ". I've also generated some charts for you to review."
                if metadata.get("has_files"):
                    content += ". Check the files I've created in the chat."
                if metadata.get("sources_count", 0) > 0:
                    sources_count = metadata["sources_count"]
                    content += f". This is based on {sources_count} sources."

            # Limit length for voice (will be truncated if too long)
            max_length = 500
            if len(content) > max_length:
                content = content[:max_length] + "... Full details are in the chat."

            return content

        except Exception as e:
            logger.error(f"Error formatting voice response: {str(e)}")
            return content  # Return original if formatting fails
