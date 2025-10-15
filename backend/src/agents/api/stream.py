import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from agents.api.websocket_interface import WebSocketInterface
from langchain.schema.messages import HumanMessage
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.types import Command, Interrupt

logger = structlog.get_logger(__name__)


async def astream_state_websocket(
    app: Runnable,
    input: HumanMessage,
    config: RunnableConfig,
    websocket_manager: WebSocketInterface,
    user_id: str,
    conversation_id: str,
    message_id: str,
) -> None:
    """Stream messages from the runnable directly to WebSocket."""
    root_run_id: Optional[str] = None
    messages: dict[str, BaseMessage] = {}

    if "resume" in input.additional_kwargs and input.additional_kwargs["resume"]:
        # Decide if it's feedback or a brand-new request
        content_lower = input.content.lower().strip()
        # Accept multiple approval keywords for voice and text input
        # Extended list to better support voice mode natural language
        approval_keywords = [
            "approve", "approved", "yes", "continue", "proceed", "true",
            "ok", "okay", "sure", "go ahead", "yep", "yeah", "affirmative",
            "confirm", "confirmed", "accepted"
        ]
        if any(keyword in content_lower for keyword in approval_keywords):
            graph_input = Command(resume="APPROVE")
        elif input.content:
            # user typed some text, treat it as feedback
            graph_input = Command(resume=input.content)

        msg = {
            "event": "agent_completion",
            "run_id": root_run_id,
            **input.model_dump(),
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        msg["id"] = str(uuid.uuid4())
        msg["type"] = "HumanMessage"
        await websocket_manager.send_message(
            user_id,
            conversation_id,
            msg,
        )
    else:
        graph_input = input

    interrupt = False

    async for event in app.astream_events(
        graph_input,
        config,
        version="v2",
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

        elif event["event"] == "on_chain_stream":
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

                converted_msgs = convert_messages_to_dict(new_messages)
                for msg in converted_msgs:
                    # DEBUG: Log what we're sending via WebSocket
                    logger.info(
                        "DEBUG: Sending agent_completion via WebSocket",
                        msg_type=msg.get("type"),
                        has_additional_kwargs="additional_kwargs" in msg,
                        additional_kwargs_keys=list(msg.get("additional_kwargs", {}).keys()) if "additional_kwargs" in msg else None,
                        has_workflow_timing=msg.get("additional_kwargs", {}).get("workflow_timing") is not None,
                        workflow_timing_preview=str(msg.get("additional_kwargs", {}).get("workflow_timing", {}))[:200] if msg.get("additional_kwargs", {}).get("workflow_timing") else None,
                    )

                    await websocket_manager.send_message(
                        user_id,
                        conversation_id,
                        {
                            "event": "agent_completion",
                            "run_id": root_run_id,
                            **msg,
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "message_id": message_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
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
                    "content": message.content,
                    "id": message.id,
                    "is_delta": True,
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

            # DEBUG: Log what model_dump returns
            logger.info(
                "DEBUG: convert_messages_to_dict model_dump",
                msg_type=item.__class__.__name__,
                has_additional_kwargs="additional_kwargs" in msg_dict,
                additional_kwargs_keys=list(msg_dict.get("additional_kwargs", {}).keys()) if "additional_kwargs" in msg_dict else None,
                has_workflow_timing=msg_dict.get("additional_kwargs", {}).get("workflow_timing") is not None,
                has_response_metadata="response_metadata" in msg_dict,
                response_metadata_keys=list(msg_dict.get("response_metadata", {}).keys()) if "response_metadata" in msg_dict else None,
            )

            # Add the message type
            msg_dict["type"] = item.__class__.__name__
            result.append(msg_dict)

        elif isinstance(item, Interrupt):
            result.append(
                {
                    "content": item.value,
                    "type": "AIMessage",
                    "additional_kwargs": {
                        "agent_type": "deep_research_interrupt",
                    },
                }
            )
        else:
            # Handle other types as-is (no ID to check for duplicates)
            result.append(item)
    return result
