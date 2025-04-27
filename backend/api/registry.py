########## NEW CODE ##########
from typing import Optional, List, Dict, Any
from enum import Enum
from .data_types import (
    AssistantMessage,
    EducationalContent,
    EndUserMessage,
    FinancialAnalysis,
    SalesLeads,
    UserQuestion,
    AgentEnum,  # import the extended enum with DeepResearch
    DeepResearch,
    SambaKnowledge,
)
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
        elif isinstance(type_hint, type) and issubclass(
            type_hint, Enum
        ):  # Handle Enum types
            enum_values = [f'"{v.value}"' for v in type_hint]
            return f"Enum({', '.join(enum_values)})"
        elif issubclass(type_hint, BaseModel):  # Check for nested Pydantic models
            return generate_type_string(type_hint)  # Recursive call
        elif hasattr(type_hint, "__name__"):  # Regular class
            return type_hint.__name__
        else:  # Basic type (str, int, etc.)
            return type_hint.__name__

    fields = get_type_hints(model)  # Use get_type_hints to resolve forward refs
    fields_string = ", ".join(
        f'"{field}": {type_to_string(field_type)}'
        for field, field_type in fields.items()
    )
    return "{ " + fields_string + " }"

class AgentRegistry:
    def __init__(self):
        self.agents = {
            "assistant": {
                "agent_type": "assistant",
                "description": "Handles user queries that do not fit into other specific categories. ALWAYS Route messages here if they are general queries that do not specify a destination or service. If the query is a factual answer or quick information about a company person or product, use this agent. For examlple What is Apple's stock price today or another company can be answered by this agent vs the financial_analysis agent.",
                "examples": "'What is the weather in Tokyo?', 'What is the capital of France?' What is Tesla's stock price? What is the latest news on Apple? What is the latest news on Elon Musk?",
            },
            "financial_analysis": {
                "agent_type": "financial_analysis",
                "description": "Handles complex financial analysis queries ONLY, including company reports, company financials, financial statements, and market trends. This is NOT for quick information or factual answers about STOCK PRICES. For this agent to work you need at least one ticker or company name. If the query is a factual answer or quick information about a company person or product, ALWAYS use the assistant agent instead. This is a specialized agent for complex financial analysis and NEVER use this agent for quick information or factual answers.",
                "examples": "Tell me about Apples financials, What's the financial statement of Tesla?, Market trends in the tech sector?",
            },
            "sales_leads": {
                "agent_type": "sales_leads",
                "description": "Handles sales lead generation queries, including industry, location, and product information.",
                "examples": "Find me sales leads in the tech sector, What are the sales leads in the US?, Sales leads in the retail industry?",
            },
            "educational_content": {
                "agent_type": "educational_content",
                "description": "Handles simpler or legacy educational queries. Possibly replaced by 'deep_research' for advanced multi-step analysis.",
                "examples": "Explain classical Newtonian mechanics in short form, Summarize a simple topic quickly.",
            },
            "deep_research": {
                "agent_type": "deep_research",
                "description": "Handles advanced educational content queries with a multi-step research flow (LangGraph). For queries that require a more in-depth or structured approach.",
                "examples": "Generate a thorough technical report on quantum entanglement with references, Provide a multi-section explanation with research steps.",
            },
            "sambanova_knowledge": {
                "agent_type": "sambanova_knowledge",
                "description": "Handles math, code, data analysis or image analysis queries with a LlamaStack agent. For queries that require code execution or image understanding.",
                "examples": "does the sentence 'On a clover, if alive, erupts a vast pure evil; a fire volcano' is a palindrome?",
            },
            "user_proxy": {
                "agent_type": "user_proxy",
                "description": "Handles questions that require a response from the user. This agent is used for queries that require a response from the user.",
                "examples": "Can you clarify your question?, Can you provide more information?",
            },
        }

    async def get_agent(self, intent: str) -> Optional[dict]:
        logger.info(f"AgentRegistry: Getting agent for intent: {intent}")
        return self.agents.get(intent)
    
    def get_context_summary_prompt(self) -> str:
        return f"""
        You are a context summary expert that summarizes the conversation history.
        The context summary should be a short summary of the conversation history.
        Mainly focus on the intent of the user's rather than the details of the conversation.
        Be concise and to the point.
        """

    def get_strucuted_output_plan_prompt(self, query: str) -> str:
        return f"""
    You are a structured output expert that extracts structured information from a query. You are given a query and you need to extract the structured information from the query.
    
    Only use information that is explicitly mentioned in the query. Do not add any assumed or inferred information.
    You can return multiple agents in the response if it is specified in the query. 
    You must return user_proxy if the query is a question that requires a response from the user.
   
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
            "agent_type": "deep_research",
            "parameters": {generate_type_string(DeepResearch)}
        }}
    ]
    
    [
        {{
            "agent_type": "sambanova_knowledge",
            "parameters": {generate_type_string(SambaKnowledge)}
        }} 
    ]

    [
        {{
            "agent_type": "educational_content",
            "parameters": {generate_type_string(EducationalContent)}
        }}
    ]

    [
        {{
            "agent_type": "assistant",
            "parameters": {generate_type_string(AssistantMessage)}
        }}
    ]

    [
        {{
            "agent_type": "user_proxy",
            "parameters": {generate_type_string(UserQuestion)}
        }}
    ]
    </output>

    Always return a valid JSON object with 'type' and 'parameters'.
    Ensure the final output does not include any code block markers like ```json or ```python.
        """

    def get_planner_prompt(self) -> str:
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
    IMPORTANT: You must include the selected name of the agents and all the information the agents need to execute the task. 
    If you decide to use the user_proxy agent, do not include any other agents in the response.
    You answer should be plain text, do not include any code blocks or JSON.
    """.format(
            agent_descriptions=agent_descriptions.strip(),
        )
        return planner_prompt