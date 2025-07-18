import html
import mimetypes
import os
import re
import time
import uuid
from datetime import datetime
from operator import add
from typing import Annotated, Dict, List, Optional, TypedDict

import structlog
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.components.open_deep_research.utils import APIKeyRotator
from agents.storage.redis_storage import RedisStorage
from agents.tools.langgraph_tools import TOOL_REGISTRY
from agents.utils.code_validator import (
    patch_plot_code_str,
    strip_markdown_code_blocks,
    validate_and_fix_html_content,
)
from agents.utils.llms import get_sambanova_llm
from agents.utils.message_interceptor import MessageInterceptor
from daytona_sdk import AsyncDaytona as DaytonaClient
from daytona_sdk import CreateSandboxFromSnapshotParams
from daytona_sdk import DaytonaConfig as DaytonaSDKConfig
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
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
    additional_packages: List[str] = Field(
        description="List of additional packages to install. This can be empty if you decide that research is needed.",
        default_factory=list,
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
    5.  **INSTALLING ADDITIONAL PACKAGES:**
        *   If the error indicates missing modules/packages (e.g., `ModuleNotFoundError`, `ImportError`), include the required package names in the `additional_packages` list.
        *   Use exact package names as they appear on PyPI (e.g., "matplotlib", "pandas", "scikit-learn").
        *   Only suggest packages you are confident about. If uncertain about the correct package name, set `needs_research` to `true` instead.
        *   If no additional packages are needed, leave the list empty.
    
    You must respond with valid JSON that matches this exact schema:
{code_replacement_schema}
"""


user_prompt = """Please analyze this Python code, the error it produced, and any provided search context. Follow the instructions to propose a fix or request research.

CODE:
```python
{code}
```

STEPS TAKEN:
```
{steps_taken}
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
        corrections_proposed: A list of dictionaries, each with "remove" and "add" keys,
                              representing the text changes to apply.
        current_retry: The current attempt number.
        max_retries: The maximum number of correction attempts allowed.
        messages: List[BaseMessage]  # List of messages from the agent
        search_context: Optional[str]
        needs_research: bool
        correction_feedback: Optional[str]
    """

    code: str
    steps_taken: Annotated[list[str], add]
    error_detected: bool
    corrections_proposed: list[Dict[str, str]]
    current_retry: int
    max_retries: int
    messages: list[BaseMessage]
    search_context: Optional[str]
    needs_research: bool
    additional_packages: Annotated[list[str], lambda left, right: right]
    installation_successful: bool
    correction_feedback: Optional[str]
    files: Annotated[list[str], add]


def create_code_execution_graph(
    user_id: str,
    sambanova_api_key: str,
    redis_storage: RedisStorage,
    daytona_manager: PersistentDaytonaManager,
):
    logger.info("Creating code execution subgraph")

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
                "steps_taken": ["Error cleaning code: " + str(e)],
            }

        # Validate the cleaned code
        if not clean_code or len(clean_code.strip()) < 3:
            return {
                "steps_taken": [
                    "Error: No valid code found after processing input. Please provide valid Python code."
                ],
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
                "steps_taken": ["Error patching code: " + str(e)],
            }

        return {
            "code": patched_code,
            "steps_taken": ["Code patched successfully"],
        }

    async def execute_code(state: CorrectingExecutorState) -> Dict:
        result: Dict = {}
        files = []
        try:
            response = None
            list_of_files = await daytona_manager.list_files(".")
            response, execution_successful = await daytona_manager.execute_code(
                state["code"]
            )
            if execution_successful:
                result_str = f"Code executed successfully, result from the sandbox:\n\n {response}"

                logger.info(
                    "Daytona response",
                    result_preview=response[:500],
                )

                generation_timestamp = time.time()
                list_of_files_after_execution = (
                    await daytona_manager.get_all_files_recursive()
                )
                for file_info in list_of_files_after_execution:
                    file = file_info["file"]
                    file_path = file_info["path"]
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
                            content = await daytona_manager.download_file(file_path)
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
                                files.append(file_id)
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

                result = {
                    "current_retry": state["current_retry"] + 1,
                    "steps_taken": [
                        "Code executed successfully",
                        "Result: " + response,
                    ],
                    "files": files,
                }

            elif not execution_successful:
                result = {
                    "steps_taken": ["Code execution failed: " + response],
                    "current_retry": state["current_retry"] + 1,
                    "error_detected": True,
                }

        except Exception as e:
            logger.error(
                "Daytona setup or critical error failed", error=str(e), exc_info=True
            )
            result = {
                "steps_taken": ["Error during Daytona setup: " + str(e)],
                "current_retry": state["current_retry"] + 1,
            }

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
                        steps_taken="\n".join(state["steps_taken"]),
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
                "steps_taken": [
                    f"Analyzed error and decided on next step, Corrections proposed: {str(response.model_dump()['corrections'])},Needs research: {str(response.needs_research)}, Install additional packages: {str(response.additional_packages)}"
                ],
                "error_detected": False,
                "corrections_proposed": response.model_dump()["corrections"],
                "needs_research": response.needs_research,
                "additional_packages": response.additional_packages,
                "messages": captured_messages,
                "search_context": None,  # Reset context
                "correction_feedback": None,  # Reset feedback
            }
        except Exception as e:
            logger.error(f"Error calling LLM for code fix: {e}", exc_info=True)
            # If the analysis fails, escalate to research as a fallback
            return {
                "needs_research": True,
                "error_detected": False,
            }

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

            return {
                "search_context": formatted_context,
                "steps_taken": ["Web search for fix was successful."],
            }
        except Exception as e:
            logger.error(f"Error during Tavily search: {e}", exc_info=True)
            # If search fails, return empty context to proceed without it
            return {
                "search_context": "Web search failed.",
                "steps_taken": ["Web search failed."],
            }

    async def override_code(state: CorrectingExecutorState) -> Dict:
        """
        Applies the proposed fix to the code in the state.
        """
        corrections = state["corrections_proposed"]
        if not corrections and not state.get("correction_feedback"):
            logger.info(
                "No corrections proposed and no feedback. Assuming successful pass-through."
            )
            return {
                "corrections_proposed": [],
                "steps_taken": [
                    "No corrections proposed and no feedback. Assuming successful pass-through."
                ],
                "error_detected": False,
            }  # Ensure corrections are cleared

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
                    "steps_taken": ["Unsuccessful code patch"],
                    "error_detected": True,
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
                    "steps_taken": ["Unsuccessful code patch"],
                    "error_detected": True,
                }

            logger.info(
                "Applying correction",
                to_remove=to_remove[:100],
                to_add=to_add[:100],
            )
            updated_code = updated_code.replace(to_remove, to_add, 1)

        return {
            "code": updated_code,
            "corrections_proposed": [],  # Clear corrections
            "steps_taken": ["Code patched successfully"],
            "error_detected": False,
        }

    async def should_continue_patch_code(state: CorrectingExecutorState) -> str:
        """
        Determines the next step after code execution.
        """
        if state["error_detected"]:
            if state["current_retry"] < state["max_retries"]:
                # If there's an error and we have retries left, enter the correction loop.
                return "analyze_and_decide"
            else:
                # If retries are exhausted, end the process.
                logger.info("Max Retries Reached")
                return "cleanup"
        else:
            # If there's no error, the process is successful.
            return "execute_code"

    async def should_continue_execute_code(state: CorrectingExecutorState) -> str:
        """
        Determines the next step after code execution.
        """
        if state["error_detected"]:
            if state["current_retry"] < state["max_retries"]:
                # If there's an error and we have retries left, enter the correction loop.
                return "analyze_and_decide"
            else:
                # If retries are exhausted, end the process.
                logger.info("Max Retries Reached")
                return "cleanup"
        else:
            # If there's no error, the process is successful.
            return "cleanup"

    async def should_research(state: CorrectingExecutorState) -> str:
        """
        Determines whether to perform a web search based on the LLM's decision.
        """
        if state.get("needs_research"):
            logger.info(
                "LLM is not confident and has requested research. Proceeding to web search."
            )
            return "research_for_fix"
        elif state.get("additional_packages"):
            logger.info(
                "LLM has suggested additional packages. Proceeding to install them."
            )
            return "install_packages"
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

    async def cleanup_node(state: CorrectingExecutorState) -> dict:
        """Clean up the persistent Daytona manager."""
        await daytona_manager.cleanup()
        return {}

    async def install_packages(state: CorrectingExecutorState) -> Dict:
        """Install the additional packages."""
        logger.info("Installing additional packages.")
        aggregated_result = ""
        installation_successful = True
        for package in state["additional_packages"]:
            pip_command = f"pip install {package}"
            result = await daytona_manager.execute(pip_command, timeout=300)
            if not result.startswith("Error"):
                aggregated_result += f"Successfully installed {package}: {result[:100] + '...' + result[-100:]}\n\n"
            else:
                aggregated_result += f"Error installing {package}: {result[:100] + '...' + result[-100:]}\n\n"
                installation_successful = False

        return {
            "additional_packages": [],
            "installation_successful": installation_successful,
            "steps_taken": [aggregated_result],
            "messages": [
                ToolMessage(
                    id=str(uuid.uuid4()),
                    content=result,
                    name="install_packages",
                    tool_call_id=str(uuid.uuid4()),
                    status="success" if installation_successful else "error",
                    additional_kwargs={
                        "agent_type": "tool_response",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            ],
        }

    async def should_continue_install_packages(state: CorrectingExecutorState) -> str:
        """Determine if the installation process should continue."""
        if state["installation_successful"]:
            logger.info("Installation successful. Proceeding to execution.")
            return "execute_code"
        else:
            logger.info("Installation failed. Proceeding to analysis.")
            return "analyze_and_decide"

    workflow = StateGraph(CorrectingExecutorState)

    workflow.add_node("patch_code", patch_code)
    workflow.add_node("execute_code", execute_code)
    workflow.add_node("analyze_and_decide", analyze_error_and_decide)
    workflow.add_node("research_for_fix", research_for_fix)
    workflow.add_node("override_code", override_code)
    workflow.add_node("cleanup", cleanup_node)
    workflow.add_node("install_packages", install_packages)
    workflow.set_entry_point("patch_code")

    workflow.add_conditional_edges(
        "patch_code",
        should_continue_patch_code,
        {
            "analyze_and_decide": "analyze_and_decide",
            "execute_code": "execute_code",
            "cleanup": "cleanup",
        },
    )

    workflow.add_conditional_edges(
        "execute_code",
        should_continue_execute_code,
        {
            "analyze_and_decide": "analyze_and_decide",
            "cleanup": "cleanup",
        },
    )

    workflow.add_conditional_edges(
        "analyze_and_decide",
        should_research,
        {
            "research_for_fix": "research_for_fix",
            "override_code": "override_code",
            "install_packages": "install_packages",
        },
    )
    workflow.add_conditional_edges(
        "install_packages",
        should_continue_install_packages,
        {"execute_code": "execute_code", "analyze_and_decide": "analyze_and_decide"},
    )

    workflow.add_conditional_edges(
        "override_code",
        did_override_succeed,
        {"analyze_and_decide": "analyze_and_decide", "execute_code": "execute_code"},
    )

    workflow.add_edge("research_for_fix", "analyze_and_decide")  # Loop back
    workflow.add_edge("cleanup", END)

    # Compile and return
    return workflow.compile()
