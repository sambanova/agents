from typing import Optional, List, Dict, Any
from enum import Enum
from .data_types import CoPilotPlan, EducationalContent, EndUserMessage, FinancialAnalysis, SalesLeads
from .otlp_tracing import logger
from pydantic import BaseModel
from typing import get_origin, get_args, get_type_hints

def generate_type_string(model: BaseModel) -> str:
    """Generates a string representation of the type structure of a Pydantic model, recursively."""

    def type_to_string(type_hint):
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        if origin is list:
            return f"List[{type_to_string(args[0])}]" if args else "List"
        elif origin:  # Generic type like List, Dict, etc.
            return str(origin).replace("typing.", "")
        elif isinstance(type_hint, type) and issubclass(type_hint, Enum):  # Handle Enum types
            enum_values = [f'"{v.value}"' for v in type_hint]
            return f"Enum({', '.join(enum_values)})"
        elif issubclass(type_hint, BaseModel):  # Check for nested Pydantic models
            return generate_type_string(type_hint)  # Recursive call
        elif hasattr(type_hint, '__name__'):  # Regular class
            return type_hint.__name__
        else:  # Basic type (str, int, etc.)
            return type_hint.__name__

    fields = get_type_hints(model) # Use get_type_hints to resolve forward refs
    fields_string = ", ".join(f'"{field}": {type_to_string(field_type)}' for field, field_type in fields.items())
    return "{ " + fields_string + " }"

class AgentRegistry:
    def __init__(self):
        self.agents = {
            "default_agent": {
                "agent_type": "default_agent",
                "description": "Handles user greetings, salutations, and general queries that do not fit into other specific categories. Route messages here if they are greetings (e.g., 'hi', 'hello', 'good morning') or general travel queries that do not specify a destination or service.",
                "examples": "'Hello', 'Hi there!', 'Good morning'",
            },
            "financial_analysis": {
                "agent_type": "financial_analysis",
                "description": "Handles financial analysis queries, including stock prices, financial statements, and market trends.",
                "examples": "Tell me about the stock price of Apple, What's the financial statement of Tesla?, Market trends in the tech sector?",
            },
            "sales_leads": {
                "agent_type": "sales_leads",
                "description": "Handles sales lead generation queries, including industry, location, and product information.",
                "examples": "Find me sales leads in the tech sector, What are the sales leads in the US?, Sales leads in the retail industry?",
            },
            "educational_content": {
                "agent_type": "educational_content",
                "description": "Handles educational content queries, including topics, audience level, and focus areas. This agent is used for queries that require a detailed explanation of a topic.",
                "examples": "Explain the relationship between quantum entanglement and teleportation?",
            },
        }

    async def get_agent(self, intent: str) -> Optional[dict]:
        logger.info(f"AgentRegistry: Getting agent for intent: {intent}")
        return self.agents.get(intent)
    
    def get_strucuted_output_plan_prompt(self, query: str) -> str:
        return f"""
    You are a structured output expert that extracts structured information from a query. You are given a query and you need to extract the structured information from the query.
    
    Only use information that is explicitly mentioned in the query. Do not add any assumed or inferred information.
    You can return multiple agents in the response if it is specified in the query.
   
    Query: "{query}"

    Ensure the output is valid JSON as it will be parsed using `json.loads()` in Python. 
    It should be in the schema: 
    <output>
    [
        {{
            "agent_type": "financial_analysis",
            "parameters": {generate_type_string(FinancialAnalysis)}
        }}
    ]

    [
        {{
            "agent_type": "sales_leads",
            "parameters": {generate_type_string(SalesLeads)}
        }}
    ]

    [
        {{
            "agent_type": "educational_content",
            "parameters": {generate_type_string(EducationalContent)}
        }}
    ]
    </output>

    Always return a valid JSON object with 'type' and 'parameters'.
    Ensure the final output does not include any code block markers like ```json or ```python.
        """

    def get_planner_prompt(self, message: EndUserMessage, history) -> str:
        agent_details = {}
        for agent in self.agents.values():
            agent_details[agent["agent_type"]] = {
                "description": agent["description"],
                "examples": agent.get("examples", ""),
                "functions": [],
            }


        agent_descriptions = "\n".join(
            f"""
    Agent Type: {agent_type}
    Description: {details['description']}
    Examples: {details['examples']}
    {chr(10).join([f"- Function: {func['function']} (Arguments: {', '.join(func['arguments'])})" for func in details['functions']]) if details['functions'] else ""}
    """
            for agent_type, details in agent_details.items()
        )

        planner_prompt = """
    You are an orchestration agent.
    Your job is to decide which agents to run based on the user's request and the conversation history.
    Below are the available agents:

    {agent_descriptions}

    The current user message: {message}
    Conversation history so far: {history}

    Your response should only include the selected agents and all the information the agents need to execute the task. You answer should be plain text, do not include any code blocks or JSON.
    """.format(
            agent_descriptions=agent_descriptions.strip(),
            message=message.content,
            history=", ".join(msg.content for msg in history),
            json_schema=generate_type_string(CoPilotPlan),
        )
        return planner_prompt
