import asyncio
import html
import mimetypes
import os
import re
import time
import uuid
from typing import Dict, List, TypedDict

import structlog
from agents.storage.redis_storage import RedisStorage
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
        description="List of code corrections.",
    )


system_prompt = """You are an expert Python developer and debugger. Your task is to analyze Python code that has failed and propose specific text replacements to fix it.

INSTRUCTIONS:
1.  Carefully analyze the provided code and the error message.
2.  Identify the exact text snippets that need to be replaced. This is especially important for code inside large multi-line strings like HTML, where line numbers are misleading.
3.  Return your response as a JSON list of objects. Each object must have two keys: "remove" and "add".
4.  The "remove" value must be the **exact** string from the original code that you want to replace.
5.  The "add" value is the new text that will replace it.
6.  **To ensure the replacement is applied at the correct location, the `remove` value must correspond to a unique block of text in the code. If the code to be changed is short and not unique, you MUST expand the `remove` string to include surrounding lines to make it unique. The `add` string must then contain the same surrounding lines plus your change.** For example, to change `x = 1` to `x = 2` in a file with multiple `x = 1` assignments, you might set `remove` to `y = 0\\nx = 1\\nz = 2` and `add` to `y = 0\\nx = 2\\nz = 2`.
7.  If you only need to add code, make "remove" an empty string "" and specify where to add it in the "add" value, including surrounding lines for context. This is not for replacement but for insertion.
8.  If you only need to remove code, make "add" an empty string "". The `remove` string must still be unique.
9.  It is critical that the "remove" string is EXACTLY as it appears in the code, including all whitespace, newlines, and special characters.


You must respond with valid JSON that matches this exact schema:
{code_replacement_schema}
"""


user_prompt = """Please analyze this Python code and the error it produced. Propose specific text replacements to fix the error.

CODE:
```python
{code}
```

ERROR:
```
{error}
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
    """

    code: str
    error_log: str
    corrections_proposed: List[Dict[str, str]]
    current_retry: int
    max_retries: int
    final_result: str
    messages: List[BaseMessage]  # List of messages from the agent


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
    daytona_snapshot = "data-analysis:0.0.8"

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

    async def secure_sandbox_executor(code: str) -> dict:
        """
        Simulates a secure environment to execute Python code.
        In a real application, this would be a sandboxed environment like a Docker container.
        """
        try:
            # A simple check to simulate a common error.
            if "import non_existent_library" in code:
                raise ImportError("No module named 'non_existent_library'")

            # Another check for a logic error.
            if "result = 10 / 0" in code:
                raise ZeroDivisionError("division by zero")

            # If no errors, simulate a successful execution.
            return {"result": "Execution successful!", "error": ""}
        except Exception as e:
            # Return the error message if execution fails.
            return {"result": "", "error": f"{type(e).__name__}: {e}"}

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

        # Step 3: Escape curly braces within f-strings to prevent evaluation.
        def escape_braces_in_fstring_content(match):
            prefix, quote, content = match.groups()
            # Escape single curly braces, leaving double braces untouched.
            content = re.sub(r"(?<!{){(?!{)", "{{", content)
            content = re.sub(r"(?<!})}(?!})", "}}", content)
            return f"{prefix}{quote}{content}{quote}"

        fstring_pattern = re.compile(
            r"""(f|F|fr|Fr|fR|FR|rf|rF)\s*({"{3}|'{3}|"|')(.+?)\2""",
            re.DOTALL | re.VERBOSE,
        )
        code = fstring_pattern.sub(escape_braces_in_fstring_content, code)

        if code != original_code:
            logger.info("Applied HTML, Unicode, and f-string fixes to the code.")

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

        result_str = ""

        try:
            config = DaytonaSDKConfig(api_key=api_key)
            daytona = DaytonaClient(config)

            params = CreateSandboxFromSnapshotParams(
                snapshot=daytona_snapshot,
            )

            sandbox = await daytona.create(params=params)
            list_of_files = [f.name for f in await sandbox.fs.list_files(".")]

            # Execute the code with timeout and error handling
            try:
                response = await sandbox.process.code_run(state["code"])
            except Exception as exec_error:
                await daytona.close()
                logger.error(
                    "Code execution failed in sandbox",
                    error=str(exec_error),
                    exc_info=True,
                )
                return {
                    "error_log": "Error during code execution: " + str(exec_error),
                    "current_retry": state["current_retry"] + 1,
                }

            if response.exit_code != 0:
                # Ensure error detail is a string
                await daytona.close()
                error_detail = (
                    str(response.result) if response.result is not None else ""
                )
                logger.info(
                    "Daytona code execution failed",
                    exit_code=response.exit_code,
                    error_detail=error_detail,
                    original_code_preview=state["code"][:200],
                )
                return {
                    "error_log": f"Error (Exit Code {response.exit_code}): {error_detail}",
                    "current_retry": state["current_retry"] + 1,
                }
            else:
                result_str += f"Code executed successfully, result from the sandbox:\n\n {str(response.result) if response.result is not None else ''}"

            # Debug: Check what we got from the response
            logger.info(
                "Daytona response",
                exit_code=response.exit_code,
                result_preview=str(response.result)[:500],
                artifacts=response.artifacts,
                current_retry=state["current_retry"] + 1,
            )

            generation_timestamp = time.time()
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
                        elif mime_type in images_formats:
                            result_str += (
                                f"\n\n![{file.name}](redis-chart:{file_id}:{user_id})"
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

            return {
                "final_result": result_str,
                "current_retry": state["current_retry"] + 1,
                "error_log": "",
            }

        except Exception as e:
            logger.error("Daytona code execution failed", error=str(e), exc_info=True)
            return {
                "error_log": "Error during Daytona code execution: " + str(e),
                "current_retry": state["current_retry"] + 1,
            }

    async def analyze_error_and_propose_fix(state: CorrectingExecutorState) -> Dict:
        """
        Node 2: Analyzes the error and gets a proposed fix from the simulated LLM.
        """
        logger.info("Analyzing error and proposing a fix...")

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
                        code=state["code"], error=state["error_log"]
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

            return {
                "corrections_proposed": response.model_dump()["corrections"],
                "messages": captured_messages,
            }
        except Exception as e:
            logger.error(f"Error calling LLM for code fix: {e}", exc_info=True)
            return {"error_logs": f"Error calling LLM for code fix: {e}"}

    async def override_code(state: CorrectingExecutorState) -> Dict:
        """
        Node 3: Applies the proposed fix to the code in the state.
        """
        corrections = state["corrections_proposed"]
        if not corrections:
            logger.info("No corrections proposed. Halting.")
            return {}

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
                continue

            if to_remove and to_remove not in updated_code:
                logger.warning(
                    "Text to remove not found in code, skipping correction.",
                    to_remove=to_remove[:100],  # Log a preview
                )
                continue

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
                return "analyze_and_fix"
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
                return "analyze_and_fix"
            else:
                # If retries are exhausted, end the process.
                logger.info("Max Retries Reached")
                return END
        else:
            # If there's no error, the process is successful.
            return END

    workflow = StateGraph(CorrectingExecutorState)

    workflow.add_node("patch_code", patch_code)
    workflow.add_node("execute_code", execute_code)
    workflow.add_node("analyze_error_and_propose_fix", analyze_error_and_propose_fix)
    workflow.add_node("override_code", override_code)

    workflow.set_entry_point("patch_code")

    workflow.add_conditional_edges(
        "patch_code",
        should_continue_patch_code,
        {
            "analyze_and_fix": "analyze_error_and_propose_fix",
            "execute_code": "execute_code",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "execute_code",
        should_continue_execute_code,
        {
            "analyze_and_fix": "analyze_error_and_propose_fix",
            END: END,
        },
    )

    workflow.add_edge("analyze_error_and_propose_fix", "override_code")
    workflow.add_edge("override_code", "execute_code")

    # Compile and return
    return workflow.compile()


async def main():
    """
    The main asynchronous function to run the graph.
    """

    with open("/Users/tamasj/Downloads/code.txt", "r") as f:
        initial_buggy_code = f.read()

    # The graph now requires the 'code' and the retry logic to be in the initial input.
    initial_input = {
        "code": initial_buggy_code,
        "current_retry": 0,
        "max_retries": 10,
        "error_log": "",
        "final_result": "",
        "corrections_proposed": [],
    }

    logger.info("Starting Self-Correcting Subgraph (Async)")
    # Invoke the graph asynchronously with ainvoke
    final_state = await create_code_execution_graph(
        "user1", "f9c2c30f-faa3-464f-a8fd-e7d10160c4b1", None
    ).ainvoke(initial_input, {"recursion_limit": 50})

    print("\n🏁 Subgraph Finished. Final State: 🏁")
    print("========================================")
    print(f"Successful: {'Yes' if final_state.get('final_result') else 'No'}")
    print(f"Result: {final_state.get('final_result', 'N/A')}")
    print(f"Final Code:\n{final_state['code']}")
    print(f"Error Log:\n{final_state['error_log']}")
    print(f"Final Result:\n{final_state['final_result']}")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(main())
