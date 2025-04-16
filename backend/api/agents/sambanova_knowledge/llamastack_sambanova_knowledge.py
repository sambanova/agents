import os
import re
import asyncio
import time
import json
from utils.logging import logger

import llama_stack_client
from llama_stack_client import LlamaStackClient
from llama_stack_client.lib.agents.agent import Agent
from llama_stack_client.lib.agents.event_logger import EventLogger
from llama_stack_client.types.agents.turn_response_event_payload import (
    AgentTurnResponseTurnCompletePayload,
    AgentTurnResponseStepStartPayload,
    AgentTurnResponseStepCompletePayload,
    ToolExecutionStep,
    InferenceStep,
)

from config.model_registry import model_registry

class UnstructuredDataTools():
    def __init__(self, llamastack_client, provider):
        self.files={}
        self.client = llamastack_client
        
        #get model id
        if provider not in ["sambanova"]:
            raise ValueError(f"Sambanova Knowledge agent doesn't have support for provider {provider}")
        model_info = model_registry.get_model_info(
            model_key="llama-3.2-11b", 
            provider=provider
        )
        if not model_info:
            raise ValueError(f"No model configuration found for provider {provider}")
        
        self.vision_model = f"{model_info['crewai_prefix']}/{model_info['model']}"
        
    def save_files(self, b64_files: list):
        self.files = b64_files
        
    def get_files(self):
        return self.files    
    
    def get_image_files(self):
        image_formats=["png","jpg","jpeg"]
        image_files = []
        for filename, data in self.get_files().items():
            if filename.lower().split('.')[-1] in image_formats:
                image_files.append(data)
        return image_files
    
    # Tools that requires access to files 
    def image_analysis(self, query: str) -> str:
        """
        Runs image analysis tool.

        :param image: str
        :param query:  str
        
        Returns:
            str: the response of analyse the image with the query 
            
        """ 
        
        files = self.get_image_files()
        if len(files)==0:
            return "The user has not attached any image"
        else:    
            response = self.client.inference.chat_completion(
                model_id=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content":{
                            "type": "image",
                            "image": {
                                "url": {
                                    "uri": files[0]
                                }
                            }
                        }
                    },
                    {
                        "role": "user",
                        "content": query,
                    }
                ],
            )

            return response.completion_message.content

def estimate_tokens_regex(text: str) -> int:
    """
    proxy for token estimation used given llamastack doesn't return server inference metadata
    """
    return len(re.findall(r"\w+|\S", text))


def create_http_client(api_key=None):
    return LlamaStackClient(
        base_url=f"http://{os.environ['LLAMA_STACK_HOST']}:{os.environ['LLAMA_STACK_PORT']}",
        provider_data={"sambanova_api_key": api_key},
    ) 

def create_agent(client, model, docs_tools):
    """
    initialize agent
    """
    agent = Agent(
        client,
        model=model,
        instructions="""
        You are a helpful assistant that can access external functions. The responses from these function calls will be appended to this dialogue. Please provide responses based on the information from these function calls.
        You are given a question and a set of possible functions.
        Based on the question, you will need to make one or more function/tool calls to achieve the purpose.
        If none of the function can be used, point it out. If the given question lacks the parameters required by the function, also point it out.
        If you decide to invoke any of the function(s), you MUST put it in a valid json format, the format is:
        [{{"name": func_1, "parameters": dictionary of argument name and its value}}, {{"name": func_2, "parameters": dictionary of argument name and its value}}]
        If you decide to call a function you SHOULD NOT include any other text in the response.
        Avoid generating extra scape characters when calling a function (like `\\n`, multiple backslashes `\\\\` and other format that could generate problems when parsing the arguments of the function call
        
        You are a general agent, you can use your tools to execute code or analyse and interpret images. Remember, always give the final answer using the tool result, if the results are empty or you receive an error, retry fixing according to error messages and finally if this is not enough let the user know.
        
        When doing data analysis and you need to pass some data to convert as dataframe be careful to not omit relevant characters like `\\n`
        """,
        sampling_params={
            "strategy": {"type": "top_p", "temperature": 0.3, "top_p" : 0.3},
        },
        tools=["builtin::code_interpreter", docs_tools.image_analysis],
        enable_session_persistence=False,
    )
    return agent


def call(thread_config, query, docs, files_b64, provider, api_key):
    """
    create llamastack client and agent and call it
    """

    config = thread_config["configurable"]
    messages = [{"role": "user", "content": f"attached documents: {docs} \n\n {query}"}]
    print(docs)

    redis_client = config["redis_client"]

    client = create_http_client(api_key)
    docs_tools = UnstructuredDataTools(client, provider)
    
    if files_b64 is not None:
        docs_tools.save_files(files_b64)
    agent = create_agent(client, config["model"], docs_tools)

    # agent turn execution
    response = agent.create_turn(
        messages=messages,
        session_id=agent.create_session(
            f"{config['user_id']}:{config['conversation_id']}"
        ),
    )

    # init metadata
    assistant_metadata = {
        "duration": 1,
        "llm_name": config["model"],
        "llm_provider": config["provider"],
        "workflow": config["workflow_name"],
        "agent_name": config["agent_name"],
        "task": "code_execution",
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }

    # estimation of initial instructions and tool definitions tokens
    assistant_metadata["total_tokens"] = 201 + estimate_tokens_regex(f"{messages}")

    # iterate over agent execution events
    for log in response:
        # start input tokens with cumulative total tokes as being sent as input (conversation history)
        assistant_metadata["prompt_tokens"] = assistant_metadata["total_tokens"]
        assistant_metadata["completion_tokens"] = 0

        # if server error event is None return message to the user
        if log.event is None:
            del client
            del agent
            del docs_tools
            return f"sambanova knowledge agent can not complete this request: {log.error.get('message', log.error)}", assistant_metadata
        # if event is complete payload final response is ready
        if isinstance(log.event.payload, AgentTurnResponseTurnCompletePayload):
            response = log.event.payload.turn.output_message.content
            assistant_metadata["completion_tokens"] += estimate_tokens_regex(response)

        # if even is a step completed check for the type to publish intermediate step
        if isinstance(log.event.payload, AgentTurnResponseStepCompletePayload):
            # inference step
            if log.event.payload.step_details.step_type == "inference":
                if (
                    len(log.event.payload.step_details.api_model_response.tool_calls)
                    > 0
                ):
                    tool_calls = (
                        log.event.payload.step_details.api_model_response.tool_calls
                    )
                    event_message = {
                        "event_object": [
                            {
                                "name": "Llamastack Inference",
                                "Inference with tool calls": f"\n```json\n{tool_calls}```",
                            }
                        ]
                    }
                elif len(log.event.payload.step_details.api_model_response.content) > 0:
                    event_message = {
                        "event_object": [
                            {
                                "name": "Llamastack Inference",
                                "Inference": log.event.payload.step_details.api_model_response.content,
                            }
                        ]
                    }
                else:
                    event_message = {
                        "event_object": [
                            {
                                "name": "Llamastack Inference",
                                "Event": str(log.event.payload.step_details),
                            }
                        ]
                    }
                assistant_metadata["completion_tokens"] += estimate_tokens_regex(
                    str(event_message)
                )
            # tool call step
            elif log.event.payload.step_details.step_type == "tool_execution":
                tool_calls = log.event.payload.step_details.tool_calls
                tool_responses = log.event.payload.step_details.tool_responses
                task = tool_calls[0].tool_name
                event_message = {
                    "event_object": [
                        {
                            "name": task,
                            "Tool calls": f"```json\n{tool_calls}\n```",
                            "Tool Execution results": f"```json\n{tool_responses}\n```",
                        },
                    ]
                } # TODO update agent name with task to update icons
                assistant_metadata["prompt_tokens"] += estimate_tokens_regex(
                    str(event_message)
                )
            # other step
            else:
                event_message = {"Event": str(log.event.payload.step_details)}
                assistant_metadata["completion_tokens"] += estimate_tokens_regex(
                    str(event_message)
                )

            # update metadata
            assistant_metadata["total_tokens"] += (
                assistant_metadata["completion_tokens"]
                + assistant_metadata["prompt_tokens"]
            )

            # if completion step event publish event
            if event_message is not None:
                intermediate_message = {
                    "user_id": config["user_id"],
                    "run_id": config["conversation_id"],
                    "message_id": config["message_id"],
                    "agent_name": config["agent_name"],
                    "text": event_message,
                    "timestamp": time.time(),
                    "metadata": assistant_metadata,
                }
                channel = (
                    f"agent_thoughts:{config['user_id']}:{config['conversation_id']}"
                )
                redis_client.publish(channel, json.dumps(intermediate_message))
                
    del client
    del agent
    del docs_tools

    return response, assistant_metadata
