import os
import re
import asyncio
import time
import json
from utils.logging import logger

from llama_stack_client import LlamaStackClient
from llama_stack_client.lib.agents.agent import Agent
from llama_stack_client.lib.agents.event_logger import EventLogger
from llama_stack_client.types.agents.turn_response_event_payload import  AgentTurnResponseTurnCompletePayload, AgentTurnResponseStepStartPayload, AgentTurnResponseStepCompletePayload, ToolExecutionStep, InferenceStep

def estimate_tokens_regex(text: str) -> int:
    """
    proxy for token estimation used given llamastack doesn't return server inference metadata  
    """
    return len(re.findall(r"\w+|\S", text))

def create_http_client(api_key=None):
    return LlamaStackClient(
        base_url=f"http://localhost:{os.environ['LLAMA_STACK_PORT']}",
        provider_data={"sambanova_api_key": api_key}
    )
    
# Example tool definition
def code_executor(query: str) -> str:
    """
    Runs code executor tool.
    
    :param query: code expression to run in sandbox environment.
        
    Returns:
        str: the response of evaluating the expression
    """
    try:
        result = eval(query)
    except Exception as e:
        result = f"error when evaluating expression {query} - {e}"
    return True

def create_agent(client, model):
    """
    initialize agent
    """
    agent = Agent(
        client,
        model=model,
        instructions="You are a helpful assistant. Use the tools you have access to for providing relevant answers",
        sampling_params={
            "strategy": {"type": "top_p", "temperature": 1.0, "top_p": 0.9},
        },
        tools=[
            code_executor
        ],
        enable_session_persistence=False,
    )
    return agent
    
def call(thread_config, query, api_key):    
    """
    create llamastack client and agent and call it 
    """
    
    config=thread_config["configurable"]
    messages = [{"role": "user", "content": query}]
    
    redis_client = config["redis_client"]
    
    client = (create_http_client(api_key))
    agent = create_agent(client, config["model"])

    response = agent.create_turn(
        messages=messages,
        session_id=agent.create_session(f"{config['user_id']}:{config['conversation_id']}"),
    )
    
    # init metadata
    assistant_metadata = {
        "duration": 1,
        "llm_name": config["model"],
        "llm_provider": config["provider"],
        "workflow": config["workflow_name"],
        "agent_name": config["agent_name"],
        "task": "code_execution", # TODO update dynamically
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }
    
    #estimation of initial instructions and tool definitions tokens
    assistant_metadata["total_tokens"]=201+estimate_tokens_regex(f"{messages}") 
    
    # iterate over agent execution events
    for log in response:
        # start input tokens with cumulative total tokes as being sent as input (conversation history) 
        assistant_metadata["prompt_tokens"]=assistant_metadata["total_tokens"]
        assistant_metadata["completion_tokens"]=0
        
        # if event is complete payload final response is ready
        if isinstance(log.event.payload, AgentTurnResponseTurnCompletePayload):
            response = log.event.payload.turn.output_message.content
            assistant_metadata["completion_tokens"]+=estimate_tokens_regex(response)
            
        # if even is a step completed check for the type to publish intermediate step
        if isinstance(log.event.payload, AgentTurnResponseStepCompletePayload):
            # inference step
            if log.event.payload.step_details.step_type == "inference":
                if len(log.event.payload.step_details.api_model_response.tool_calls)>0:
                    step_type = "Inference with tool calls"
                    tool_calls = log.event.payload.step_details.api_model_response.tool_calls
                    event_message = f"\n```json\n{tool_calls}```"
                elif len(log.event.payload.step_details.api_model_response.content)>0:
                    step_type = "Inference"
                    event_message = log.event.payload.step_details.api_model_response.content
                else: 
                    step_type = "event"
                    event_message = str(log.event.payload.step_details)
                assistant_metadata["completion_tokens"]+=estimate_tokens_regex(event_message)
            # tool call step
            elif log.event.payload.step_details.step_type == "tool_execution":
                step_type = "ToolExecution"
                tool_calls =  log.event.payload.step_details.tool_calls
                tool_responses = log.event.payload.step_details.tool_responses
                event_message = f"\nTool calls:\n```json\n{tool_calls}\n```\n\nTool Execution results\n```json\n{tool_responses}\n```"
                assistant_metadata["prompt_tokens"]+=estimate_tokens_regex(event_message)
            # other step
            else:
                step_type = "Event"
                event_message = str(log.event.payload.step_details)
                assistant_metadata["completion_tokens"]+=estimate_tokens_regex(event_message)
            
            # update metadata
            assistant_metadata["total_tokens"]+=(assistant_metadata["completion_tokens"]+assistant_metadata["prompt_tokens"])
            
            # if completion step event publish event
            if event_message is not None:
                intermediate_message = {
                        "user_id": config["user_id"],
                        "run_id": config["conversation_id"],
                        "message_id": config["message_id"],
                        "agent_name": config["agent_name"],
                        "text": f"{step_type}: {event_message}",
                        "timestamp": time.time(),
                        "metadata": assistant_metadata,
                    }
                channel = f"agent_thoughts:{config['user_id']}:{config['conversation_id']}"
                redis_client.publish(channel, json.dumps(intermediate_message))

    return response, assistant_metadata