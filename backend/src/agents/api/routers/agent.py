import json
import uuid
from typing import Optional

from agents.components.compound.data_science_subgraph import (
    create_data_science_subgraph,
)
from agents.components.compound.financial_analysis_subgraph import (
    create_financial_analysis_graph,
)
from agents.components.compound.xml_agent import get_global_checkpointer
from agents.components.open_deep_research.graph import create_deep_research_graph
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
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


@router.post("/datascience")
async def datascience_agent(request: Request, api_key: str):
    agent = create_data_science_subgraph(
        user_id=request.app.state.user_id,
        sambanova_api_key=api_key,
        redis_storage=request.app.state.redis_storage_service,
        daytona_manager=request.app.state.daytona_manager,
        directory_content=[],
    )
    return JSONResponse(status_code=200, content={"message": "Hello, world!"})


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
            status_code=401,
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
                status_code=200,
                content={
                    "thread_id": thread_id,
                    "status": "completed",
                    "result": result_step2["final_report"],
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "thread_id": thread_id,
                "status": "error",
                "result": "Failed to get final report after auto-approval.",
                "details": result_step2,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
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
            status_code=401,
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
                    status_code=200,
                    content={
                        "thread_id": thread_id,
                        "status": "interrupted",
                        "result": interrupt_message,
                    },
                )
        elif "final_report" in result:
            return JSONResponse(
                status_code=200,
                content={
                    "thread_id": thread_id,
                    "status": "completed",
                    "result": result["final_report"],
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "thread_id": thread_id,
                "status": "completed",
                "result": "Unable to extract results from the graph",
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "thread_id": thread_id,
                "status": "error",
                "error": str(e),
            },
        )


@router.post("/compound")
async def compound_agent(request: Request, api_key: str):
    from agents.components.compound.agent import enhanced_agent

    agent = enhanced_agent(
        api_key=api_key,
        provider="sambanova",
        request_timeout=120,
        redis_storage=request.app.state.redis_storage_service,
        user_id=request.app.state.user_id,
    )
    return JSONResponse(status_code=200, content={"message": "Hello, world!"})


@router.post("/financialanalysis")
async def financialanalysis_agent(request: Request, api_key: str):
    agent = create_financial_analysis_graph(
        api_key=api_key,
        provider="sambanova",
        request_timeout=120,
        redis_storage=request.app.state.redis_storage_service,
        user_id=request.app.state.user_id,
    )
    return JSONResponse(status_code=200, content={"message": "Hello, world!"})
