import base64
import json
import re
import uuid
from typing import List, Optional

import markdown
import structlog
from agents.api.routers.upload import process_and_store_file, upload_document
from agents.api.utils import process_data_science_report
from agents.components.compound.data_science_subgraph import (
    create_data_science_subgraph,
)
from agents.components.compound.xml_agent import get_global_checkpointer
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.components.open_deep_research.graph import create_deep_research_graph
from agents.storage.redis_storage import RedisStorage
from agents.tools.langgraph_tools import load_static_tools
from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse, Response
from langchain_core.messages import HumanMessage
from langgraph.types import Command, Interrupt
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/agent",
)


class DeepResearchRequest(BaseModel):
    prompt: str


class DeepResearchInteractiveRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None
    resume: bool = False


class DataScienceInteractiveRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None
    resume: bool = False


@router.post("/datascience", tags=["Analysis"])
async def datascience_agent_and_report(
    request: Request,
    prompt: str = Form(..., description="The main prompt for the data science agent."),
    files: List[UploadFile] = File(
        ..., description="One or more files to be analyzed."
    ),
    authorization: Optional[str] = Header(
        None, description="Authorization header with Bearer token."
    ),
):
    """
    Fire-and-forget data science API.
    Submits a prompt and returns the final report in a single call.
    """
    # Extract API key from Authorization header (Bearer token)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token is required",
        )

    thread_id = str(uuid.uuid4())
    api_key = authorization.replace("Bearer ", "")

    try:
        file_ids = []
        file_names = []
        for file in files:
            file_info = await process_and_store_file(request, file, api_key)
            file_ids.append(file_info["file_id"])
            file_names.append(file_info["filename"])

        checkpointer = get_global_checkpointer()
        daytona_manager = PersistentDaytonaManager(
            user_id=api_key,
            redis_storage=request.app.state.redis_storage_service,
            snapshot="data-analysis:0.0.10",
            file_ids=file_ids,
        )

        agent = create_data_science_subgraph(
            user_id=api_key,
            sambanova_api_key=api_key,
            redis_storage=request.app.state.redis_storage_service,
            daytona_manager=daytona_manager,
            directory_content=file_names,
            checkpointer=checkpointer,
        )
        results = await agent.ainvoke(
            {
                "internal_messages": [
                    HumanMessage(content=prompt, id=str(uuid.uuid4()))
                ],
                "hypothesis": "",
                "process": "",
                "process_decision": None,
                "visualization_state": "",
                "searcher_state": "",
                "code_state": "",
                "report_section": "",
                "quality_review": "",
                "needs_revision": False,
                "sender": "",
            },
            config={"configurable": {"thread_id": thread_id}},
        )
        graph_input_step2 = Command(resume="APPROVE")
        result_step2 = await agent.ainvoke(
            graph_input_step2,
            config={"configurable": {"thread_id": thread_id}},
        )
        markdown_report = result_step2["internal_messages"][-1].content
        files_from_report = result_step2["internal_messages"][-1].additional_kwargs.get(
            "files", []
        )
        final_html = await process_data_science_report(
            markdown_report,
            files_from_report,
            request.app.state.redis_storage_service,
            api_key,
        )

        return HTMLResponse(content=final_html, status_code=status.HTTP_200_OK)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


@router.post("/datascience/interactive")
async def datascience_interactive(
    request: Request,
    prompt: str = Form(...),
    authorization: Optional[str] = Header(None),
    resume: bool = Form(False),
    thread_id: Optional[str] = Form(None),
    files: Optional[List[UploadFile]] = File(None),
    file_ids_json: Optional[str] = Form(
        None, description="A JSON string of file IDs, required for resuming a session"
    ),
):
    """
    Two-step interactive data science API:
    Step 1: Submit prompt and files, get thread_id and hypothesis for approval.
    Step 2: Submit prompt with thread_id, file_ids_json, and resume=true to get the final report.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Bearer token is required",
        )
    api_key = authorization.replace("Bearer ", "")

    try:
        if not resume:
            # Step 1: Hypothesis Generation
            if not files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Files are required for the initial request.",
                )

            new_thread_id = str(uuid.uuid4())
            file_ids = []
            file_names = []
            for file in files:
                file_info = await process_and_store_file(request, file, api_key)
                file_ids.append(file_info["file_id"])
                file_names.append(file_info["filename"])

            checkpointer = get_global_checkpointer()
            daytona_manager = PersistentDaytonaManager(
                user_id=api_key,
                redis_storage=request.app.state.redis_storage_service,
                snapshot="data-analysis:0.0.10",
                file_ids=file_ids,
            )

            agent = create_data_science_subgraph(
                user_id=api_key,
                sambanova_api_key=api_key,
                redis_storage=request.app.state.redis_storage_service,
                daytona_manager=daytona_manager,
                directory_content=file_names,
                checkpointer=checkpointer,
            )

            result = await agent.ainvoke(
                {
                    "internal_messages": [
                        HumanMessage(content=prompt, id=str(uuid.uuid4()))
                    ],
                    "hypothesis": "",
                    "process": "",
                    "process_decision": None,
                    "visualization_state": "",
                    "searcher_state": "",
                    "code_state": "",
                    "report_section": "",
                    "quality_review": "",
                    "needs_revision": False,
                    "sender": "",
                },
                config={"configurable": {"thread_id": new_thread_id}},
            )

            # Manually stop sandbox
            await daytona_manager.cleanup()

            if "__interrupt__" in result and len(result["__interrupt__"]) > 0:
                interrupt_message = result["__interrupt__"][0]
                if isinstance(interrupt_message, Interrupt):
                    interrupt_message = interrupt_message.value
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content={
                            "thread_id": new_thread_id,
                            "file_ids": file_ids,
                            "status": "interrupted",
                            "result": interrupt_message,
                        },
                    )

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "thread_id": new_thread_id,
                    "status": "completed",
                    "result": "Unable to extract hypothesis from the graph",
                },
            )
        else:
            # Step 2: Execution and Reporting
            if not thread_id or not file_ids_json:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="thread_id and file_ids_json are required for resuming.",
                )

            file_ids = json.loads(file_ids_json)
            # We need file_names, but they are not passed from step 1.
            # For now, let's retrieve them, but this is inefficient.
            # A better solution would be to store them or pass them along.
            file_names = []
            for file_id in file_ids:
                _, metadata = await request.app.state.redis_storage_service.get_file(
                    api_key, file_id
                )
                file_names.append(metadata["filename"])

            checkpointer = get_global_checkpointer()
            daytona_manager = PersistentDaytonaManager(
                user_id=api_key,
                redis_storage=request.app.state.redis_storage_service,
                snapshot="data-analysis:0.0.10",
                file_ids=file_ids,
            )

            agent = create_data_science_subgraph(
                user_id=api_key,
                sambanova_api_key=api_key,
                redis_storage=request.app.state.redis_storage_service,
                daytona_manager=daytona_manager,
                directory_content=file_names,
                checkpointer=checkpointer,
            )

            graph_input_step2 = Command(resume=prompt)
            result_step2 = await agent.ainvoke(
                graph_input_step2,
                config={"configurable": {"thread_id": thread_id}},
            )

            # User decided to revise graph
            if (
                "__interrupt__" in result_step2
                and len(result_step2["__interrupt__"]) > 0
            ):
                # Manually stop sandbox
                await daytona_manager.cleanup()
                interrupt_message = result_step2["__interrupt__"][0]
                if isinstance(interrupt_message, Interrupt):
                    interrupt_message = interrupt_message.value
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content={
                            "thread_id": thread_id,
                            "file_ids": file_ids,
                            "status": "interrupted",
                            "result": interrupt_message,
                        },
                    )

            markdown_report = result_step2["internal_messages"][-1].content
            files_from_report = result_step2["internal_messages"][
                -1
            ].additional_kwargs.get("files", [])

            final_html = await process_data_science_report(
                markdown_report,
                files_from_report,
                request.app.state.redis_storage_service,
                api_key,
            )

            return HTMLResponse(content=final_html, status_code=status.HTTP_200_OK)

    except Exception as e:
        error_content = {
            "status": "error",
            "error": str(e),
        }
        if thread_id:
            error_content["thread_id"] = thread_id
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_content,
        )


@router.post("/deepresearch")
async def deepresearch_agent(
    request: Request,
    research_request: DeepResearchRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Fire-and-forget deep research API.
    Submits a prompt and returns the final report in a single call.
    """
    # Extract API key from Authorization header (Bearer token)
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    api_key = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service
    checkpointer = get_global_checkpointer()

    # Create and execute the deep research graph
    agent = create_deep_research_graph(
        api_key=api_key,
        provider="sambanova",
        request_timeout=120,
        redis_storage=redis_storage,
        user_id=api_key,
        checkpointer=checkpointer,
    )

    thread_id = str(uuid.uuid4())
    try:
        # Step 1: Initial call
        graph_input_step1 = {"topic": research_request.prompt}
        await agent.ainvoke(
            graph_input_step1,
            config={"configurable": {"thread_id": thread_id}},
        )

        # Step 2: Auto-approve
        graph_input_step2 = Command(resume="APPROVE")
        result_step2 = await agent.ainvoke(
            graph_input_step2,
            config={"configurable": {"thread_id": thread_id}},
        )

        if "final_report" in result_step2:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "thread_id": thread_id,
                    "status": "completed",
                    "result": result_step2["final_report"],
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "result": "Failed to get final report after auto-approval.",
                "details": result_step2,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


@router.post("/deepresearch/interactive")
async def deepresearch_interactive_agent(
    request: Request,
    research_request: DeepResearchInteractiveRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Two-step interactive deep research API:
    Step 1: Submit prompt, get thread_id and research plan for approval.
    Step 2: Submit prompt with thread_id and resume=true to get the final report.
    """
    # Extract API key from Authorization header (Bearer token)
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    api_key = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service
    checkpointer = get_global_checkpointer()

    # Create and execute the deep research graph
    agent = create_deep_research_graph(
        api_key=api_key,
        provider="sambanova",
        request_timeout=120,
        redis_storage=redis_storage,
        user_id=api_key,
        checkpointer=checkpointer,
    )

    if research_request.resume is False:
        thread_id = str(uuid.uuid4())
    else:
        thread_id = research_request.thread_id

    try:
        if research_request.resume is False:
            graph_input = {"topic": research_request.prompt}
        else:
            if (
                research_request.prompt.lower() == "approve"
                or research_request.prompt.lower() == "true"
            ):
                graph_input = Command(resume="APPROVE")
            else:
                graph_input = Command(resume=research_request.prompt)

        result = await agent.ainvoke(
            graph_input,
            config={"configurable": {"thread_id": thread_id}},
        )
        if "__interrupt__" in result and len(result["__interrupt__"]) > 0:
            interrupt_message = result["__interrupt__"][0]
            if isinstance(interrupt_message, Interrupt):
                interrupt_message = interrupt_message.value
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "thread_id": thread_id,
                        "status": "interrupted",
                        "result": interrupt_message,
                    },
                )
        elif "final_report" in result:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "thread_id": thread_id,
                    "status": "completed",
                    "result": result["final_report"],
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "completed",
                "result": "Unable to extract results from the graph",
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


# ==================== MAIN AGENT API ====================


class MainAgentRequest(BaseModel):
    prompt: str


class MainAgentInteractiveRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None
    resume: bool = False


@router.post("/mainagent", tags=["Agents"])
async def main_agent(
    request: Request,
    agent_request: MainAgentRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Fire-and-forget main agent API.
    The main agent is a general-purpose AI assistant that can coordinate with subagents
    (coding, financial analysis, deep research, data science) to complete complex tasks.

    Submits a prompt and returns the final response in a single call.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    api_key = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service
    checkpointer = get_global_checkpointer()
    thread_id = str(uuid.uuid4())

    try:
        # Import here to avoid circular dependencies
        from agents.components.compound.agent import enhanced_agent
        from agents.components.compound.data_types import LLMType
        from agents.api.subgraph_factory import create_all_subgraphs

        # Load tools same way as websocket
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
                logger.info(
                    "Loaded connector tools for main agent API",
                    num_connector_tools=len(connector_tools),
                    total_tools=len(all_tools)
                )
        except Exception as e:
            logger.error("Failed to load connector tools", error=str(e))

        # Create all subgraphs for the main agent using centralized factory
        subgraphs = create_all_subgraphs(
            user_id=api_key,
            api_key=api_key,
            redis_storage=redis_storage,
            provider="sambanova",
            enable_data_science=False,  # No files uploaded in this API
        )

        # Configure and execute the main agent with correct config keys
        agent = enhanced_agent.with_config(
            configurable={
                "llm_type": LLMType.SN_DEEPSEEK_V3,
                "type==default/system_message": "You are a helpful AI assistant. You can help with general questions, coding tasks, financial analysis, deep research, and data science. When a user asks for something specific, you can delegate to specialized subagents.",
                "type==default/tools": all_tools,
                "type==default/subgraphs": subgraphs,
                "type==default/user_id": api_key,
            }
        )

        # Execute the agent using streaming (same as frontend websocket) to avoid truncation
        # Collect all streamed events and build the final result
        result = None
        graph_input = [HumanMessage(content=agent_request.prompt)]

        async for chunk in agent.astream(
            graph_input,
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "api_key": api_key,
                },
                "metadata": {
                    "user_id": api_key,
                    "thread_id": thread_id,
                    "message_id": str(uuid.uuid4()),
                }
            },
            stream_mode="values"
        ):
            result = chunk  # Keep updating with latest state

        # Handle deep research interrupts (auto-approve for fire-and-forget API)
        max_interrupt_retries = 3
        interrupt_retry = 0
        while result and "__interrupt__" in result and len(result.get("__interrupt__", [])) > 0 and interrupt_retry < max_interrupt_retries:
            interrupt_msg = result["__interrupt__"][0]
            interrupt_value = interrupt_msg.value if isinstance(interrupt_msg, Interrupt) else interrupt_msg

            # Check if this is a deep research interrupt (contains the plan approval prompt)
            if "provide feedback" in str(interrupt_value).lower() and "approve" in str(interrupt_value).lower():
                logger.info(
                    "Main agent API: Auto-approving deep research interrupt",
                    thread_id=thread_id,
                    retry=interrupt_retry
                )
                # Auto-approve and continue using streaming
                result = None
                async for chunk in agent.astream(
                    Command(resume="APPROVE"),
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "api_key": api_key,
                        },
                        "metadata": {
                            "user_id": api_key,
                            "thread_id": thread_id,
                            "message_id": str(uuid.uuid4()),
                        }
                    },
                    stream_mode="values"
                ):
                    result = chunk  # Keep updating with latest state
                interrupt_retry += 1
            else:
                # Unknown interrupt type, break out
                logger.warning(
                    "Main agent API: Unknown interrupt type, cannot auto-approve",
                    interrupt_msg=str(interrupt_value)[:200]
                )
                break

        # Extract the final message content and collect artifacts from ALL messages
        if result and len(result) > 0:
            final_message = result[-1]
            response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)

            # Collect artifacts from ALL messages in the conversation
            # Subgraphs (like DaytonaCodeSandbox) return files in their output messages
            artifacts = []
            for message in result:
                if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                    files = message.additional_kwargs.get('files', [])
                    if files:
                        # Avoid duplicates
                        for file in files:
                            if file not in artifacts:
                                artifacts.append(file)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "thread_id": thread_id,
                    "status": "completed",
                    "result": response_content,
                    "artifacts": artifacts,
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": "No response from agent",
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


@router.post("/mainagent/interactive", tags=["Agents"])
async def main_agent_interactive(
    request: Request,
    agent_request: MainAgentInteractiveRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Interactive main agent API for multi-turn conversations.
    The main agent is a general-purpose AI assistant that can coordinate with subagents
    (coding, financial analysis, deep research, data science) to complete complex tasks.

    Step 1: Submit prompt, get thread_id and initial response.
    Step 2: Continue conversation with thread_id and resume=true.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    api_key = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service
    checkpointer = get_global_checkpointer()

    if agent_request.resume is False:
        thread_id = str(uuid.uuid4())
    else:
        thread_id = agent_request.thread_id
        if not thread_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "thread_id is required when resume=true"},
            )

    try:
        # Import here to avoid circular dependencies
        from agents.components.compound.agent import enhanced_agent
        from agents.components.compound.data_types import LLMType
        from agents.api.subgraph_factory import create_all_subgraphs

        # Load tools same way as websocket
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
                logger.info(
                    "Loaded connector tools for main agent interactive API",
                    num_connector_tools=len(connector_tools),
                    total_tools=len(all_tools)
                )
        except Exception as e:
            logger.error("Failed to load connector tools", error=str(e))

        # Create all subgraphs for the main agent using centralized factory
        subgraphs = create_all_subgraphs(
            user_id=api_key,
            api_key=api_key,
            redis_storage=redis_storage,
            provider="sambanova",
            enable_data_science=False,  # No files uploaded in this API
        )

        # Configure and execute the main agent with correct config keys
        agent = enhanced_agent.with_config(
            configurable={
                "llm_type": LLMType.SN_DEEPSEEK_V3,
                "type==default/system_message": "You are a helpful AI assistant. You can help with general questions, coding tasks, financial analysis, deep research, and data science. When a user asks for something specific, you can delegate to specialized subagents.",
                "type==default/tools": all_tools,
                "type==default/subgraphs": subgraphs,
                "type==default/user_id": api_key,
            }
        )

        # Execute the agent using streaming (same as frontend websocket) to avoid truncation
        if agent_request.resume is False:
            # Initial request
            graph_input = [HumanMessage(content=agent_request.prompt)]
        else:
            # Continuing conversation - append new message
            graph_input = Command(resume=[HumanMessage(content=agent_request.prompt)])

        # Collect all streamed events and build the final result
        result = None
        async for chunk in agent.astream(
            graph_input,
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "api_key": api_key,
                },
                "metadata": {
                    "user_id": api_key,
                    "thread_id": thread_id,
                    "message_id": str(uuid.uuid4()),
                }
            },
            stream_mode="values"
        ):
            result = chunk  # Keep updating with latest state

        # Handle deep research interrupts (auto-approve for main agent API)
        max_interrupt_retries = 3
        interrupt_retry = 0
        while result and "__interrupt__" in result and len(result.get("__interrupt__", [])) > 0 and interrupt_retry < max_interrupt_retries:
            interrupt_msg = result["__interrupt__"][0]
            interrupt_value = interrupt_msg.value if isinstance(interrupt_msg, Interrupt) else interrupt_msg

            # Check if this is a deep research interrupt (contains the plan approval prompt)
            if "provide feedback" in str(interrupt_value).lower() and "approve" in str(interrupt_value).lower():
                logger.info(
                    "Main agent interactive API: Auto-approving deep research interrupt",
                    thread_id=thread_id,
                    retry=interrupt_retry
                )
                # Auto-approve and continue using streaming
                result = None
                async for chunk in agent.astream(
                    Command(resume="APPROVE"),
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "api_key": api_key,
                        },
                        "metadata": {
                            "user_id": api_key,
                            "thread_id": thread_id,
                            "message_id": str(uuid.uuid4()),
                        }
                    },
                    stream_mode="values"
                ):
                    result = chunk  # Keep updating with latest state
                interrupt_retry += 1
            else:
                # Unknown interrupt type, break out
                logger.warning(
                    "Main agent interactive API: Unknown interrupt type, cannot auto-approve",
                    interrupt_msg=str(interrupt_value)[:200]
                )
                break

        # Check for interrupts (if the agent needs user input)
        if "__interrupt__" in result and len(result["__interrupt__"]) > 0:
            interrupt_message = result["__interrupt__"][0]
            if isinstance(interrupt_message, Interrupt):
                interrupt_message = interrupt_message.value
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "thread_id": thread_id,
                    "status": "interrupted",
                    "result": interrupt_message,
                },
            )

        # Extract the final message content and collect artifacts from ALL messages
        if result and len(result) > 0:
            final_message = result[-1]
            response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)

            # Collect artifacts from ALL messages in the conversation
            # Subgraphs (like DaytonaCodeSandbox) return files in their output messages
            artifacts = []
            for message in result:
                if hasattr(message, 'additional_kwargs') and message.additional_kwargs:
                    files = message.additional_kwargs.get('files', [])
                    if files:
                        # Avoid duplicates
                        for file in files:
                            if file not in artifacts:
                                artifacts.append(file)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "thread_id": thread_id,
                    "status": "completed",
                    "result": response_content,
                    "artifacts": artifacts,
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "completed",
                "result": "Unable to extract results from the agent",
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )

# ==================== CODING AGENT API ====================


class CodingAgentRequest(BaseModel):
    prompt: str
    code: str


class CodingAgentInteractiveRequest(BaseModel):
    prompt: str
    code: str
    thread_id: Optional[str] = None
    resume: bool = False


@router.post("/coding", tags=["Agents"])
async def coding_agent(
    request: Request,
    agent_request: CodingAgentRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Fire-and-forget coding agent API.
    The coding agent can execute Python code in a sandbox environment, fix errors, and provide results.

    Submits code with an optional prompt and returns the execution result in a single call.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    api_key = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service
    thread_id = str(uuid.uuid4())

    try:
        # Import here to avoid circular dependencies
        from agents.components.compound.code_execution_subgraph import create_code_execution_graph
        from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager

        # Create Daytona manager for code execution
        daytona_manager = PersistentDaytonaManager(
            user_id=api_key,
            redis_storage=redis_storage,
            snapshot="data-analysis:0.0.10",
            file_ids=[],
        )

        # Create code execution graph
        code_graph = create_code_execution_graph(
            user_id=api_key,
            sambanova_api_key=api_key,
            redis_storage=redis_storage,
            daytona_manager=daytona_manager,
        )

        # Execute the code
        result = await code_graph.ainvoke(
            {
                "code": agent_request.code,
                "steps_taken": [],
                "error_detected": False,
                "corrections_proposed": [],
                "current_retry": 0,
                "max_retries": 3,
                "messages": [],
                "search_context": None,
                "additional_packages": [],
                "installation_successful": True,
                "search_query": None,
                "correction_feedback": None,
                "files": [],
            },
            config={
                "configurable": {"thread_id": thread_id},
                "metadata": {
                    "user_id": api_key,
                    "thread_id": thread_id,
                    "message_id": str(uuid.uuid4()),
                }
            },
        )

        # Extract results
        steps_taken = result.get("steps_taken", [])
        files = result.get("files", [])

        # Format the response
        response_content = "\n\n".join(steps_taken) if steps_taken else "Code execution completed."

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "thread_id": thread_id,
                "status": "completed",
                "result": response_content,
                "artifacts": files,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


@router.post("/coding/interactive", tags=["Agents"])
async def coding_agent_interactive(
    request: Request,
    agent_request: CodingAgentInteractiveRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Interactive coding agent API for iterative code development.
    The coding agent can execute Python code in a sandbox environment, fix errors, and provide results.

    Step 1: Submit code with prompt, get thread_id and execution result.
    Step 2: Continue with thread_id and resume=true to iterate on code.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    api_key = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service

    if agent_request.resume is False:
        thread_id = str(uuid.uuid4())
    else:
        thread_id = agent_request.thread_id
        if not thread_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "thread_id is required when resume=true"},
            )

    try:
        # Import here to avoid circular dependencies
        from agents.components.compound.code_execution_subgraph import create_code_execution_graph
        from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager

        # Create Daytona manager for code execution
        daytona_manager = PersistentDaytonaManager(
            user_id=api_key,
            redis_storage=redis_storage,
            snapshot="data-analysis:0.0.10",
            file_ids=[],
        )

        # Create code execution graph
        code_graph = create_code_execution_graph(
            user_id=api_key,
            sambanova_api_key=api_key,
            redis_storage=redis_storage,
            daytona_manager=daytona_manager,
        )

        # Execute the code
        result = await code_graph.ainvoke(
            {
                "code": agent_request.code,
                "steps_taken": [],
                "error_detected": False,
                "corrections_proposed": [],
                "current_retry": 0,
                "max_retries": 3,
                "messages": [],
                "search_context": None,
                "additional_packages": [],
                "installation_successful": True,
                "search_query": None,
                "correction_feedback": None,
                "files": [],
            },
            config={
                "configurable": {"thread_id": thread_id},
                "metadata": {
                    "user_id": api_key,
                    "thread_id": thread_id,
                    "message_id": str(uuid.uuid4()),
                }
            },
        )

        # Extract results
        steps_taken = result.get("steps_taken", [])
        files = result.get("files", [])

        # Format the response
        response_content = "\n\n".join(steps_taken) if steps_taken else "Code execution completed."

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "thread_id": thread_id,
                "status": "completed",
                "result": response_content,
                "artifacts": files,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


# ==================== FINANCIAL ANALYSIS AGENT API ====================


class FinancialAnalysisRequest(BaseModel):
    prompt: str


class FinancialAnalysisInteractiveRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None
    resume: bool = False


@router.post("/financialanalysis", tags=["Agents"])
async def financial_analysis_agent(
    request: Request,
    agent_request: FinancialAnalysisRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Fire-and-forget financial analysis agent API.
    The financial analysis agent can analyze stocks, companies, and financial data.

    Submits a prompt and returns the financial analysis report in a single call.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    api_key = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service
    thread_id = str(uuid.uuid4())

    try:
        # Import here to avoid circular dependencies
        from agents.components.compound.financial_analysis_subgraph import create_financial_analysis_graph

        # Create financial analysis graph
        financial_graph = create_financial_analysis_graph(
            redis_client=redis_storage,
            user_id=api_key,
        )

        # Execute the analysis
        result = await financial_graph.ainvoke(
            [HumanMessage(content=agent_request.prompt)],
            config={
                "configurable": {"thread_id": thread_id, "api_key": api_key},
                "metadata": {
                    "user_id": api_key,
                    "thread_id": thread_id,
                    "message_id": str(uuid.uuid4()),
                }
            },
        )

        # Extract the final message content
        if result and len(result) > 0:
            final_message = result[-1]

            # Handle the JSON content from financial analysis
            import json as json_module
            if hasattr(final_message, 'content'):
                try:
                    # The content is a JSON string, parse it
                    content_data = json_module.loads(final_message.content)
                    response_content = json_module.dumps(content_data, indent=2)
                except (json_module.JSONDecodeError, TypeError):
                    # If it's not JSON, use as-is
                    response_content = final_message.content
            else:
                response_content = str(final_message)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "thread_id": thread_id,
                    "status": "completed",
                    "result": response_content,
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": "No response from financial analysis agent",
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


@router.post("/financialanalysis/interactive", tags=["Agents"])
async def financial_analysis_agent_interactive(
    request: Request,
    agent_request: FinancialAnalysisInteractiveRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Interactive financial analysis agent API for follow-up questions.
    The financial analysis agent can analyze stocks, companies, and financial data.

    Step 1: Submit prompt, get thread_id and initial analysis.
    Step 2: Continue with thread_id and resume=true for follow-up questions.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    api_key = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service

    if agent_request.resume is False:
        thread_id = str(uuid.uuid4())
    else:
        thread_id = agent_request.thread_id
        if not thread_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "thread_id is required when resume=true"},
            )

    try:
        # Import here to avoid circular dependencies
        from agents.components.compound.financial_analysis_subgraph import create_financial_analysis_graph

        # Create financial analysis graph
        financial_graph = create_financial_analysis_graph(
            redis_client=redis_storage,
            user_id=api_key,
        )

        # Execute the analysis
        result = await financial_graph.ainvoke(
            [HumanMessage(content=agent_request.prompt)],
            config={
                "configurable": {"thread_id": thread_id, "api_key": api_key},
                "metadata": {
                    "user_id": api_key,
                    "thread_id": thread_id,
                    "message_id": str(uuid.uuid4()),
                }
            },
        )

        # Extract the final message content
        if result and len(result) > 0:
            final_message = result[-1]

            # Handle the JSON content from financial analysis
            import json as json_module
            if hasattr(final_message, 'content'):
                try:
                    # The content is a JSON string, parse it
                    content_data = json_module.loads(final_message.content)
                    response_content = json_module.dumps(content_data, indent=2)
                except (json_module.JSONDecodeError, TypeError):
                    # If it's not JSON, use as-is
                    response_content = final_message.content
            else:
                response_content = str(final_message)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "thread_id": thread_id,
                    "status": "completed",
                    "result": response_content,
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": "No response from financial analysis agent",
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


# ==================== FILE DOWNLOAD API ====================


@router.get("/files/{file_id}", tags=["Agents"])
async def download_agent_file(
    request: Request,
    file_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Download a file generated by an agent using Bearer token authentication.
    This endpoint allows API users to download files (artifacts) returned by agent APIs.
    
    Security: Files are scoped to users - you can only download your own files.
    The storage layer verifies file ownership before returning data.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Authorization header with Bearer token is required"},
        )

    # The API key IS the user_id in the agent system
    user_id = authorization.replace("Bearer ", "")
    redis_storage = request.app.state.redis_storage_service

    try:
        # Get file from Redis storage with ownership verification
        # This call internally verifies the file belongs to this user_id
        file_data, file_metadata = await redis_storage.get_file(user_id, file_id)

        if not file_data or not file_metadata:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": "File not found or access denied"},
            )

        # Return the file with appropriate headers
        return Response(
            content=file_data,
            media_type=file_metadata.get("format", "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="{file_metadata.get("filename", file_id)}"'
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Error downloading file: {str(e)}"},
        )
