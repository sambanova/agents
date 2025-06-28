import asyncio
import html
import mimetypes
import os
import re
import time
import uuid
from enum import Enum
from functools import lru_cache
from typing import Annotated, Literal, Tuple

import redis
import structlog
from agents.rag.upload import RedisHybridRetriever, create_user_vector_store
from agents.storage.redis_storage import RedisStorage
from agents.utils.code_validator import (
    patch_plot_code_str,
    strip_markdown_code_blocks,
    validate_and_fix_html_content,
)
from daytona_sdk import AsyncDaytona as DaytonaClient
from daytona_sdk import CreateSandboxFromSnapshotParams
from daytona_sdk import DaytonaConfig as DaytonaSDKConfig
from langchain.tools.retriever import create_retriever_tool
from langchain_community.agent_toolkits.connery import ConneryToolkit
from langchain_community.retrievers.kay import KayAiRetriever
from langchain_community.retrievers.pubmed import PubMedRetriever
from langchain_community.retrievers.wikipedia import WikipediaRetriever
from langchain_community.retrievers.you import YouRetriever
from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.tools.connery import ConneryService
from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchRun
from langchain_community.tools.tavily_search import TavilyAnswer as _TavilyAnswer
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from langchain_core.tools import Tool
from pydantic import BaseModel, ConfigDict, Field
from redisvl.query.filter import Tag
from typing_extensions import TypedDict

logger = structlog.get_logger(__name__)


class DDGInput(BaseModel):
    query: Annotated[str, Field(description="search query to look up")]


class ArxivInput(BaseModel):
    query: Annotated[str, Field(description="search query to look up")]


class PythonREPLInput(BaseModel):
    query: Annotated[str, Field(description="python command to run")]


class DallEInput(BaseModel):
    query: Annotated[str, Field(description="image description to generate image from")]


class AvailableTools(str, Enum):
    ACTION_SERVER = "action_server_by_sema4ai"
    CONNERY = "ai_action_runner_by_connery"
    DDG_SEARCH = "ddg_search"
    TAVILY = "search_tavily"
    TAVILY_ANSWER = "search_tavily_answer"
    RETRIEVAL = "retrieval"
    ARXIV = "arxiv"
    YOU_SEARCH = "you_search"
    SEC_FILINGS = "sec_filings_kai_ai"
    PRESS_RELEASES = "press_releases_kai_ai"
    PUBMED = "pubmed"
    WIKIPEDIA = "wikipedia"
    DALL_E = "dall_e"
    DAYTONA = "daytona"


class ToolConfig(TypedDict): ...


class DaytonaConfig(ToolConfig):
    user_id: str
    redis_storage: RedisStorage


class RetrievalConfig(ToolConfig):
    user_id: str
    doc_ids: tuple
    description: str
    api_key: str
    redis_client: redis.Redis


class BaseTool(BaseModel):

    model_config = ConfigDict(arbitrary_types_allowed=True)

    type: AvailableTools
    name: str
    description: str
    config: ToolConfig = Field(default_factory=dict)
    multi_use: bool = False


class ActionServerConfig(ToolConfig):
    url: str
    api_key: str


class ActionServer(BaseTool):
    type: Literal[AvailableTools.ACTION_SERVER] = AvailableTools.ACTION_SERVER
    name: Literal["Action Server by Sema4.ai"] = "Action Server by Sema4.ai"
    description: Literal[
        (
            "Run AI actions with "
            "[Sema4.ai Action Server](https://github.com/Sema4AI/actions)."
        )
    ] = (
        "Run AI actions with "
        "[Sema4.ai Action Server](https://github.com/Sema4AI/actions)."
    )
    config: ActionServerConfig
    multi_use: Literal[True] = True


class Connery(BaseTool):
    type: Literal[AvailableTools.CONNERY] = AvailableTools.CONNERY
    name: Literal["AI Action Runner by Connery"] = "AI Action Runner by Connery"
    description: Literal[
        (
            "Connect OpenGPTs to the real world with "
            "[Connery](https://github.com/connery-io/connery)."
        )
    ] = (
        "Connect OpenGPTs to the real world with "
        "[Connery](https://github.com/connery-io/connery)."
    )


class DDGSearch(BaseTool):
    type: Literal[AvailableTools.DDG_SEARCH] = AvailableTools.DDG_SEARCH
    name: Literal["DuckDuckGo Search"] = "DuckDuckGo Search"
    description: Literal[
        "Search the web with [DuckDuckGo](https://pypi.org/project/duckduckgo-search/)."
    ] = "Search the web with [DuckDuckGo](https://pypi.org/project/duckduckgo-search/)."


class Arxiv(BaseTool):
    type: Literal[AvailableTools.ARXIV] = AvailableTools.ARXIV
    name: Literal["Arxiv"] = "Arxiv"
    description: Literal["Searches [Arxiv](https://arxiv.org/)."] = (
        "Searches [Arxiv](https://arxiv.org/)."
    )


class YouSearch(BaseTool):
    type: Literal[AvailableTools.YOU_SEARCH] = AvailableTools.YOU_SEARCH
    name: Literal["You.com Search"] = "You.com Search"
    description: Literal[
        "Uses [You.com](https://you.com/) search, optimized responses for LLMs."
    ] = "Uses [You.com](https://you.com/) search, optimized responses for LLMs."


class SecFilings(BaseTool):
    type: Literal[AvailableTools.SEC_FILINGS] = AvailableTools.SEC_FILINGS
    name: Literal["SEC Filings (Kay.ai)"] = "SEC Filings (Kay.ai)"
    description: Literal[
        "Searches through SEC filings using [Kay.ai](https://www.kay.ai/)."
    ] = "Searches through SEC filings using [Kay.ai](https://www.kay.ai/)."


class PressReleases(BaseTool):
    type: Literal[AvailableTools.PRESS_RELEASES] = AvailableTools.PRESS_RELEASES
    name: Literal["Press Releases (Kay.ai)"] = "Press Releases (Kay.ai)"
    description: Literal[
        "Searches through press releases using [Kay.ai](https://www.kay.ai/)."
    ] = "Searches through press releases using [Kay.ai](https://www.kay.ai/)."


class PubMed(BaseTool):
    type: Literal[AvailableTools.PUBMED] = AvailableTools.PUBMED
    name: Literal["PubMed"] = "PubMed"
    description: Literal["Searches [PubMed](https://pubmed.ncbi.nlm.nih.gov/)."] = (
        "Searches [PubMed](https://pubmed.ncbi.nlm.nih.gov/)."
    )


class Wikipedia(BaseTool):
    type: Literal[AvailableTools.WIKIPEDIA] = AvailableTools.WIKIPEDIA
    name: Literal["Wikipedia"] = "Wikipedia"
    description: Literal[
        "Searches [Wikipedia](https://pypi.org/project/wikipedia/)."
    ] = "Searches [Wikipedia](https://pypi.org/project/wikipedia/)."


class Tavily(BaseTool):
    type: Literal[AvailableTools.TAVILY] = AvailableTools.TAVILY
    name: Literal["Search (Tavily)"] = "Search (Tavily)"
    description: Literal[
        (
            "Uses the [Tavily](https://app.tavily.com/) search engine. "
            "Includes sources in the response."
        )
    ] = (
        "Uses the [Tavily](https://app.tavily.com/) search engine. "
        "Includes sources in the response."
    )


class TavilyAnswer(BaseTool):
    type: Literal[AvailableTools.TAVILY_ANSWER] = AvailableTools.TAVILY_ANSWER
    name: Literal["Search (short answer, Tavily)"] = "Search (short answer, Tavily)"
    description: Literal[
        (
            "Uses the [Tavily](https://app.tavily.com/) search engine. "
            "This returns only the answer, no supporting evidence."
        )
    ] = (
        "Uses the [Tavily](https://app.tavily.com/) search engine. "
        "This returns only the answer, no supporting evidence."
    )


class Retrieval(BaseTool):
    type: Literal[AvailableTools.RETRIEVAL] = AvailableTools.RETRIEVAL
    name: Literal["Retrieval"] = "Retrieval"
    description: Literal["Look up information in uploaded files."] = (
        "Look up information in uploaded files."
    )
    config: RetrievalConfig


class DallE(BaseTool):
    type: Literal[AvailableTools.DALL_E] = AvailableTools.DALL_E
    name: Literal["Generate Image (Dall-E)"] = "Generate Image (Dall-E)"
    description: Literal[
        "Generates images from a text description using OpenAI's DALL-E model."
    ] = "Generates images from a text description using OpenAI's DALL-E model."


class Daytona(BaseTool):
    type: Literal[AvailableTools.DAYTONA] = AvailableTools.DAYTONA
    name: Literal["Daytona Code Sandbox"] = "Daytona Code Sandbox"
    description: Literal["Executes Python code in a secure sandbox environment."] = (
        "Executes Python code in a secure sandbox environment."
    )
    config: DaytonaConfig


RETRIEVAL_DESCRIPTION = """Can be used to look up information that was uploaded to this assistant.
If the user is referencing particular files, that is often a good hint that information may be here.
If the user asks a vague question, they are likely meaning to look up info from this retriever, and you should call it!"""


def _get_retrieval_tool(
    user_id: str,
    doc_ids: Tuple[str, ...],
    api_key: str,
    description: str,
    redis_client: redis.Redis,
):
    """
    Returns a LangChain Tool that does true hybrid (keyword + vector) search
    filtered by user_id and document_id tags.
    """

    vector_store = create_user_vector_store(api_key, redis_client)

    user_filter = Tag("user_id") == user_id
    doc_filter = Tag("document_id") == list(doc_ids)
    filter_expr = user_filter & doc_filter

    retriever = RedisHybridRetriever(
        search_index=vector_store._index,
        embedding_model=vector_store._embeddings,
        filter_expr=filter_expr,
    )

    return create_retriever_tool(
        retriever=retriever,
        name="Retriever",
        description=description,
    )


@lru_cache(maxsize=5)
def _get_retrieval_tool_mmr(
    user_id: str, doc_ids: tuple, api_key: str, description: str
):
    from agents.rag.upload import create_user_vector_store
    from redisvl.query.filter import Tag

    user_filter = Tag("user_id") == user_id
    doc_filter = Tag("document_id") == list(doc_ids)
    filter_expr = user_filter & doc_filter

    return create_retriever_tool(
        create_user_vector_store(api_key).as_retriever(
            search_type="mmr",
            search_kwargs={
                "filter": filter_expr,
                "k": 10,
                "fetch_k": 50,
                "lambda_mult": 0.3,
            },
        ),
        "Retriever",
        description,
    )


@lru_cache(maxsize=1)
def _get_duck_duck_go():
    return DuckDuckGoSearchRun(args_schema=DDGInput)


@lru_cache(maxsize=1)
def _get_arxiv():
    return ArxivQueryRun(api_wrapper=ArxivAPIWrapper(), args_schema=ArxivInput)


@lru_cache(maxsize=1)
def _get_you_search():
    return create_retriever_tool(
        YouRetriever(n_hits=3, n_snippets_per_hit=3),
        "you_search",
        "Searches for documents using You.com",
    )


@lru_cache(maxsize=1)
def _get_sec_filings():
    return create_retriever_tool(
        KayAiRetriever.create(
            dataset_id="company", data_types=["10-K", "10-Q"], num_contexts=3
        ),
        "sec_filings_search",
        "Search for a query among SEC Filings",
    )


@lru_cache(maxsize=1)
def _get_press_releases():
    return create_retriever_tool(
        KayAiRetriever.create(
            dataset_id="company", data_types=["PressRelease"], num_contexts=6
        ),
        "press_release_search",
        "Search for a query among press releases from US companies",
    )


@lru_cache(maxsize=1)
def _get_pubmed():
    return create_retriever_tool(
        PubMedRetriever(), "pub_med_search", "Search for a query on PubMed"
    )


@lru_cache(maxsize=1)
def _get_wikipedia():
    return create_retriever_tool(
        WikipediaRetriever(), "wikipedia", "Search for a query on Wikipedia"
    )


@lru_cache(maxsize=1)
def _get_tavily():
    tavily_search = TavilySearchAPIWrapper()
    return TavilySearchResults(api_wrapper=tavily_search, name="search_tavily")


@lru_cache(maxsize=1)
def _get_tavily_answer():
    tavily_search = TavilySearchAPIWrapper()
    return _TavilyAnswer(api_wrapper=tavily_search, name="search_tavily_answer")


@lru_cache(maxsize=1)
def _get_connery_actions():
    connery_service = ConneryService()
    connery_toolkit = ConneryToolkit.create_instance(connery_service)
    tools = connery_toolkit.get_tools()
    return tools


@lru_cache(maxsize=1)
def _get_dalle_tools():
    return Tool(
        "Dall-E-Image-Generator",
        DallEAPIWrapper(size="1024x1024", quality="hd").run,
        "A wrapper around OpenAI DALL-E API. Useful for when you need to generate images from a text description. Input should be an image description.",
    )


@lru_cache(maxsize=1)
def _get_daytona(user_id: str, redis_storage: RedisStorage):
    api_key = os.getenv("DAYTONA_API_KEY")

    supported_extensions = [
        "image/png",
        "image/jpg",
        "image/jpeg",
        "image/gif",
        "image/svg",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/html",
        "text/markdown",
        "text/plain",
        "text/csv",
    ]
    images_formats = ["image/png", "image/jpg", "image/jpeg", "image/gif", "image/svg"]

    async def async_run_daytona_code(code_to_run: str) -> str:
        try:
            config = DaytonaSDKConfig(api_key=api_key)
            daytona = DaytonaClient(config)

            params = CreateSandboxFromSnapshotParams(
                snapshot="data-analysis:0.0.8",
            )

            # Strip markdown formatting before processing
            clean_code = strip_markdown_code_blocks(code_to_run)

            # Validate the cleaned code
            if not clean_code or len(clean_code.strip()) < 3:
                return "Error: No valid code found after processing input. Please provide valid Python code."

            # Enhanced logging for debugging
            logger.info(
                "Processing code for execution",
                original_length=len(code_to_run),
                cleaned_length=len(clean_code),
                first_100_chars=clean_code[:100],
            )

            patched_code, expected_filenames = patch_plot_code_str(clean_code)
            sandbox = await daytona.create(params=params)
            list_of_files = [f.name for f in await sandbox.fs.list_files(".")]

            # Execute the code with timeout and error handling
            try:
                response = await sandbox.process.code_run(patched_code)
            except Exception as exec_error:
                await daytona.close()
                logger.error(
                    "Code execution failed in sandbox",
                    error=str(exec_error),
                    exc_info=True,
                )
                return f"Error during code execution: {str(exec_error)}"

            # Ensure result is a string, even if None or other types
            result_str = str(response.result) if response.result is not None else ""

            if response.exit_code != 0:
                # Ensure error detail is a string
                await daytona.close()
                error_detail = result_str
                logger.error(
                    "Daytona code execution failed",
                    exit_code=response.exit_code,
                    error_detail=error_detail,
                    original_code_preview=code_to_run[:200],
                )
                return f"Error (Exit Code {response.exit_code}): {error_detail}"

            # Debug: Check what we got from the response
            logger.info(
                "Daytona response",
                exit_code=response.exit_code,
                result_preview=str(response.result)[:500],
                artifacts=response.artifacts,
            )

            generation_timestamp = time.time()

            # Process expected filenames first
            for filename in expected_filenames:
                mime_type, _ = mimetypes.guess_type(filename)
                try:
                    file_id = str(uuid.uuid4())
                    content = await sandbox.fs.download_file(filename)
                    logger.info(
                        "Downloaded file from sandbox",
                        filename=filename,
                        size_bytes=len(content),
                    )

                    # Store in Redis for backup/download purposes
                    if redis_storage:
                        await redis_storage.put_file(
                            user_id,
                            file_id,
                            data=content,
                            filename=filename,
                            format=mime_type,
                            upload_timestamp=generation_timestamp,
                            indexed=False,
                            source="daytona",
                        )

                    # For image files, use compact Redis references instead of data URLs
                    if mime_type in images_formats:
                        result_str += (
                            f"\n\n![{filename}](redis-chart:{file_id}:{user_id})"
                        )
                    else:
                        # For non-image files, still use attachment reference
                        result_str += f"\n\n![{filename}](attachment:{file_id})"
                except Exception as e:
                    logger.error(
                        "Error downloading file from sandbox",
                        filename=filename,
                        error=str(e),
                        exc_info=True,
                    )

            # Download all new files with enhanced HTML handling
            list_of_files_after_execution = await sandbox.fs.list_files(".")
            for file in list_of_files_after_execution:
                mime_type, _ = mimetypes.guess_type(file.name)

                # Markdown files are text/markdown
                if mime_type is None:
                    if file.name.lower().endswith(".md"):
                        mime_type = "text/markdown"
                    elif file.name.lower().endswith((".pptx", ".ppt")):
                        # Fallback for PowerPoint files when system mimetypes are missing
                        mime_type = (
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                            if file.name.lower().endswith(".pptx")
                            else "application/vnd.ms-powerpoint"
                        )
                    elif file.name.lower().endswith(".pdf"):
                        mime_type = "application/pdf"
                    elif file.name.lower().endswith((".docx", ".doc")):
                        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

                if file.name not in list_of_files and mime_type in supported_extensions:
                    file_id = str(uuid.uuid4())
                    try:
                        content = await sandbox.fs.download_file(file.name)
                        logger.info(
                            "Downloaded file from sandbox",
                            filename=file.name,
                            size_bytes=len(content),
                            mime_type=mime_type,
                        )

                        if mime_type == "text/html":
                            # Try to validate and fix HTML content
                            try:
                                content_str = (
                                    content.decode("utf-8")
                                    if isinstance(content, bytes)
                                    else str(content)
                                )

                                # Validate and potentially fix the HTML content
                                fixed_content = validate_and_fix_html_content(
                                    content_str, file.name
                                )

                                # If content was modified, update the stored file
                                if fixed_content != content_str:
                                    logger.info(
                                        f"HTML content was enhanced for {file.name}"
                                    )
                                    content = (
                                        fixed_content.encode("utf-8")
                                        if isinstance(fixed_content, str)
                                        else fixed_content
                                    )

                                if not (
                                    "<html" in fixed_content.lower()
                                    or "<body" in fixed_content.lower()
                                ):
                                    result_str += f"\n\n**Note**: {file.name} may not contain complete HTML structure"

                            except Exception as html_check_error:
                                logger.warning(
                                    f"Could not validate HTML content: {html_check_error}"
                                )
                        else:
                            # For non-image files, still use attachment reference
                            result_str += f"\n\n![{file.name}](attachment:{file_id})"

                        # Store in Redis for backup/download purposes
                        if redis_storage:
                            await redis_storage.put_file(
                                user_id,
                                file_id,
                                data=content,
                                filename=file.name,
                                format=mime_type,
                                upload_timestamp=generation_timestamp,
                                indexed=False,
                                source="daytona",
                            )
                    except Exception as e:
                        logger.error(
                            "Error downloading file from sandbox",
                            filename=file.name,
                            error=str(e),
                            exc_info=True,
                        )

            # Process charts from artifacts
            if hasattr(response.artifacts, "charts") and response.artifacts.charts:
                logger.info(
                    "Processing charts from artifacts",
                    num_charts=len(response.artifacts.charts),
                )
                for i, chart in enumerate(response.artifacts.charts):
                    image_id = str(uuid.uuid4())
                    title = chart.title or f"Chart {i+1}"
                    try:
                        if chart.png:
                            # Chart.png should be base64 string, convert to bytes for storage
                            import base64

                            chart_data = base64.b64decode(chart.png)

                            # Store in Redis for backup/download purposes
                            if redis_storage:
                                await redis_storage.put_file(
                                    user_id,
                                    image_id,
                                    data=chart_data,
                                    filename=title,
                                    format="png",
                                    upload_timestamp=generation_timestamp,
                                    indexed=False,
                                    source="daytona",
                                )

                            # Use compact Redis reference instead of data URL to save context
                            result_str += (
                                f"\n\n![{title}](redis-chart:{image_id}:{user_id})"
                            )
                            logger.info(
                                "Successfully stored chart",
                                chart_index=i,
                                chart_title=title,
                                image_id=image_id,
                            )
                        else:
                            logger.info("Chart has no PNG data", chart_index=i)
                            result_str += f"\n\n**Chart Generated:** {title}"
                    except Exception as e:
                        logger.error(
                            "Error storing chart",
                            chart_index=i,
                            error=str(e),
                            exc_info=True,
                        )
                        # Fallback to generic message
                        result_str += f"\n\n**Chart Generated:** {title}"
            else:
                logger.info("No charts found in response artifacts")

            # Clean up sandbox after processing everything
            await daytona.close()

            # Final validation and enhancement of result
            if not result_str.strip():
                result_str = "Code executed successfully. Check the console output above for any results."

            # Add execution summary
            files_created = len(
                [
                    f
                    for f in list_of_files_after_execution
                    if f.name not in list_of_files
                ]
            )
            if files_created > 0:
                result_str += f"\n\n**Execution Summary**: {files_created} file(s) created successfully."

            return result_str

        except Exception as e:
            logger.error("Daytona code execution failed", error=str(e), exc_info=True)
            return f"Error during Daytona code execution: {str(e)}"

    def sync_run_daytona_code_wrapper(code_to_run: str) -> str:
        return asyncio.run(async_run_daytona_code(code_to_run))

    def missing_api_key_tool_sync(code: str) -> str:
        return "Daytona tool is not configured: DAYTONA_API_KEY environment variable is not set."

    async def missing_api_key_tool_async(code: str) -> str:
        return "Daytona tool is not configured: DAYTONA_API_KEY environment variable is not set."

    if not api_key:
        return Tool(
            name="DaytonaCodeSandbox_Misconfigured",
            func=missing_api_key_tool_sync,
            coroutine=missing_api_key_tool_async,
            description="Daytona tool is misconfigured. Set DAYTONA_API_KEY. Input: Python code.",
            args_schema=PythonREPLInput,
        )

    return Tool(
        name="DaytonaCodeSandbox",
        func=sync_run_daytona_code_wrapper,
        coroutine=async_run_daytona_code,
        description="REQUIRED for executing Python code to generate files, perform analysis, or create visualizations. Use this tool when users ask to: create/generate PDFs, HTML files, charts, graphs, images, data analysis, process datasets, build dashboards, or any task requiring code execution. DO NOT just provide code as text - execute it here to deliver actual results. Best practices: structure code with functions, add error handling, validate inputs, use clear variable names, and save all outputs to current directory ('./'). For HTML files, embed images as base64 data URLs for proper display.",
        args_schema=PythonREPLInput,
    )


TOOL_REGISTRY = {
    AvailableTools.DAYTONA: {
        "factory": _get_daytona,
        "schema": Daytona,
    },
    AvailableTools.DDG_SEARCH: {
        "factory": _get_duck_duck_go,
        "schema": DDGSearch,
    },
    AvailableTools.CONNERY: {
        "factory": _get_connery_actions,
        "schema": Connery,
    },
    AvailableTools.ARXIV: {
        "factory": _get_arxiv,
        "schema": Arxiv,
    },
    AvailableTools.YOU_SEARCH: {
        "factory": _get_you_search,
        "schema": YouSearch,
    },
    AvailableTools.SEC_FILINGS: {
        "factory": _get_sec_filings,
        "schema": SecFilings,
    },
    AvailableTools.PRESS_RELEASES: {
        "factory": _get_press_releases,
        "schema": PressReleases,
    },
    AvailableTools.PUBMED: {
        "factory": _get_pubmed,
        "schema": PubMed,
    },
    AvailableTools.WIKIPEDIA: {
        "factory": _get_wikipedia,
        "schema": Wikipedia,
    },
    AvailableTools.TAVILY: {
        "factory": _get_tavily,
        "schema": Tavily,
    },
    AvailableTools.TAVILY_ANSWER: {
        "factory": _get_tavily_answer,
        "schema": TavilyAnswer,
    },
    AvailableTools.DALL_E: {
        "factory": _get_dalle_tools,
        "schema": DallE,
    },
    AvailableTools.RETRIEVAL: {
        "factory": _get_retrieval_tool,
        "schema": Retrieval,
    },
}


def validate_tool_config(tool_type: AvailableTools, config: dict) -> dict:
    """Validate tool configuration against its schema."""
    try:
        schema_class = TOOL_REGISTRY[tool_type]["schema"]

        # Create a full tool instance to validate
        tool_data = {
            "type": tool_type,
            "name": schema_class.model_fields["name"].default,
            "description": schema_class.model_fields["description"].default,
            "config": config,
        }

        # Validate using the schema
        validated_tool = schema_class.model_validate(tool_data)
        return validated_tool.config

    except KeyError:
        raise ValueError(f"Unknown tool type: {tool_type}")
    except Exception as e:
        raise ValueError(f"Invalid config for {tool_type}: {e}")
