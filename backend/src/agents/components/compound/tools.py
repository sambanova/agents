import asyncio
import os
from enum import Enum
from functools import lru_cache
from typing import Annotated, Literal
import uuid

from langchain.tools.retriever import create_retriever_tool
from langchain_community.agent_toolkits.connery import ConneryToolkit
from langchain_community.retrievers.kay import KayAiRetriever
from langchain_community.retrievers.pubmed import PubMedRetriever
from langchain_community.retrievers.wikipedia import WikipediaRetriever
from langchain_community.retrievers.you import YouRetriever
from langchain_community.tools.arxiv.tool import ArxivQueryRun
from langchain_community.tools.connery import ConneryService
from langchain_community.tools.ddg_search.tool import DuckDuckGoSearchRun
from langchain_community.tools.tavily_search import (
    TavilyAnswer as _TavilyAnswer,
)
from langchain_community.tools.tavily_search import (
    TavilySearchResults,
)
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from daytona_sdk import (
    CreateSandboxParams,
    Daytona as DaytonaClient,
    DaytonaConfig as DaytonaSDKConfig,
)


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


class BaseTool(BaseModel):
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


class DallE(BaseTool):
    type: Literal[AvailableTools.DALL_E] = AvailableTools.DALL_E
    name: Literal["Generate Image (Dall-E)"] = "Generate Image (Dall-E)"
    description: Literal[
        "Generates images from a text description using OpenAI's DALL-E model."
    ] = "Generates images from a text description using OpenAI's DALL-E model."


class Daytona(BaseTool):
    type: Literal[AvailableTools.DAYTONA] = AvailableTools.DAYTONA
    name: Literal["Daytona Code Sandbox"] = "Daytona Code Sandbox"
    description: Literal[
        "Executes Python code in a secure sandbox environment. Make sure that outputs are printed and plots are displayed."
    ] = "Executes Python code in a secure sandbox environment. Make sure that outputs are printed and plots are displayed."


RETRIEVAL_DESCRIPTION = """Can be used to look up information that was uploaded to this assistant.
If the user is referencing particular files, that is often a good hint that information may be here.
If the user asks a vague question, they are likely meaning to look up info from this retriever, and you should call it!"""


def get_retriever(assistant_id: str, thread_id: str):
    return vstore.as_retriever(
        search_kwargs={"filter": {"namespace": {"$in": [assistant_id, thread_id]}}}
    )


@lru_cache(maxsize=5)
def get_retrieval_tool(assistant_id: str, thread_id: str, description: str):
    return create_retriever_tool(
        get_retriever(assistant_id, thread_id),
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
def _get_daytona(user_id: str):
    api_key = os.getenv("DAYTONA_API_KEY")

    async def async_run_daytona_code(code_to_run: str) -> str:
        try:
            config = DaytonaSDKConfig(api_key=api_key)
            daytona = DaytonaClient(config)

            params = CreateSandboxParams(
                language="python",
                image="harbor-transient.internal.daytona.app/daytona/data-analysis:0.0.3",
            )

            sandbox = daytona.create(params=params)

            patched_code, expected_filenames = patch_plot_code_str(code_to_run)
            response = sandbox.process.code_run(patched_code)

            # Ensure result is a string, even if None or other types
            result_str = str(response.result) if response.result is not None else ""

            if response.exit_code != 0:
                # Ensure error detail is a string
                daytona.remove(sandbox)
                error_detail = result_str
                return f"Error (Exit Code {response.exit_code}): {error_detail}"

            for filename in expected_filenames:
                extension = os.path.splitext(filename)[1].lstrip(".")
                try:
                    image_id = str(uuid.uuid4())
                    content = sandbox.fs.download_file(filename)
                    await put_file(
                        user_id,
                        image_id,
                        data=content,
                        title=filename,
                        format=extension,
                    )
                    result_str += f"\n\n![{filename}](attachment:{image_id})"
                except Exception as e:
                    pass

            daytona.remove(sandbox)

            if response.artifacts.charts:
                for i, chart in enumerate(response.artifacts.charts):
                    image_id = str(uuid.uuid4())
                    title = chart.title or f"Chart {i+1}"
                    await put_file(
                        user_id, image_id, data=chart.png, title=title, format="png"
                    )
                    result_str += f"\n\n![{title}](attachment:{image_id})"

            return result_str
        except Exception as e:
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
        description="Executes Python code in a secure sandbox environment. Displays plots and text output directly without saving to files.",
        args_schema=PythonREPLInput,
    )


TOOLS = {
    AvailableTools.CONNERY: _get_connery_actions,
    AvailableTools.DDG_SEARCH: _get_duck_duck_go,
    AvailableTools.ARXIV: _get_arxiv,
    AvailableTools.YOU_SEARCH: _get_you_search,
    AvailableTools.SEC_FILINGS: _get_sec_filings,
    AvailableTools.PRESS_RELEASES: _get_press_releases,
    AvailableTools.PUBMED: _get_pubmed,
    AvailableTools.WIKIPEDIA: _get_wikipedia,
    AvailableTools.TAVILY: _get_tavily,
    AvailableTools.TAVILY_ANSWER: _get_tavily_answer,
    AvailableTools.DALL_E: _get_dalle_tools,
    AvailableTools.DAYTONA: _get_daytona,
}
