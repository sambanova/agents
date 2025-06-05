from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence, Union

from agents.api.data_types import AgentEnum, AgentStructuredResponse
from agents.api.websocket_interface import WebSocketInterface
from langchain_core.messages import (
    AnyMessage,
    BaseMessage,
)
from langchain_core.runnables import Runnable, RunnableConfig
from langchain.schema.messages import HumanMessage, AIMessage
from langgraph.types import Interrupt


async def astream_state_websocket(
    app: Runnable,
    input: Union[Sequence[AnyMessage], Dict[str, Any]],
    config: RunnableConfig,
    websocket_manager: WebSocketInterface,
    user_id: str,
    conversation_id: str,
    message_id: str,
) -> None:
    """Stream messages from the runnable directly to WebSocket."""
    root_run_id: Optional[str] = None
    messages: dict[str, BaseMessage] = {}

    interrupt = False

    async for event in app.astream_events(
        input,
        config,
        version="v1",
        stream_mode="values",
        exclude_tags=["nostream"],
    ):
        if event["event"] == "on_chain_start" and not root_run_id:
            root_run_id = event["run_id"]
            # Send initial event via WebSocket
            await websocket_manager.send_message(
                user_id,
                conversation_id,
                {
                    "event": "stream_start",
                    "run_id": root_run_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        elif event["event"] == "on_chain_stream" and event["run_id"] == root_run_id:
            new_messages: list[BaseMessage] = []

            # Extract messages from the event data
            state_chunk = event["data"]["chunk"]

            # Handle different state formats
            if isinstance(state_chunk, dict):
                # StateGraph format - extract messages from state
                if "messages" in state_chunk:
                    state_chunk_msgs = state_chunk["messages"]
                elif "__interrupt__" in state_chunk:
                    state_chunk_msgs = state_chunk["__interrupt__"]
                    interrupt = True
                else:
                    # Skip non-message state updates
                    continue
            elif isinstance(state_chunk, (list, tuple)):
                # MessageGraph format - messages are directly in the chunk
                state_chunk_msgs = state_chunk
            else:
                # Skip unknown formats
                continue

            # Process each message
            for msg in state_chunk_msgs:
                if isinstance(msg, dict):
                    # Message as dict - get ID from dict
                    msg_id = msg.get("id")
                else:
                    # Message object - get ID from attribute
                    msg_id = getattr(msg, "id", None)

                if msg_id and msg_id in messages and msg == messages[msg_id]:
                    # Skip duplicate messages
                    continue
                else:
                    # New or updated message
                    if msg_id:
                        messages[msg_id] = msg
                    new_messages.append(msg)

            if new_messages:
                # Send new messages via WebSocket
                for msg in new_messages:
                    await websocket_manager.send_message(
                        user_id,
                        conversation_id,
                        {
                            "event": "agent_completion",
                            "run_id": root_run_id,
                            **convert_messages_to_dict([msg])[0],
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "message_id": message_id,
                            "timestamp": (
                                msg.additional_kwargs.get("timestamp")
                                if hasattr(msg, "additional_kwargs")
                                else datetime.now(timezone.utc).isoformat()
                            ),
                        },
                    )

        elif event["event"] == "on_chat_model_stream":
            # Handle streaming from chat models (for both agent types)
            message: BaseMessage = event["data"]["chunk"]
            if message.id not in messages:
                messages[message.id] = message
            else:
                messages[message.id] += message

            # Send streaming content via WebSocket
            await websocket_manager.send_message(
                user_id,
                conversation_id,
                {
                    "event": "llm_stream_chunk",
                    "run_id": root_run_id,
                    "data": {
                        "content": (
                            message.content
                            if hasattr(message, "content")
                            else str(message)
                        ),
                        "node": event["metadata"]["langgraph_node"],
                        "id": message.id,
                        "is_delta": True,  # Indicates this is a streaming chunk
                    },
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        # Stop streaming if an interrupt is detected
        if interrupt:
            break

    if interrupt:
        # Send completion event
        await websocket_manager.send_message(
            user_id,
            conversation_id,
            {
                "event": "stream_complete",
                "run_id": root_run_id,
                "data": {},
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    else:
        # Send completion event
        await websocket_manager.send_message(
            user_id,
            conversation_id,
            {
                "event": "stream_complete",
                "run_id": root_run_id,
                "data": {
                    "output": convert_messages_to_dict(
                        event["data"]["output"]
                        if isinstance(event["data"]["output"], list)
                        else [event["data"]["output"]]
                    ),
                },
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


def convert_messages_to_dict(output_list):
    """Convert message objects to dictionaries in the output data."""
    result = []
    seen_ids = set()

    for item in output_list:
        if isinstance(item, dict):
            # Convert each value (message object) to dict
            converted_item = {}
            for key, value in item.items():
                # Check for duplicate message ID
                msg_id = (
                    getattr(value, "id", None)
                    if hasattr(value, "id")
                    else value.get("id") if isinstance(value, dict) else None
                )
                if msg_id and msg_id in seen_ids:
                    continue
                if msg_id:
                    seen_ids.add(msg_id)

                if hasattr(value, "model_dump"):
                    # Pydantic v2 style
                    msg_dict = value.model_dump()
                    msg_dict["type"] = value.__class__.__name__
                    converted_item[key] = msg_dict
                elif hasattr(value, "dict"):
                    # Pydantic v1 style
                    msg_dict = value.dict()
                    msg_dict["type"] = value.__class__.__name__
                    converted_item[key] = msg_dict
                else:
                    converted_item[key] = value
            if converted_item:  # Only add if not empty after deduplication
                result.append(converted_item)
        elif hasattr(item, "model_dump") or hasattr(item, "dict"):
            # Handle message objects directly in the list
            msg_id = getattr(item, "id", None)
            if msg_id and msg_id in seen_ids:
                continue
            if msg_id:
                seen_ids.add(msg_id)

            if hasattr(item, "model_dump"):
                # Pydantic v2 style
                msg_dict = item.model_dump()
            else:
                # Pydantic v1 style
                msg_dict = item.dict()

            # Add the message type
            msg_dict["type"] = item.__class__.__name__
            result.append(msg_dict)

        elif isinstance(item, Interrupt):
            result.append(
                {
                    "content": item.value,
                    "type": "AIMessage",
                    "agent_type": "deep_research_interrupt",
                }
            )
        else:
            # Handle other types as-is (no ID to check for duplicates)
            result.append(item)
    return result
