from agents.components.compound.data_science_subgraph import (
    create_data_science_subgraph,
)
from agents.components.compound.financial_analysis_subgraph import create_financial_analysis_graph
from agents.components.open_deep_research.graph import create_deep_research_graph
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(
    prefix="/agents",
)


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
async def deepresearch_agent(request: Request, api_key: str):
    agent = create_deep_research_graph(
        api_key=api_key,
        provider="sambanova",
        request_timeout=120,
        redis_storage=request.app.state.redis_storage_service,
        user_id=request.app.state.user_id,
    )
    return JSONResponse(status_code=200, content={"message": "Hello, world!"})


@router.post("/compound")
async def compound_agent(request: Request, api_key: str):
    from agents.components.compound.agent import enhanced_agent
    agent = ...
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