import base64
import json
import re
import uuid
from typing import List, Optional

import markdown
from agents.api.routers.upload import process_and_store_file, upload_document
from agents.api.utils import process_data_science_report
from agents.components.compound.data_science_subgraph import (
    create_data_science_subgraph,
)
from agents.components.compound.xml_agent import get_global_checkpointer
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.components.open_deep_research.graph import create_deep_research_graph
from agents.storage.redis_storage import RedisStorage
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
from fastapi.responses import HTMLResponse, JSONResponse
from langchain_core.messages import HumanMessage
from langgraph.types import Command, Interrupt
from pydantic import BaseModel

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
        provider="groq",
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
        provider="groq",
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
