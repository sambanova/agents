"""
OpenAI Responses API Compatible Router
Endpoint: /v1/responses
Specification: https://platform.openai.com/docs/api-reference/responses
"""
import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, Optional

import structlog
from agents.api.openai_models import (
    OpenAIError,
    ResponseObject,
    ResponseOutputText,
    ResponseRequest,
    ResponseStatus,
    ResponseTool,
    ResponseToolFunction,
    ResponseUsage,
    StreamEventOutputTextDelta,
    StreamEventResponseCompleted,
    StreamEventResponseCreated,
    create_error_response,
)
from agents.api.subgraph_factory import create_all_subgraphs
from agents.components.compound.agent import enhanced_agent
from agents.components.compound.data_types import LLMType
from agents.components.compound.xml_agent import get_global_checkpointer
from agents.api.utils import validate_external_url
from agents.tools.langgraph_tools import load_static_tools
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.types import Command, Interrupt

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/v1",
    tags=["OpenAI Compatible"],
    responses={
        401: {
            "description": "Unauthorized - Missing or invalid API key",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "message": "Authorization header with Bearer token is required",
                            "type": "authentication_error",
                            "code": "missing_auth"
                        }
                    }
                }
            }
        }
    }
)


# Define available subgraph tools in OpenAI format
AVAILABLE_TOOLS = [
    ResponseTool(
        type="function",
        function=ResponseToolFunction(
            name="financial_analysis",
            description="Analyze stocks, companies, and financial data. Provides comprehensive financial analysis including competitor analysis, market trends, and financial metrics.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The financial analysis query or company/stock symbol to analyze"
                    }
                },
                "required": ["query"]
            }
        )
    ),
    ResponseTool(
        type="function",
        function=ResponseToolFunction(
            name="deep_research",
            description="Conduct deep research on any topic with multiple search iterations, analysis, and comprehensive reporting. Best for complex research questions requiring in-depth investigation.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The research topic or question to investigate"
                    }
                },
                "required": ["query"]
            }
        )
    ),
    ResponseTool(
        type="function",
        function=ResponseToolFunction(
            name="code_execution",
            description="Execute Python code in a sandboxed environment. Can run data analysis, generate visualizations, and perform computations.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute"
                    }
                },
                "required": ["code"]
            }
        )
    ),
    ResponseTool(
        type="function",
        function=ResponseToolFunction(
            name="data_science",
            description="Perform comprehensive data science analysis on uploaded datasets. Requires file upload via separate endpoint. Includes hypothesis generation, statistical analysis, and visualization.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The data science analysis query or question about the data"
                    },
                    "file_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of uploaded files to analyze"
                    }
                },
                "required": ["query"]
            }
        )
    )
]


# Model mapping: OpenAI-style model names to internal agent types
MODEL_MAPPING = {
    "mainagent": "mainagent",
    "gpt-4": "mainagent",  # Alias for compatibility
    "gpt-3.5-turbo": "mainagent",  # Alias for compatibility
    "financialanalysis": "financialanalysis",
    "deepresearch": "deepresearch",
    "datascience": "datascience",
}


def _extract_text_from_messages(messages: list[BaseMessage]) -> str:
    """
    Extract final text content from messages, matching the working API behavior.
    Takes the LAST message content as the final output (like agent.py does).
    """
    if not messages or len(messages) == 0:
        return ""

    # Get the last message (final output) - this matches agent.py behavior
    final_message = messages[-1]

    if hasattr(final_message, 'content'):
        if isinstance(final_message.content, str):
            return final_message.content
        elif isinstance(final_message.content, list):
            # Handle list content (multimodal)
            text_parts = []
            for item in final_message.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return "\n".join(text_parts)

    return str(final_message)


async def _execute_agent_with_auto_resume(
    agent,
    initial_input,
    config: dict,
    thread_id: str,
    max_retries: int = 3
) -> dict:
    """
    Execute agent and auto-resume on interrupts (e.g., deep research approval).
    Returns the final state.
    """
    result = None

    # Initial execution
    async for chunk in agent.astream(
        initial_input,
        config=config,
        stream_mode="values"
    ):
        result = chunk

    # Handle interrupts with auto-approval
    interrupt_retry = 0
    while (
        result
        and "__interrupt__" in result
        and len(result.get("__interrupt__", [])) > 0
        and interrupt_retry < max_retries
    ):
        interrupt_msg = result["__interrupt__"][0]
        interrupt_value = interrupt_msg.value if isinstance(interrupt_msg, Interrupt) else interrupt_msg

        logger.info(
            "OpenAI API: Detected interrupt",
            thread_id=thread_id,
            interrupt_value_preview=str(interrupt_value)[:200],
            has_provide_feedback="provide feedback" in str(interrupt_value).lower(),
            has_approve="approve" in str(interrupt_value).lower()
        )

        # Auto-approve if it's a deep research or data science approval prompt
        if "provide feedback" in str(interrupt_value).lower() and "approve" in str(interrupt_value).lower():
            logger.info(
                "OpenAI API: Auto-approving interrupt",
                thread_id=thread_id,
                retry=interrupt_retry
            )
            result = None
            async for chunk in agent.astream(
                Command(resume="APPROVE"),
                config=config,
                stream_mode="values"
            ):
                result = chunk

            logger.info(
                "OpenAI API: After auto-approve",
                thread_id=thread_id,
                has_result=result is not None,
                has_messages="messages" in result if result and isinstance(result, dict) else False,
                result_keys=list(result.keys()) if result and isinstance(result, dict) else "NOT_A_DICT"
            )
            interrupt_retry += 1
        else:
            # Unknown interrupt type, break
            logger.warning(
                "OpenAI API: Unknown interrupt type, stopping",
                thread_id=thread_id,
                interrupt_value=str(interrupt_value)[:200]
            )
            break

    return result


async def _stream_agent_with_auto_resume(
    agent,
    initial_input,
    config: dict,
    thread_id: str,
    response_id: str,
    model: str,
    max_retries: int = 3
) -> AsyncGenerator[str, None]:
    """
    Stream agent execution with auto-resume on interrupts.
    Yields SSE-formatted events compatible with OpenAI Responses API.
    """
    created_timestamp = int(time.time())

    # Send initial response.created event
    initial_response = ResponseObject(
        id=response_id,
        object="response",
        created=created_timestamp,
        model=model,
        status=ResponseStatus.IN_PROGRESS,
        output=[],
        usage=None,
        metadata={"thread_id": thread_id}
    )

    created_event = StreamEventResponseCreated(
        event="response.created",
        data=initial_response
    )
    yield f"event: response.created\ndata: {created_event.model_dump_json()}\n\n"

    # Track accumulated output
    accumulated_text = ""
    current_message_id = None

    # Execute agent and stream events
    result = None
    async for event in agent.astream_events(
        initial_input,
        config=config,
        version="v2",
        stream_mode="values",
        exclude_tags=["nostream"],
    ):
        # Stream LLM chunks
        if event["event"] == "on_chat_model_stream":
            message: BaseMessage = event["data"]["chunk"]
            if message.content:
                accumulated_text += message.content
                current_message_id = message.id

                # Send output_text.delta event
                delta_event = StreamEventOutputTextDelta(
                    event="response.output_text.delta",
                    data={
                        "delta": message.content,
                        "message_id": message.id,
                    }
                )
                yield f"event: response.output_text.delta\ndata: {delta_event.model_dump_json()}\n\n"

        # Track final state
        elif event["event"] == "on_chain_stream":
            state_chunk = event["data"].get("chunk")
            if isinstance(state_chunk, dict):
                result = state_chunk

    # Handle interrupts with auto-approval
    interrupt_retry = 0
    while (
        result
        and "__interrupt__" in result
        and len(result.get("__interrupt__", [])) > 0
        and interrupt_retry < max_retries
    ):
        interrupt_msg = result["__interrupt__"][0]
        interrupt_value = interrupt_msg.value if isinstance(interrupt_msg, Interrupt) else interrupt_msg

        if "provide feedback" in str(interrupt_value).lower() and "approve" in str(interrupt_value).lower():
            logger.info(
                "OpenAI API Streaming: Auto-approving interrupt",
                thread_id=thread_id,
                retry=interrupt_retry
            )

            # Continue streaming after auto-approval
            result = None
            async for event in agent.astream_events(
                Command(resume="APPROVE"),
                config=config,
                version="v2",
                stream_mode="values",
                exclude_tags=["nostream"],
            ):
                if event["event"] == "on_chat_model_stream":
                    message: BaseMessage = event["data"]["chunk"]
                    if message.content:
                        accumulated_text += message.content
                        current_message_id = message.id

                        delta_event = StreamEventOutputTextDelta(
                            event="response.output_text.delta",
                            data={
                                "delta": message.content,
                                "message_id": message.id,
                            }
                        )
                        yield f"event: response.output_text.delta\ndata: {delta_event.model_dump_json()}\n\n"

                elif event["event"] == "on_chain_stream":
                    state_chunk = event["data"].get("chunk")
                    if isinstance(state_chunk, dict):
                        result = state_chunk

            interrupt_retry += 1
        else:
            logger.warning(
                "OpenAI API Streaming: Unknown interrupt type, stopping",
                thread_id=thread_id,
                interrupt_value=str(interrupt_value)[:200]
            )
            break

    # Extract artifacts from final result (if available)
    artifacts = []
    if result:
        messages_list = []
        if isinstance(result, list):
            messages_list = result
        elif isinstance(result, dict) and "messages" in result:
            messages_list = result["messages"]

        for message in messages_list:
            if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                files = message.additional_kwargs.get('files', [])
                if files:
                    for file in files:
                        if file not in artifacts:
                            artifacts.append(file)

    # Send final response.completed event with artifacts in metadata
    metadata = {"thread_id": thread_id}
    if artifacts:
        metadata["artifacts"] = artifacts

    final_response = ResponseObject(
        id=response_id,
        object="response",
        created=created_timestamp,
        model=model,
        status=ResponseStatus.COMPLETED,
        output=[
            ResponseOutputText(
                type="text",
                text=accumulated_text
            )
        ],
        usage=ResponseUsage(
            prompt_tokens=0,  # TODO: Calculate from tokenizer
            completion_tokens=0,
            total_tokens=0
        ),
        metadata=metadata
    )

    completed_event = StreamEventResponseCompleted(
        event="response.completed",
        data=final_response
    )
    yield f"event: response.completed\ndata: {completed_event.model_dump_json()}\n\n"


@router.get("/tools", response_model=list[ResponseTool])
async def list_tools(authorization: Optional[str] = Header(None)):
    """
    List all available tools/functions that can be used with the agent.

    This endpoint returns the available subgraphs (financial_analysis, deep_research, etc.)
    as OpenAI-compatible function definitions.

    Compatible with OpenAI SDK:
    ```python
    from openai import OpenAI

    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="your-api-key"
    )

    tools = client.get("/tools")
    ```
    """
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content=create_error_response(
                "Authorization header with Bearer token is required",
                "authentication_error",
                "missing_auth"
            ).model_dump()
        )
    return AVAILABLE_TOOLS


@router.post("/responses", response_model=ResponseObject, responses={
    200: {"description": "Successful response"},
    400: {"model": OpenAIError, "description": "Bad request"},
    401: {"model": OpenAIError, "description": "Unauthorized"},
    500: {"model": OpenAIError, "description": "Internal server error"},
})
async def create_response(
    request: Request,
    response_request: ResponseRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Create a response using OpenAI Responses API format.

    Supports both streaming (SSE) and non-streaming responses.

    Compatible with OpenAI SDK:
    ```python
    from openai import OpenAI

    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="your-api-key"
    )

    response = client.responses.create(
        model="mainagent",
        input="What are the latest AI trends?",
        stream=False
    )
    ```
    """
    # Validate authorization
    if not authorization or not authorization.startswith("Bearer "):
        error_response = create_error_response(
            message="Authorization header with Bearer token is required",
            error_type="authentication_error",
            code="missing_auth"
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_response.model_dump()
        )

    api_key = authorization.replace("Bearer ", "")

    # Validate model
    internal_model = MODEL_MAPPING.get(response_request.model)
    if not internal_model:
        error_response = create_error_response(
            message=f"Model '{response_request.model}' not found.",
            error_type="invalid_request_error",
            code="model_not_found"
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump()
        )

    # Extract input text and handle multimodal content (text + images)
    input_content = None
    if isinstance(response_request.input, str):
        input_text = response_request.input
        input_content = input_text
    elif isinstance(response_request.input, list):
        # Handle multimodal input (text + images)
        text_parts = []
        has_images = False
        content_list = []

        for item in response_request.input:
            if item.type == "text":
                text_parts.append(item.text)
                content_list.append({"type": "text", "text": item.text})
            elif item.type == "image":
                has_images = True
                # Handle image input - convert to LangChain format
                if item.source.type == "url":
                    # SSRF protection: block internal/private image URLs
                    if not validate_external_url(item.source.url):
                        error_response = create_error_response(
                            message="Image URL must be an external, publicly-routable address",
                            error_type="invalid_request_error",
                            code="invalid_image_url"
                        )
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content=error_response.model_dump()
                        )
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": item.source.url}
                    })
                elif item.source.type == "base64":
                    content_list.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{item.source.base64}"}
                    })

        input_text = " ".join(text_parts)
        # Use multimodal content if images present, otherwise just text
        input_content = content_list if has_images else input_text
    else:
        error_response = create_error_response(
            message="Invalid input format",
            error_type="invalid_request_error",
            code="invalid_input"
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump()
        )

    # Generate IDs
    response_id = f"resp_{uuid.uuid4().hex[:24]}"
    thread_id = str(uuid.uuid4())

    try:
        # Setup agent (currently only mainagent supported)
        if internal_model != "mainagent":
            error_response = create_error_response(
                message=f"Model '{internal_model}' not yet implemented. Only 'mainagent' is currently supported.",
                error_type="invalid_request_error",
                code="model_not_implemented"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response.model_dump()
            )

        redis_storage = request.app.state.redis_storage_service
        checkpointer = get_global_checkpointer()

        # Load tools
        tools_config = [
            {"type": "arxiv", "config": {}},
            {"type": "search_tavily", "config": {}},
            {"type": "search_tavily_answer", "config": {}},
            {"type": "wikipedia", "config": {}},
        ]
        all_tools = await load_static_tools(tools_config)

        # Load connector tools if available
        try:
            from agents.connectors.core.connector_manager import get_connector_manager
            connector_manager = get_connector_manager()
            if connector_manager:
                connector_tools = await connector_manager.get_user_tools(api_key)
                all_tools.extend(connector_tools)
        except Exception as e:
            logger.error("Failed to load connector tools", error=str(e))

        # Create subgraphs
        subgraphs = create_all_subgraphs(
            user_id=api_key,
            api_key=api_key,
            redis_storage=redis_storage,
            provider="sambanova",
            enable_data_science=False,
        )

        # Determine if we need vision model (check if input_content is a list with images)
        use_vision_model = isinstance(input_content, list) and any(
            item.get("type") == "image_url" for item in input_content if isinstance(item, dict)
        )

        # Configure agent with appropriate model
        llm_type = LLMType.SN_LLAMA_MAVERICK if use_vision_model else LLMType.SN_DEEPSEEK_V3

        agent = enhanced_agent.with_config(
            configurable={
                "llm_type": llm_type,
                "type==default/system_message": "You are a helpful AI assistant. You can help with general questions, coding tasks, financial analysis, deep research, and data science.",
                "type==default/tools": all_tools,
                "type==default/subgraphs": subgraphs,
                "type==default/user_id": api_key,
            }
        )

        config = {
            "configurable": {
                "thread_id": thread_id,
                "api_key": api_key,
            },
            "metadata": {
                "user_id": api_key,
                "thread_id": thread_id,
                "message_id": str(uuid.uuid4()),
            }
        }

        # Handle streaming vs non-streaming
        if response_request.stream:
            # Return SSE stream
            return StreamingResponse(
                _stream_agent_with_auto_resume(
                    agent=agent,
                    initial_input=[HumanMessage(content=input_content)],
                    config=config,
                    thread_id=thread_id,
                    response_id=response_id,
                    model=response_request.model,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            # Non-streaming response
            created_timestamp = int(time.time())

            result = await _execute_agent_with_auto_resume(
                agent=agent,
                initial_input=[HumanMessage(content=input_content)],
                config=config,
                thread_id=thread_id,
            )

            # Extract text from messages and artifacts
            # Result can be either a list of messages or a dict with "messages" key
            output_text = ""
            artifacts = []
            messages_list = []

            if result:
                if isinstance(result, list):
                    # LangGraph astream returns list of messages directly
                    messages_list = result
                elif isinstance(result, dict) and "messages" in result:
                    # Some graphs return dict with messages key
                    messages_list = result["messages"]

                if messages_list:
                    logger.info(
                        "Extracting text from messages",
                        message_count=len(messages_list),
                        message_types=[type(m).__name__ for m in messages_list]
                    )
                    output_text = _extract_text_from_messages(messages_list)

                    # Extract artifacts from messages (same as agent.py)
                    for message in messages_list:
                        if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                            files = message.additional_kwargs.get('files', [])
                            if files:
                                for file in files:
                                    if file not in artifacts:
                                        artifacts.append(file)

                    logger.info(
                        "Extracted text and artifacts",
                        output_length=len(output_text),
                        artifacts_count=len(artifacts),
                        output_preview=output_text[:200] if output_text else "EMPTY"
                    )

            # Build response object with artifacts in metadata (custom extension)
            metadata = {"thread_id": thread_id}
            if artifacts:
                metadata["artifacts"] = artifacts

            response_obj = ResponseObject(
                id=response_id,
                object="response",
                created=created_timestamp,
                model=response_request.model,
                status=ResponseStatus.COMPLETED,
                output=[
                    ResponseOutputText(
                        type="text",
                        text=output_text
                    )
                ],
                usage=ResponseUsage(
                    prompt_tokens=0,  # TODO: Calculate from tokenizer
                    completion_tokens=0,
                    total_tokens=0
                ),
                metadata=metadata
            )

            return response_obj

    except Exception as e:
        logger.error(
            "OpenAI API error",
            error=str(e),
            thread_id=thread_id,
            response_id=response_id,
            exc_info=True
        )
        error_response = create_error_response(
            message="An internal error occurred",
            error_type="server_error",
            code="internal_error"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump()
        )
