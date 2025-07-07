import html
import mimetypes
import os
import re
import time
import uuid
from typing import Dict, List, Optional, TypedDict

import structlog
from agents.components.open_deep_research.utils import APIKeyRotator
from agents.storage.redis_storage import RedisStorage
from agents.tools.langgraph_tools import TOOL_REGISTRY
from agents.utils.code_validator import (
    patch_plot_code_str,
    strip_markdown_code_blocks,
    validate_and_fix_html_content,
)
from agents.utils.llms import get_sambanova_llm
from daytona_sdk import AsyncDaytona as DaytonaClient
from daytona_sdk import CreateSandboxFromSnapshotParams
from daytona_sdk import DaytonaConfig as DaytonaSDKConfig
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from unidecode import unidecode

logger = structlog.get_logger(__name__)


class CodeReplacement(BaseModel):
    remove: str = Field(description="Code to replace")
    add: str = Field(description="Code to add")


class CodeCorrections(BaseModel):
    corrections: List[CodeReplacement] = Field(
        description="List of code corrections. This can be empty if you decide that research is needed.",
        default_factory=list,
    )
    needs_research: bool = Field(
        description="Set to true if you are not confident about the fix and believe a web search for the error message would provide better context. If you set this to true, you MUST provide an empty list for `corrections`.",
        default=False,
    )


system_prompt = """You are an expert Python developer and debugger. Your primary goal is to be accurate. When in doubt, you MUST request more information by using the web search tool.

INSTRUCTIONS:
1.  First, analyze the provided code, error message, and any search context.
2.  Next, categorize the error. Is it:
    a) A simple syntax error, typo, or undefined variable?
    b) A complex error involving an external library's API (e.g., `AttributeError`, `TypeError`, `ValueError` from a library call)?
    c) An error you don't recognize?
3.  **Based on the category, DECIDE YOUR NEXT ACTION:**
    *   **If `search_context` is EMPTY:**
        *   If the error is category (a) (simple syntax/typo), you can propose a fix directly. Set `needs_research` to `false`.
        *   If the error is category (b) or (c) (library error or unknown), you MUST assume you don't have enough information. Set `needs_research` to `true` and provide an EMPTY list for `corrections`. This is the safest action. **DO NOT GUESS THE FIX FOR LIBRARY ERRORS.**
    *   **If `search_context` is NOT EMPTY:**
        *   You MUST use the provided search context to formulate a definitive fix. Provide the code corrections based on your analysis and set `needs_research` to `false`.
4.  **FORMATTING THE FIX:**
    *   The "remove" value must be the **exact** string from the original code.
    *   The "add" value is the new text that will replace it.
    *   To ensure uniqueness, expand the `remove` and `add` strings with surrounding lines if necessary.
    *   It is critical that the "remove" string is EXACTLY as it appears in the code, including all whitespace, newlines, and special characters.
    *   If you receive `CORRECTION FEEDBACK`, your previous attempt failed. Carefully read the feedback and adjust your proposed `corrections` to address the issue. For example, if the feedback says your 'remove' string was not unique, you MUST add more surrounding lines to both the 'remove' and 'add' fields.

You must respond with valid JSON that matches this exact schema:
{code_replacement_schema}
"""


user_prompt = """Please analyze this Python code, the error it produced, and any provided search context. Follow the instructions to propose a fix or request research.

CODE:
```python
{code}
```

ERROR:
```
{error}
```

SEARCH CONTEXT:
```
{context}
```

CORRECTION FEEDBACK:
```
{feedback}
```
"""


class CorrectingExecutorState(TypedDict):
    """
    Represents the state for a self-correcting code execution task.

    Attributes:
        code: The Python code to execute. This is modified by the correction loop.
        error_log: The error message from the last failed attempt.
        corrections_proposed: A list of dictionaries, each with "remove" and "add" keys,
                              representing the text changes to apply.
        current_retry: The current attempt number.
        max_retries: The maximum number of correction attempts allowed.
        final_result: The successful output of the code.
        messages: List[BaseMessage]  # List of messages from the agent
        search_context: Optional[str]
        needs_research: bool
        correction_feedback: Optional[str]
    """

    code: str
    error_log: str
    corrections_proposed: List[Dict[str, str]]
    current_retry: int
    max_retries: int
    final_result: str
    messages: List[BaseMessage]
    search_context: Optional[str]
    needs_research: bool
    correction_feedback: Optional[str]


class MessageInterceptor:
    def __init__(self):
        self.captured_messages = []

    def capture_and_pass(self, message):
        """Capture the message and pass it through"""
        if isinstance(message, AIMessage):
            self.captured_messages.append(message)
        return message


def create_code_execution_graph(
    user_id: str, sambanova_api_key: str, redis_storage: RedisStorage
):
    logger.info("Creating code execution subgraph")
    api_key = os.getenv("DAYTONA_API_KEY")
    daytona_snapshot = os.getenv("DAYTONA_SNAPSHOT")

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

    def fix_common_string_issues(code: str) -> str:
        """
        Fixes common HTML, Unicode, and f-string issues in generated Python code.
        This function acts as a pre-processor to clean the code before execution.
        """
        original_code = code

        # Step 1: Un-escape HTML entities to get clean code
        code = html.unescape(code)

        # Step 2: Transliterate all Unicode to ASCII to handle symbols like ∼, ℓ, etc.
        code = unidecode(code)

        # Step 3: Remove XML-like closing tags at the end of the code
        # This handles cases like </subgraph, </s, </sub, etc. that cause syntax errors
        code = re.sub(r"</[a-zA-Z][a-zA-Z0-9_]*\s*(?:\n```)?$", "", code)

        # Handle the case where there's just a '</' without any following characters
        code = re.sub(r"</\s*(?:\n```)?$", "", code)

        if code != original_code:
            logger.info(
                "Applied HTML, Unicode, f-string, or XML tag fixes to the code."
            )

        return code

    async def patch_code(state: CorrectingExecutorState) -> Dict:
        """
        Patches the code to fix the error.
        """

        try:
            # Strip markdown formatting before processing
            clean_code = strip_markdown_code_blocks(state["code"])

        except Exception as e:
            logger.info("Error cleaning code", error=str(e), exc_info=True)
            return {
                "error_log": "Error patching code: " + str(e),
            }

        # Validate the cleaned code
        if not clean_code or len(clean_code.strip()) < 3:
            return {
                "error_log": "Error: No valid code found after processing input. Please provide valid Python code."
            }

        # Enhanced logging for debugging
        logger.info(
            "Processing code for execution",
            original_length=len(state["code"]),
            cleaned_length=len(clean_code),
            first_100_chars=clean_code[:100],
        )

        # Apply common fixes for HTML/string formatting issues
        try:
            clean_code = fix_common_string_issues(clean_code)
        except Exception as e:
            logger.info("Error applying string fixes", error=str(e), exc_info=True)

        try:
            patched_code, _ = patch_plot_code_str(clean_code)
        except Exception as e:
            logger.info("Error patching code", error=str(e), exc_info=True)
            return {
                "code": clean_code,
                "error_log": "Error patching code: " + str(e),
            }

        return {
            "code": patched_code,
            "error_log": "",
        }

    async def execute_code(state: CorrectingExecutorState) -> Dict:
        result: Dict = {}
        sandbox = None
        daytona = None
        try:
            # 1. Setup clients
            config = DaytonaSDKConfig(api_key=api_key)
            daytona = DaytonaClient(config)

            # 2. Create sandbox
            params = CreateSandboxFromSnapshotParams(
                snapshot=daytona_snapshot,
            )
            sandbox = await daytona.create(params=params)
            list_of_files = [f.name for f in await sandbox.fs.list_files(".")]

            # 3. Run code and handle errors without returning
            response = None
            execution_successful = False
            try:
                response = await sandbox.process.code_run(state["code"])
                if response.exit_code == 0:
                    execution_successful = True
                else:
                    error_detail = (
                        str(response.result) if response.result is not None else ""
                    )
                    logger.info(
                        "Daytona code execution failed with non-zero exit code",
                        exit_code=response.exit_code,
                        error_detail=error_detail,
                    )
                    result = {
                        "error_log": f"Error (Exit Code {response.exit_code}): {error_detail}",
                        "current_retry": state["current_retry"] + 1,
                    }
            except Exception as exec_error:
                logger.error(
                    "Code execution failed in sandbox",
                    error=str(exec_error),
                    exc_info=True,
                )
                result = {
                    "error_log": "Error during code execution: " + str(exec_error),
                    "current_retry": state["current_retry"] + 1,
                }

            # 4. If execution was successful, process artifacts
            if execution_successful and response:
                result_str = f"Code executed successfully, result from the sandbox:\n\n {str(response.result) if response.result is not None else ''}"

                logger.info(
                    "Daytona response",
                    exit_code=response.exit_code,
                    result_preview=str(response.result)[:500],
                    artifacts=response.artifacts,
                )

                generation_timestamp = time.time()
                list_of_files_after_execution = await sandbox.fs.list_files(".")
                for file in list_of_files_after_execution:
                    mime_type, _ = mimetypes.guess_type(file.name)

                    if mime_type is None:
                        if file.name.lower().endswith(".md"):
                            mime_type = "text/markdown"
                        elif file.name.lower().endswith((".pptx", ".ppt")):
                            mime_type = (
                                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                                if file.name.lower().endswith(".pptx")
                                else "application/vnd.ms-powerpoint"
                            )
                        elif file.name.lower().endswith(".pdf"):
                            mime_type = "application/pdf"
                        elif file.name.lower().endswith((".docx", ".doc")):
                            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

                    if (
                        file.name not in list_of_files
                        and mime_type in supported_extensions
                    ):
                        file_id = str(uuid.uuid4())
                        try:
                            content = await sandbox.fs.download_file(file.name)
                            if mime_type == "text/html":
                                try:
                                    content_str = (
                                        content.decode("utf-8")
                                        if isinstance(content, bytes)
                                        else str(content)
                                    )
                                    fixed_content = validate_and_fix_html_content(
                                        content_str, file.name
                                    )
                                    if fixed_content != content_str:
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
                                    else:
                                        result_str += (
                                            f"\n\n![{file.name}](attachment:{file_id})"
                                        )
                                except Exception as html_check_error:
                                    logger.warning(
                                        f"Could not validate HTML content: {html_check_error}"
                                    )
                            elif mime_type in images_formats:
                                result_str += f"\n\n![{file.name}](redis-chart:{file_id}:{user_id})"
                            else:
                                result_str += (
                                    f"\n\n![{file.name}](attachment:{file_id})"
                                )

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

                if hasattr(response.artifacts, "charts") and response.artifacts.charts:
                    for i, chart in enumerate(response.artifacts.charts):
                        image_id = str(uuid.uuid4())
                        title = chart.title or f"Chart {i+1}"
                        try:
                            if chart.png:
                                import base64

                                chart_data = base64.b64decode(chart.png)
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
                                result_str += (
                                    f"\n\n![{title}](redis-chart:{image_id}:{user_id})"
                                )
                        except Exception as e:
                            logger.error(
                                "Error storing chart",
                                chart_index=i,
                                error=str(e),
                                exc_info=True,
                            )
                            result_str += f"\n\n**Chart Generated:** {title}"

                files_created = len(
                    [
                        f
                        for f in list_of_files_after_execution
                        if f.name not in list_of_files
                    ]
                )
                if files_created > 0:
                    result_str += f"\n\n**Execution Summary**: {files_created} file(s) created successfully."

                result = {
                    "final_result": result_str,
                    "current_retry": state["current_retry"] + 1,
                    "error_log": "",
                }

        except Exception as e:
            logger.error(
                "Daytona setup or critical error failed", error=str(e), exc_info=True
            )
            result = {
                "error_log": "Error during Daytona setup: " + str(e),
                "current_retry": state["current_retry"] + 1,
            }
        finally:
            if sandbox:
                await sandbox.delete()
            if daytona:
                await daytona.close()

        return result

    async def analyze_error_and_decide(state: CorrectingExecutorState) -> Dict:
        """
        Analyzes the error and decides whether to propose a fix directly or to
        conduct research first. If research has already been done, it uses the
        context to propose a definitive fix.
        """
        context = state.get("search_context")
        feedback = state.get("correction_feedback")
        if context:
            logger.info("Analyzing error with search context...")
        else:
            logger.info("Analyzing error and deciding on next step...")

        try:
            llm = get_sambanova_llm(api_key=sambanova_api_key, model="DeepSeek-V3-0324")

            messages = [
                SystemMessage(
                    content=system_prompt.format(
                        code_replacement_schema=CodeCorrections.model_json_schema()
                    )
                ),
                HumanMessage(
                    content=user_prompt.format(
                        code=state["code"],
                        error=state["error_log"],
                        context=context or "No search context provided.",
                        feedback=feedback or "No feedback on previous attempt.",
                    )
                ),
            ]

            fixing_interceptor = MessageInterceptor()

            inceptor_llm = llm | RunnableLambda(fixing_interceptor.capture_and_pass)
            structured_llm = inceptor_llm | OutputFixingParser.from_llm(
                llm=inceptor_llm,
                parser=PydanticOutputParser(pydantic_object=CodeCorrections),
            )

            response = await structured_llm.ainvoke(messages)

            captured_messages = []
            for m in fixing_interceptor.captured_messages:
                m.additional_kwargs["agent_type"] = "code_fixer_agents"
                captured_messages.append(m)

            # Clear the search context after it's been used
            return {
                "corrections_proposed": response.model_dump()["corrections"],
                "needs_research": response.needs_research,
                "messages": captured_messages,
                "search_context": None,  # Reset context
                "correction_feedback": None,  # Reset feedback
            }
        except Exception as e:
            logger.error(f"Error calling LLM for code fix: {e}", exc_info=True)
            # If the analysis fails, escalate to research as a fallback
            return {"needs_research": True}

    async def research_for_fix(state: CorrectingExecutorState) -> Dict:
        """
        Node: Performs a web search using the error message to find solutions.
        """
        logger.info("Performing web search for error context...")
        error_log = state["error_log"]

        # Extract the most meaningful line from the error log for a better query
        error_lines = error_log.strip().split("\n")
        concise_error = error_lines[-1] if error_lines else error_log
        query = f"python {concise_error}"
        logger.info(f"Tavily search query: {query}")

        try:
            # Get the search tool from the registry
            tavily_search = TOOL_REGISTRY["search_tavily"]["factory"]()

            # Perform the search
            search_results = await tavily_search.ainvoke(
                {"query": query, "max_results": 5, "include_raw_content": True}
            )

            # The tool returns a list of strings, so we format it.
            formatted_context = "\n\n".join([s["content"] for s in search_results])

            return {"search_context": formatted_context}
        except Exception as e:
            logger.error(f"Error during Tavily search: {e}", exc_info=True)
            # If search fails, return empty context to proceed without it
            return {"search_context": "Web search failed."}

    async def override_code(state: CorrectingExecutorState) -> Dict:
        """
        Applies the proposed fix to the code in the state.
        """
        corrections = state["corrections_proposed"]
        if not corrections and not state.get("correction_feedback"):
            logger.info(
                "No corrections proposed and no feedback. Assuming successful pass-through."
            )
            return {"corrections_proposed": []}  # Ensure corrections are cleared

        updated_code = state["code"]

        # Apply each correction sequentially.
        for correction in corrections:
            to_remove = correction.get("remove")
            to_add = correction.get("add")

            if to_remove is None or to_add is None:
                logger.warning(
                    "Invalid correction format, skipping.", correction=correction
                )
                continue

            # Ensure the "remove" string is unique to avoid ambiguous replacements.
            if to_remove and updated_code.count(to_remove) > 1:
                logger.warning(
                    "Text to remove is not unique, skipping correction to avoid ambiguity.",
                    to_remove=to_remove[:100],  # Log a preview
                )
                feedback_msg = f"The 'remove' string you provided was not unique. Please add more surrounding lines of context to make it specific. The non-unique string was: '{to_remove[:100]}...'"
                return {
                    "correction_feedback": feedback_msg,
                    "corrections_proposed": [],  # Clear the failed proposal
                }

            if to_remove and to_remove not in updated_code:
                logger.warning(
                    "Text to remove not found in code, skipping correction.",
                    to_remove=to_remove[:100],  # Log a preview
                )
                feedback_msg = f"The 'remove' string you provided was not found in the code. Ensure it is an exact match. The string was: '{to_remove[:100]}...'"
                return {
                    "correction_feedback": feedback_msg,
                    "corrections_proposed": [],  # Clear the failed proposal
                }

            logger.info(
                "Applying correction",
                to_remove=to_remove[:100],
                to_add=to_add[:100],
            )
            updated_code = updated_code.replace(to_remove, to_add, 1)

        return {"code": updated_code, "corrections_proposed": []}  # Clear corrections

    async def should_continue_patch_code(state: CorrectingExecutorState) -> str:
        """
        Determines the next step after code execution.
        """
        if state["error_log"]:
            if state["current_retry"] < state["max_retries"]:
                # If there's an error and we have retries left, enter the correction loop.
                return "analyze_and_decide"
            else:
                # If retries are exhausted, end the process.
                logger.info("Max Retries Reached")
                return END
        else:
            # If there's no error, the process is successful.
            return "execute_code"

    async def should_continue_execute_code(state: CorrectingExecutorState) -> str:
        """
        Determines the next step after code execution.
        """
        if state["error_log"]:
            if state["current_retry"] < state["max_retries"]:
                # If there's an error and we have retries left, enter the correction loop.
                return "analyze_and_decide"
            else:
                # If retries are exhausted, end the process.
                logger.info("Max Retries Reached")
                return END
        else:
            # If there's no error, the process is successful.
            return END

    async def should_research(state: CorrectingExecutorState) -> str:
        """
        Determines whether to perform a web search based on the LLM's decision.
        """
        if state.get("needs_research"):
            logger.info(
                "LLM is not confident and has requested research. Proceeding to web search."
            )
            return "research_for_fix"
        else:
            logger.info("LLM is confident or has used context. Applying proposed fix.")
            return "override_code"

    def did_override_succeed(state: CorrectingExecutorState) -> str:
        """
        Checks if the override_code step produced feedback, indicating a failure.
        """
        if state.get("correction_feedback"):
            logger.info("Correction failed. Looping back to analysis with feedback.")
            return "analyze_and_decide"
        else:
            logger.info("Correction applied successfully. Proceeding to execution.")
            return "execute_code"

    workflow = StateGraph(CorrectingExecutorState)

    workflow.add_node("patch_code", patch_code)
    workflow.add_node("execute_code", execute_code)
    workflow.add_node("analyze_and_decide", analyze_error_and_decide)
    workflow.add_node("research_for_fix", research_for_fix)
    workflow.add_node("override_code", override_code)

    workflow.set_entry_point("patch_code")

    workflow.add_conditional_edges(
        "patch_code",
        should_continue_patch_code,
        {
            "analyze_and_decide": "analyze_and_decide",
            "execute_code": "execute_code",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "execute_code",
        should_continue_execute_code,
        {
            "analyze_and_decide": "analyze_and_decide",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "analyze_and_decide",
        should_research,
        {"research_for_fix": "research_for_fix", "override_code": "override_code"},
    )

    workflow.add_conditional_edges(
        "override_code",
        did_override_succeed,
        {"analyze_and_decide": "analyze_and_decide", "execute_code": "execute_code"},
    )

    workflow.add_edge("research_for_fix", "analyze_and_decide")  # Loop back

    # Compile and return
    return workflow.compile()
