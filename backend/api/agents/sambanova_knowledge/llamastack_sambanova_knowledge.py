import os
import asyncio
import time
import json
from utils.logging import logger

from llama_stack_client import LlamaStackClient
from llama_stack_client.lib.agents.agent import Agent
from llama_stack_client.lib.agents.event_logger import EventLogger
from llama_stack_client.types.agents.turn_response_event_payload import  AgentTurnResponseTurnCompletePayload, AgentTurnResponseStepStartPayload, AgentTurnResponseStepCompletePayload


# Example tool definition
def get_sambanova_info(query: str) -> str:
    """
    Runs get sambanova_info rag tool.
    
    :param query: sambanova related query.
        
    Returns:
        str: the response for the sambanova query
    """
    return "sambanova aisk: AI Starter kit are a series of quickstart open source llm applications provided by sambanova"

def create_http_client(api_key=None):
    return LlamaStackClient(
        base_url=f"http://localhost:{os.environ['LLAMA_STACK_PORT']}",
        provider_data={"sambanova_api_key": api_key}
    )

def create_agent(client, model):
    agent = Agent(
        client,
        model=model,
        instructions="You are a helpful assistant. Use the tools you have access to for providing relevant answers",
        sampling_params={
            "strategy": {"type": "top_p", "temperature": 1.0, "top_p": 0.9},
        },
        tools=[
            get_sambanova_info
        ],
        enable_session_persistence=False,
    )
    return agent
    
def call(thread_config, query, api_key):    
    
    config=thread_config["configurable"]
    messages = [{"role": "user", "content": query}]
    
    redis_client = config["redis_client"]
    
    client = (create_http_client(api_key))
    agent = create_agent(client, config["model"])

    response = agent.create_turn(
        messages=messages,
        session_id=agent.create_session(f"{config['user_id']}:{config['conversation_id']}"),
    )
    
    assistant_metadata = {
        "duration": 1,
        "llm_name": config["model"],
        "llm_provider": config["provider"],
        "workflow": config["workflow_name"],
        "agent_name": config["agent_name"],
        "task": "assistant",
        "total_tokens": 10,
        "prompt_tokens": 10,
        "completion_tokens": 10,
    }
    
    for log in response:
        if isinstance(log.event.payload, AgentTurnResponseTurnCompletePayload):
            response = log.event.payload.turn.output_message.content
        else:
            event_message = None
            if isinstance(log.event.payload, AgentTurnResponseStepStartPayload):
                event_message = log.event.payload.step_type
            elif isinstance(log.event.payload, AgentTurnResponseStepCompletePayload):
                event_message = log.event.payload.step_details
            if event_message is not None:
                intermediate_message = {
                        "user_id": config["user_id"],
                        "run_id": config["conversation_id"],
                        "message_id": config["message_id"],
                        "agent_name": config["agent_name"],
                        "text": str(event_message),
                        "timestamp": time.time(),
                        "metadata": assistant_metadata,
                    }
                
                channel = f"agent_thoughts:{config['user_id']}:{config['conversation_id']}"
                redis_client.publish(channel, json.dumps(intermediate_message))
    
    return response