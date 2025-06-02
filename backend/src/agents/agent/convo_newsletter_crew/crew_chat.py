# agent/convo_newsletter_crew/crew_chat.py

import json
import re
import sys
import time
import threading
import uuid
from typing import Any, Dict, List, Optional, Set

# We'll keep CLI references to preserve original "old functionality"
import click
import redis
import os

from crewai.crew import Crew
from crewai.llm import LLM
from crewai.types.crew_chat import ChatInputField, ChatInputs
from crewai.utilities.llm_utils import create_llm

# Import your "newsletter_crew.py" that can accept API keys
from .newsletter_crew import ConvoNewsletterCrew

###############################################################################
# Redis-based conversation store. Replaces the old in-memory dict.
###############################################################################

def get_redis_client():
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

def redis_conversation_key(conversation_id: str, user_id: str) -> str:
    # We'll just store as "conversation:{user_id}:{conversation_id}"
    return f"conversation:{user_id}:{conversation_id}"

def load_conversation_data(user_id: str, conversation_id: str) -> Dict[str, Any]:
    r = get_redis_client()
    key = redis_conversation_key(conversation_id, user_id)
    raw = r.get(key)
    if not raw:
        return {}
    return json.loads(raw)

def save_conversation_data(user_id: str, conversation_id: str, data: Dict[str, Any]):
    r = get_redis_client()
    key = redis_conversation_key(conversation_id, user_id)
    r.set(key, json.dumps(data))

###############################################################################
# 1) CLI-based chat loop (OLD FUNCTIONALITY)
###############################################################################

def run_chat():
    """
    Runs an interactive chat loop (like the old CLI).
    No references to pyproject.toml or version checks are used here.
    """
    click.secho(
        "\nAnalyzing crew for conversation-based usage. Please wait...\n",
        fg="white"
    )

    crew_obj, messages, crew_tool_schema, available_functions = _initialize_cli_crew()

    click.secho("\nFinished analyzing crew.\n", fg="white")
    first_assistant_message = messages[-1]["content"]
    click.secho(f"Assistant: {first_assistant_message}\n", fg="green")

    # Now enter a loop for user input
    while True:
        try:
            user_input = _get_user_input()
            if user_input.strip().lower() == "exit":
                click.echo("Exiting chat. Goodbye!")
                break

            if not user_input.strip():
                click.echo("Empty message. Provide input or type 'exit'.")
                continue

            messages.append({"role": "user", "content": user_input})

            click.echo()
            click.secho("Assistant is processing your input. Please wait...", fg="green")

            response_text = _multi_turn_llm_call(crew_obj, messages, crew_tool_schema, available_functions)
            messages.append({"role": "assistant", "content": response_text})

            click.secho(f"\nAssistant: {response_text}\n", fg="green")

        except KeyboardInterrupt:
            click.echo("\nExiting chat. Goodbye!")
            break
        except Exception as exc:
            click.secho(f"Error: {exc}", fg="red")
            break

def _initialize_cli_crew():
    """
    Creates the crew in a CLI scenario, builds system message, calls LLM for intro.
    """
    crew_object = ConvoNewsletterCrew().crew()

    chat_llm = create_llm(crew_object.chat_llm)
    crew_name = "ConvoNewsletterCrew"
    crew_chat_inputs = generate_crew_chat_inputs(crew_object, crew_name, chat_llm)
    crew_tool_schema = generate_crew_tool_schema(crew_chat_inputs)
    system_message = build_system_message(crew_chat_inputs)

    # Intro message
    intro_msg = chat_llm.call(messages=[{"role": "system", "content": system_message}])
    messages = [
        {"role": "system", "content": system_message},
        {"role": "assistant", "content": intro_msg},
    ]
    available_functions = {
        crew_chat_inputs.crew_name: create_tool_function(crew_object, messages)
    }

    return crew_object, messages, crew_tool_schema, available_functions

def _get_user_input() -> str:
    """
    Collect multi-line user input with blank line as delimiter (CLI style).
    """
    click.secho("\nYou (type your message; press Enter twice to finish):", fg="blue")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)

###############################################################################
# 2) NEW: API-based methods (init & message) that do NOT re-init the Crew each time
###############################################################################

def api_init_conversation(
    sambanova_key: str,
    serper_key: Optional[str] = None,
    exa_key: Optional[str] = None,
    user_id: Optional[str] = None,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Initializes a brand-new conversation by creating a ConvoNewsletterCrew
    with the provided keys and user/run info, analyzing tasks/agents to build
    a system message & function schema, then returns the initial assistant reply.
    """
    # 1) Create the crew
    crew_object = ConvoNewsletterCrew(
        sambanova_key=sambanova_key,
        serper_key=serper_key,
        user_id=user_id,
    ).crew()

    # 2) Same analysis as CLI
    chat_llm = create_llm(crew_object.chat_llm)
    crew_name = "ConvoNewsletterCrew"
    crew_chat_inputs = generate_crew_chat_inputs(crew_object, crew_name, chat_llm)
    crew_tool_schema = generate_crew_tool_schema(crew_chat_inputs)
    system_message = build_system_message(crew_chat_inputs)

    # 3) Get the initial assistant message
    introductory_message = chat_llm.call(
        messages=[{"role": "system", "content": system_message}]
    )

    # 4) Start conversation
    messages = [
        {"role": "system", "content": system_message},
        {"role": "assistant", "content": introductory_message},
    ]

    available_functions = {
        crew_chat_inputs.crew_name: create_tool_function(crew_object, messages)
    }

    # 5) Unique conversation id
    conversation_id = str(uuid.uuid4())

    # 6) Save in Redis
    conv_data = {
        "crew_config": {
            "sambanova_key": sambanova_key or "",
            "serper_key": serper_key or "",
            "exa_key": exa_key or "",
        },
        "messages": messages,
        "crew_tool_schema": crew_tool_schema,
        "function_names": list(available_functions.keys())
    }
    save_conversation_data(user_id or "anonymous", conversation_id, conv_data)

    return {
        "conversation_id": conversation_id,
        "assistant_message": introductory_message
    }

def api_process_message(
    conversation_id: str,
    user_input: str,
    user_id: str = "anonymous"
) -> str:
    """
    Accepts a new user message for an existing conversation,
    calls the LLM with the same messages & tool schema, returns the new assistant reply.
    We do NOT re-instantiate the crew from scratch if not needed.
    """
    if not conversation_id:
        raise ValueError("Missing conversation_id")

    data = load_conversation_data(user_id, conversation_id)
    if not data:
        raise ValueError(f"No conversation found for id='{conversation_id}' user='{user_id}'.")

    config = data["crew_config"]
    messages = data["messages"]
    crew_tool_schema = data["crew_tool_schema"]
    fn_names = data["function_names"] or []
    if not fn_names:
        fn_names = ["ConvoNewsletterCrew"]

    # Re-init the crew object from config each time
    crew_obj = ConvoNewsletterCrew(
        sambanova_key=config.get("sambanova_key"),
        serper_key=config.get("serper_key"),
        user_id=user_id
    ).crew()

    # Build function dict
    available_functions = {
        fn_names[0]: create_tool_function(crew_obj, messages)
    }

    if not user_input.strip():
        return "You sent an empty message. Try again."

    # Add user message
    messages.append({"role": "user", "content": user_input})

    # Multi-turn
    final_response = _multi_turn_llm_call(crew_obj, messages, crew_tool_schema, available_functions)

    messages.append({"role": "assistant", "content": final_response})

    data_update = {
        "crew_config": config,
        "messages": messages,
        "crew_tool_schema": crew_tool_schema,
        "function_names": fn_names
    }
    save_conversation_data(user_id, conversation_id, data_update)

    return final_response

###############################################################################
# 2b) GET FULL HISTORY (NEW)
###############################################################################

def api_get_full_history(conversation_id: str, user_id: str="anonymous") -> Dict[str, Any]:
    """
    Return the entire conversation messages, so the front end can show them from start.
    """
    data = load_conversation_data(user_id, conversation_id)
    if not data:
        raise ValueError(f"No conversation found for id='{conversation_id}' user='{user_id}'.")
    return {
        "messages": data["messages"]
    }

###############################################################################
# 3) Common multi-turn approach from the CLI
###############################################################################

def _multi_turn_llm_call(
    crew_obj: Crew,
    messages: List[Dict[str, str]],
    crew_tool_schema: Dict[str, Any],
    available_functions: Dict[str, Any],
    max_calls: int = 5
) -> str:
    """
    Does a short loop to handle the possibility that the LLM calls the function multiple times.
    """
    chat_llm = crew_obj.chat_llm
    for _ in range(max_calls):
        raw_response = chat_llm.call(
            messages=messages,
            tools=[crew_tool_schema],
            available_functions=available_functions,
        )
        if not _is_function_call(raw_response):
            return raw_response

        fn_name, fn_args = _parse_function_call(raw_response)
        # unify function name => single crew function
        real_fn_name = list(available_functions.keys())[0]
        try:
            tool_func = available_functions[real_fn_name]
            tool_output = tool_func(**fn_args)
        except Exception as e:
            tool_output = f"Error running function {real_fn_name}: {str(e)}"

        messages.append({"role":"assistant","content":tool_output})

    return messages[-1]["content"]

def _is_function_call(response_text: str) -> bool:
    trimmed = response_text.strip()
    return trimmed.startswith("{") and '"name":' in trimmed

def _parse_function_call(response_text: str):
    data = json.loads(response_text)
    fn_name = data.get("name","")
    fn_args = data.get("arguments",{})
    if not isinstance(fn_args, dict):
        fn_args = {}
    return fn_name, fn_args

###############################################################################
# 4) Helper methods from original approach
###############################################################################

def generate_crew_chat_inputs(crew: Crew, crew_name: str, chat_llm: LLM) -> ChatInputs:
    required_inputs = fetch_required_inputs(crew)
    input_fields = []
    for input_name in required_inputs:
        desc = generate_input_description_with_ai(input_name, crew, chat_llm)
        input_fields.append(ChatInputField(name=input_name, description=desc))

    crew_description = generate_crew_description_with_ai(crew, chat_llm)
    return ChatInputs(
        crew_name=crew_name,
        crew_description=crew_description,
        inputs=input_fields
    )

def fetch_required_inputs(crew: Crew) -> Set[str]:
    placeholder_pattern = re.compile(r"\{(.+?)\}")
    required_inputs: Set[str] = set()

    for t in crew.tasks:
        text = f"{t.description or ''} {t.expected_output or ''}"
        required_inputs.update(placeholder_pattern.findall(text))

    for a in crew.agents:
        text = f"{a.role or ''} {a.goal or ''} {a.backstory or ''}"
        required_inputs.update(placeholder_pattern.findall(text))

    return required_inputs

def generate_input_description_with_ai(
    input_name: str, crew: Crew, chat_llm: LLM
) -> str:
    # For brevity, returning fallback. 
    # Original logic tried to gather context and call the LLM. We'll keep that approach short.
    return f"User input for '{input_name}'."

def generate_crew_description_with_ai(crew: Crew, chat_llm: LLM) -> str:
    # For brevity, a fallback:
    return "A specialized newsletter crew."

def generate_crew_tool_schema(crew_inputs: ChatInputs) -> dict:
    properties = {}
    for field in crew_inputs.inputs:
        properties[field.name] = {
            "type": "string",
            "description": field.description or "No description provided",
        }
    required_fields = [field.name for field in crew_inputs.inputs]

    return {
        "type": "function",
        "function": {
            "name": crew_inputs.crew_name,
            "description": crew_inputs.crew_description or "No crew description",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required_fields,
            },
        },
    }

def build_system_message(crew_chat_inputs: ChatInputs) -> str:
    required_fields_str = (
        ", ".join(
            f"{field.name} (desc: {field.description or 'n/a'})"
            for field in crew_chat_inputs.inputs
        )
        or "(No required fields detected)"
    )

    return (
        "You are a helpful AI assistant for the CrewAI platform. "
        "Your primary purpose is to assist users with the crew's specific tasks. "
        "You can answer general questions, but should guide users back to the crew's purpose afterward. "
        "You have a function (tool) you can call by name if you have all required inputs. "
        f"Those required inputs are: {required_fields_str}. "
        "If the user is off-topic, answer briefly then remind them. "
        "\nCrew Name: {crew_chat_inputs.crew_name}\n"
        f"Crew Description: {crew_chat_inputs.crew_description}"
    )

def create_tool_function(crew: Crew, messages: List[Dict[str, str]]):
    def run_crew_tool_with_messages(**kwargs):
        return run_crew_tool(crew, messages, **kwargs)
    return run_crew_tool_with_messages

def run_crew_tool(crew: Crew, messages: List[Dict[str, str]], **kwargs) -> str:
    try:
        kwargs["crew_chat_messages"] = json.dumps(messages)
        crew_output = crew.kickoff(inputs=kwargs)
        return str(crew_output)
    except Exception as e:
        return f"An error occurred while running the crew: {str(e)}"

###############################################################################
# If you want to allow "python crew_chat.py" => CLI usage:
###############################################################################
if __name__ == "__main__":
    run_chat()
