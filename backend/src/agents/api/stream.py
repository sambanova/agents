from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence, Union

from agents.api.websocket_interface import WebSocketInterface
from langchain_core.messages import (
    AnyMessage,
    BaseMessage,
)
from langchain_core.runnables import Runnable, RunnableConfig


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
                    "data": {"run_id": root_run_id},
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
                            "event": "agent_message_stream",
                            "data": {
                                "content": (
                                    msg.content if hasattr(msg, "content") else str(msg)
                                ),
                                "type": (
                                    msg.__class__.__name__
                                    if hasattr(msg, "__class__")
                                    else "unknown"
                                ),
                                "id": getattr(msg, "id", None),
                            },
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
                    "data": {
                        "content": (
                            message.content
                            if hasattr(message, "content")
                            else str(message)
                        ),
                        "id": message.id,
                        "is_delta": True,  # Indicates this is a streaming chunk
                    },
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

    # Send completion event
    await websocket_manager.send_message(
        user_id,
        conversation_id,
        {
            "event": "stream_complete",
            "data": {"run_id": root_run_id},
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
