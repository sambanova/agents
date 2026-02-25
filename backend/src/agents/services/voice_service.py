"""
Voice service for managing Hume AI EVI (Empathic Voice Interface) sessions.
"""
import os
from typing import Dict, Optional
import structlog
import httpx
from hume import AsyncHumeClient
from agents.storage.redis_storage import RedisStorage

logger = structlog.get_logger(__name__)


class HumeVoiceService:
    """Service for managing Hume AI voice sessions and context injection."""

    def __init__(self, redis_storage: RedisStorage):
        """
        Initialize the Hume Voice Service.

        Args:
            redis_storage: RedisStorage instance for accessing user data
        """
        self.redis_storage = redis_storage
        self.api_key = os.getenv("HUME_API_KEY")
        self.secret_key = os.getenv("HUME_SECRET_KEY")
        self.config_id = os.getenv("HUME_EVI_CONFIG_ID")

        if not self.api_key or not self.secret_key:
            logger.warning(
                "Hume API credentials not configured. Voice mode will be unavailable."
            )

    async def generate_access_token(self) -> Optional[Dict[str, str]]:
        """
        Generate a short-lived, scoped access token for Hume EVI
        using the OAuth2 client-credentials flow.

        Returns:
            Dict with access_token and expires_in, or None if not configured
        """
        if not self.api_key or not self.secret_key:
            logger.error("Cannot generate token: Hume API key or secret key not configured")
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.hume.ai/oauth2-cc/token",
                    auth=(self.api_key, self.secret_key),
                    data={"grant_type": "client_credentials"},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10.0,
                )
                response.raise_for_status()
                token_data = response.json()

            logger.info("Generated scoped Hume EVI access token successfully")

            return {
                "access_token": token_data["access_token"],
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": token_data.get("expires_in", 600),
            }
        except Exception as e:
            logger.error(f"Failed to generate Hume access token: {str(e)}")
            return None

    async def get_user_context(
        self, user_id: str, conversation_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Build user context for injection into Hume EVI session.

        Args:
            user_id: User ID
            conversation_id: Optional conversation ID for loading history

        Returns:
            Dict with system_prompt, context, and variables
        """
        context_data = {
            "system_prompt": "",
            "context": "",
            "variables": {},
        }

        try:
            # Build system prompt with user context
            system_prompt_parts = [
                "You are a friendly, empathic AI voice assistant with access to powerful backend agents.",
                "",
                "YOUR TOOL:",
                "- You have access to 'query_backend_agent' tool that connects to backend agents",
                "- Use this tool for ANY substantive questions or requests from users",
                "- The tool provides: financial analysis, research, code execution, web search, and more",
                "- If the user has connected integrations (Google Workspace, Jira, PayPal, Notion), the tool can also access those",
                "",
                "HOW YOU WORK:",
                "1. When a user asks a question, IMMEDIATELY respond out loud with a brief acknowledgment (2-5 words)",
                "   Examples: 'Let me check that...', 'Looking that up now...', 'One moment please...'",
                "2. WHILE SPEAKING your acknowledgment, call the 'query_backend_agent' tool with their query",
                "3. You CAN speak while the tool is running - EVI 3 supports parallel processing",
                "4. When the tool response arrives, seamlessly incorporate it into your answer",
                "5. For simple greetings ('hi', 'hello'), respond warmly without calling the tool",
                "",
                "YOUR INTERACTION STYLE:",
                "- NEVER stay silent - ALWAYS speak immediately when the user finishes talking",
                "- Start with acknowledgment FIRST (speak it out loud): 'Let me check that...', 'Searching for that now...'",
                "- Then call the tool WHILE or right after speaking your acknowledgment",
                "- Be warm, natural, and conversational",
                "- Don't wait for the tool - speak your acknowledgment BEFORE the tool response arrives",
                "- When you get tool responses, incorporate them naturally into your ongoing response",
                "- Look for [Processing steps: ...] prefix showing what the agents did",
                "- Reference these steps naturally: 'I searched for info, analyzed the data, and here's what I found...'",
                "- Summarize results conversationally - this is a conversation, not an essay",
                "- Keep voice responses concise and engaging",
                "- For follow-up questions, call the tool again if needed",
                "",
                "CRITICAL RULES:",
                "- You MUST ALWAYS use the query_backend_agent tool for ANY factual questions (stock prices, financial data, research, analysis, current events, company info, market data)",
                "- NEVER provide factual information from your training data alone - you must ALWAYS verify via the tool",
                "- If a user asks for facts, data, or analysis, respond: 'Let me check that for you' then immediately call the tool",
                "- Even if you think you know the answer, you MUST verify it using the tool - your knowledge may be outdated",
                "- The ONLY exceptions are: greetings ('hi', 'hello'), casual chat, and clarifying questions",
                "- For everything else (stocks, companies, research topics, code, analysis), you MUST use the tool",
                "",
                "EXAMPLES REQUIRING THE TOOL:",
                "- 'What's Apple's stock price?' → MUST call tool (stock data changes constantly)",
                "- 'Analyze Tesla financials' → MUST call tool (requires current data)",
                "- 'Research AI trends' → MUST call tool (requires web search and analysis)",
                "- 'What is X company doing?' → MUST call tool (requires current info)",
                "- 'Check my calendar' → MUST call tool (if Google Workspace is connected)",
                "- 'What Jira tickets are assigned to me?' → MUST call tool (if Atlassian is connected)",
                "",
                "CONNECTOR INTEGRATIONS:",
                "- Google Workspace (Gmail, Calendar, Drive): Available if the user has connected their Google account",
                "- Atlassian (Jira & Confluence): Available if the user has connected their Atlassian account",
                "- PayPal: Available if the user has connected their PayPal account",
                "- Notion: Available if the user has connected their Notion workspace",
                "- When you receive responses from these connectors, incorporate the data naturally into your answer",
                "- If a user asks about something requiring a connector that's not enabled, you can mention they can connect it in settings",
                "",
                "DEEP RESEARCH AUTO-APPROVAL:",
                "- The system automatically approves deep research requests in voice mode",
                "- DO NOT ask the user 'Should I proceed with deep research?' or 'Do you want me to approve this?'",
                "- Simply acknowledge the request and let the backend handle it: 'I'll do a comprehensive research on that for you...'",
                "- When the research is complete, summarize the key findings from the report naturally",
                "",
                "STYLE GUIDELINES:",
                "- If you see processing steps in the response, acknowledge them briefly but naturally",
                "- Don't read the steps verbatim - paraphrase conversationally",
                "- Incorporate tool results naturally - don't say 'the tool returned...'",
                "- Be conversational and empathic, not robotic",
                "- Keep it brief and voice-friendly",
            ]

            context_data["system_prompt"] = "\n".join(system_prompt_parts)

            # Build context with available tools/capabilities
            context_parts = [
                f"User ID: {user_id}",
                "Current mode: Voice assistant",
                "",
                "AVAILABLE CAPABILITIES:",
                "",
                "Subgraphs:",
                "- Financial Analysis: Analyze stocks, get company financials, market research",
                "- Deep Research: Comprehensive research reports on any topic",
                "- Code Execution: Run Python code, data analysis, visualizations",
                "",
                "Tools:",
                "- arxiv: Search academic papers",
                "- search_tavily: Web search for current information",
                "- search_tavily_answer: Get direct answers from web search",
                "- wikipedia: Look up encyclopedic information",
                "",
                "Connector Integrations (user-enabled):",
                "- Google Workspace: Gmail, Google Calendar, Google Drive (if connected)",
                "- Atlassian: Jira tickets, Confluence pages (if connected)",
                "- PayPal: Transaction history, account info (if connected)",
                "- Notion: Workspace pages, databases (if connected)",
            ]

            # TODO: Fetch user's actual connected integrations and update context dynamically
            # For now, we list all available connectors with "(if connected)" qualifier

            # Load conversation history if available
            if conversation_id:
                try:
                    messages = await self.redis_storage.get_messages(
                        user_id, conversation_id
                    )
                    if messages and len(messages) > 0:
                        context_parts.append(
                            f"\nActive conversation with {len(messages)} previous messages"
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not load conversation history: {str(e)}"
                    )

            context_data["context"] = "\n".join(context_parts)

            # Set up variables for dynamic prompt injection
            context_data["variables"] = {
                "user_id": user_id[:8],
                "timestamp": "",
            }

            logger.info(
                "Built user context for voice session", user_id=user_id[:8]
            )

            return context_data

        except Exception as e:
            logger.error(f"Error building user context: {str(e)}")
            return context_data

    def get_session_settings(
        self,
        system_prompt: str,
        context: str,
        variables: Dict[str, str],
        voice_name: str = "ITO",
    ) -> Dict:
        """
        Build Hume EVI session settings message.

        Args:
            system_prompt: System prompt for the session
            context: Persistent context
            variables: Dynamic variables for the session
            voice_name: Voice to use (default: ITO)

        Returns:
            Session settings message dict
        """
        # Define tool for EVI to call backend agents
        # Note: parameters must be a JSON STRING, not an object
        import json

        tools = [
            {
                "type": "function",  # Required by Hume
                "name": "query_backend_agent",
                "description": "Query the backend agent system for information, analysis, research, or to execute tasks. Use this for any substantive user requests.",
                "parameters": json.dumps({
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The user's question or request to send to the backend agents"
                        }
                    },
                    "required": ["query"]
                })
            }
        ]

        return {
            "voice": {"name": voice_name},
            "systemPrompt": system_prompt,  # String, not object
            "context": {"text": context, "type": "persistent"},
            "variables": variables,
            "tools": tools,
        }

    async def get_voice_config(self, user_id: str) -> Dict[str, str]:
        """
        Get user's voice preferences from storage.

        Args:
            user_id: User ID

        Returns:
            Dict with voice preferences (voice_name, narration_enabled, etc.)
        """
        # Default voice settings
        default_config = {
            "voice_name": "ITO",
            "narration_enabled": True,
            "speech_speed": "normal",
            "verbosity": "balanced",  # Options: "concise", "balanced", "detailed"
        }

        try:
            # Try to load from Redis
            config_key = f"voice_config:{user_id}"
            stored_config = await self.redis_storage.redis_client.get(
                config_key, user_id
            )

            if stored_config:
                import json

                return {**default_config, **json.loads(stored_config)}

            return default_config

        except Exception as e:
            logger.warning(
                f"Could not load voice config, using defaults: {str(e)}"
            )
            return default_config

    async def save_voice_config(
        self, user_id: str, config: Dict[str, str]
    ) -> bool:
        """
        Save user's voice preferences to storage.

        Args:
            user_id: User ID
            config: Voice configuration dict

        Returns:
            True if saved successfully
        """
        try:
            import json

            config_key = f"voice_config:{user_id}"
            await self.redis_storage.redis_client.set(
                config_key, json.dumps(config), user_id
            )

            logger.info("Saved voice config for user", user_id=user_id[:8])
            return True

        except Exception as e:
            logger.error(f"Failed to save voice config: {str(e)}")
            return False
