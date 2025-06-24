import asyncio
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
from agents.utils.code_patcher import patch_plot_code_str
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
import html

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
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # PowerPoint
        "text/html",
        "text/markdown",
        "text/plain",
        "text/csv",
    ]
    images_formats = ["image/png", "image/jpg", "image/jpeg", "image/gif", "image/svg"]

    def strip_markdown_code_blocks(code_str):
        """
        Enhanced function to strip markdown code block formatting from a code string.
        Handles multiple code block formats and common parsing issues that cause HTML generation problems.
        """
        if not isinstance(code_str, str):
            return str(code_str).strip() if code_str is not None else ""
        
        # Store original for fallback
        original_code = code_str
        
        try:
            # Remove opening code block markers (```python, ```py, ```html, or just ```)
            code_str = re.sub(r"^```(?:python|py|html|css|javascript|js)?\s*\n?", "", code_str, flags=re.MULTILINE)

            # Remove closing code block markers
            code_str = re.sub(r"\n?```\s*$", "", code_str, flags=re.MULTILINE)

            # Remove <|python_start|> and <|python_end|> tags
            code_str = re.sub(r"<\|python_start\|>\s*\n?", "", code_str, flags=re.MULTILINE)
            code_str = re.sub(r"\n?\s*<\|python_end\|>", "", code_str, flags=re.MULTILINE)

            # Handle tool_input tags more robustly - common source of HTML parsing errors
            code_str = re.sub(r"<tool_input[^>]*>", "", code_str, flags=re.MULTILINE)
            code_str = re.sub(r"</tool_input[^>]*>", "", code_str, flags=re.MULTILINE)
            
            # Remove incomplete tool tags that can break execution
            code_str = re.sub(r"<tool[^>]*>.*?</tool[^>]*>", "", code_str, flags=re.DOTALL)
            code_str = re.sub(r"</?tool[^>]*>", "", code_str, flags=re.MULTILINE)
            
            # Handle common XML/HTML artifacts that interfere with Python execution
            code_str = re.sub(r"<\?xml[^>]*\?>", "", code_str, flags=re.MULTILINE)
            code_str = re.sub(r"<!DOCTYPE[^>]*>", "", code_str, flags=re.MULTILINE)
            
            # Remove leading/trailing whitespace and empty lines
            code_str = code_str.strip()

            # Decode HTML entities (e.g., &lt; &gt;)
            if '&lt;' in code_str or '&gt;' in code_str or '&amp;' in code_str:
                code_str = html.unescape(code_str)

            # Remove any stray trailing '<' characters introduced by partial tag removal
            code_str = re.sub(r"<+$", "", code_str).rstrip()
            
            # Remove any remaining partial <tool or </tool tokens without closing bracket
            code_str = re.sub(r"</?tool[^>\n]*", "", code_str, flags=re.MULTILINE)
            # Collapse excessive blank lines
            code_str = re.sub(r"\n{3,}", "\n\n", code_str)
            
            # Validate that we still have executable code
            if not code_str or len(code_str.strip()) < 5:
                logger.warning("Code block stripping resulted in very short or empty code, using fallback")
                return original_code.strip()
                
            # Basic syntax validation for Python code
            lines = code_str.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            
            # If we have code but no Python-like content, it might be pure HTML/CSS
            has_python_keywords = any(keyword in code_str.lower() for keyword in 
                                    ['import', 'def', 'class', 'if', 'for', 'while', 'print', 'return'])
            
            if not has_python_keywords and len(non_empty_lines) > 0:
                # Check if this looks like HTML/CSS/JS content
                if any(tag in code_str.lower() for tag in ['<html', '<div', '<body', '<style', 'function']):
                    logger.info("Detected non-Python code (HTML/CSS/JS), wrapping in file creation")
                    # Wrap in Python code to write the content to a file
                    file_extension = 'html'
                    if '<style' in code_str.lower() or 'css' in original_code.lower():
                        file_extension = 'css'
                    elif 'function' in code_str.lower() or 'javascript' in original_code.lower():
                        file_extension = 'js'
                    
                    wrapped_code = f'''
# Auto-generated wrapper for {file_extension.upper()} content
content = """
{code_str}
"""

filename = "generated_content.{file_extension}"
with open(filename, "w", encoding="utf-8") as f:
    f.write(content)

print(f"{{file_extension.upper()}} content written to {{filename}}")
'''
                    return wrapped_code.strip()
            
            return code_str
            
        except Exception as e:
            logger.error(f"Error in strip_markdown_code_blocks: {e}", exc_info=True)
            return original_code.strip()

    def validate_and_fix_html_content(content: str, filename: str) -> str:
        """
        Validates HTML content and attempts to fix common issues that prevent proper rendering.
        """
        try:
            # Basic HTML structure validation and enhancement
            content_lower = content.lower().strip()
            
            # Check if it's a complete HTML document
            has_doctype = content_lower.startswith('<!doctype')
            has_html_tag = '<html' in content_lower
            has_head_tag = '<head' in content_lower
            has_body_tag = '<body' in content_lower
            
            # If it's missing essential HTML structure, wrap it
            if not has_html_tag and not has_doctype:
                logger.info(f"Adding HTML structure to {filename}")
                
                # Detect if it's CSS or JavaScript
                if '<style' in content_lower or 'css' in filename.lower():
                    # Wrap CSS in proper HTML
                    content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated CSS Content</title>
    <style>
{content}
    </style>
</head>
<body>
    <h1>CSS Styles Applied</h1>
    <p>This document contains the generated CSS styles.</p>
</body>
</html>'''
                elif '<script' in content_lower or 'javascript' in content_lower or filename.lower().endswith('.js'):
                    # Wrap JavaScript in proper HTML
                    content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated JavaScript Content</title>
</head>
<body>
    <h1>JavaScript Application</h1>
    <div id="app"></div>
    <script>
{content}
    </script>
</body>
</html>'''
                else:
                    # Wrap general HTML content
                    content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Content</title>
</head>
<body>
{content}
</body>
</html>'''
            
            # Fix common HTML issues
            # Ensure proper charset declaration
            if 'charset' not in content_lower and '<head' in content_lower:
                content = content.replace('<head>', '<head>\n    <meta charset="UTF-8">')
            
            # Add viewport meta tag for mobile responsiveness
            if 'viewport' not in content_lower and '<head' in content_lower:
                charset_pos = content.lower().find('charset')
                if charset_pos != -1:
                    # Find end of charset meta tag
                    next_tag = content.find('>', charset_pos)
                    if next_tag != -1:
                        content = content[:next_tag+1] + '\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">' + content[next_tag+1:]
            
            # Decode HTML entities if needed
            if '&lt;' in content or '&gt;' in content or '&amp;' in content:
                content = html.unescape(content)
                content_lower = content.lower().strip()

            logger.info(f"HTML content validated and enhanced for {filename}")
            return content
            
        except Exception as e:
            logger.warning(f"Could not validate/fix HTML content for {filename}: {e}")
            return content  # Return original content if validation fails

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
                logger.error("Code execution failed in sandbox", error=str(exec_error), exc_info=True)
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
                
                # Enhanced MIME type detection for common web files
                if mime_type is None:
                    if file.name.lower().endswith(".md"):
                        mime_type = "text/markdown"
                    elif file.name.lower().endswith(".html") or file.name.lower().endswith(".htm"):
                        mime_type = "text/html"
                    elif file.name.lower().endswith(".css"):
                        mime_type = "text/css"
                    elif file.name.lower().endswith(".js"):
                        mime_type = "application/javascript"
                    elif file.name.lower().endswith(".json"):
                        mime_type = "application/json"
                
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

                        # For image files, use compact Redis references instead of data URLs
                        if mime_type in images_formats:
                            result_str += (
                                f"\n\n![{file.name}](redis-chart:{file_id}:{user_id})"
                            )
                        elif mime_type == "text/html":
                            # Special handling for HTML files to ensure proper rendering
                            result_str += f"\n\n**HTML File Generated:** [{file.name}](attachment:{file_id})"
                            # Try to validate and fix HTML content
                            try:
                                content_str = content.decode('utf-8') if isinstance(content, bytes) else str(content)
                                
                                # Validate and potentially fix the HTML content
                                fixed_content = validate_and_fix_html_content(content_str, file.name)
                                
                                # If content was modified, update the stored file
                                if fixed_content != content_str:
                                    logger.info(f"HTML content was enhanced for {file.name}")
                                    fixed_content_bytes = fixed_content.encode('utf-8') if isinstance(fixed_content, str) else fixed_content
                                    
                                    # Update the file in the sandbox
                                    try:
                                        if hasattr(sandbox.fs, 'write_file'):
                                            await sandbox.fs.write_file(file.name, fixed_content_bytes)
                                        else:
                                            await sandbox.fs.upload_file(file.name, fixed_content_bytes)
                                        # Also update Redis storage with fixed content
                                        if redis_storage:
                                            await redis_storage.put_file(
                                                user_id,
                                                file_id,
                                                data=fixed_content_bytes,
                                                filename=file.name,
                                                format=mime_type,
                                                upload_timestamp=generation_timestamp,
                                                indexed=False,
                                                source="daytona",
                                            )
                                    except Exception as upload_error:
                                        logger.warning(f"Could not update fixed HTML file: {upload_error}")
                                
                                if '<html' in fixed_content.lower() or '<body' in fixed_content.lower():
                                    result_str += f"\n\n📄 **Interactive HTML file created**: {file.name}"
                                    logger.info(f"Valid HTML content detected in {file.name}")
                                else:
                                    result_str += f"\n\n⚠️ **Note**: {file.name} may not contain complete HTML structure"
                            except Exception as html_check_error:
                                logger.warning(f"Could not validate HTML content: {html_check_error}")
                        else:
                            # For non-image files, still use attachment reference
                            result_str += f"\n\n![{file.name}](attachment:{file_id})"
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
            files_created = len([f for f in list_of_files_after_execution if f.name not in list_of_files])
            if files_created > 0:
                result_str += f"\n\n✅ **Execution Summary**: {files_created} file(s) created successfully."

            return result_str
            
        except Exception as e:
            logger.error("Daytona code execution failed", error=str(e), exc_info=True)
            # Provide more helpful error messages
            if "connection" in str(e).lower():
                return f"Error: Could not connect to Daytona sandbox. Please check your API key and network connection."
            elif "timeout" in str(e).lower():
                return f"Error: Code execution timed out. Try simplifying your code or breaking it into smaller parts."
            else:
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
        description="Executes Python code in a secure sandbox environment. It can be used to plot graphs, create charts, images, documents, etc. If the user asks you for any of these, you should use this tool. Make sure you write everything to disk.",
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
