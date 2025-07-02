import asyncio
import mimetypes
import os
import time
import uuid
from ast import List
from typing import Dict, TypedDict

import structlog
from agents.storage.redis_service import SecureRedisService
from agents.storage.redis_storage import RedisStorage
from agents.utils.code_validator import (
    patch_plot_code_str,
    strip_markdown_code_blocks,
    validate_and_fix_html_content,
)
from daytona_sdk import AsyncDaytona as DaytonaClient
from daytona_sdk import CreateSandboxFromSnapshotParams
from daytona_sdk import DaytonaConfig as DaytonaSDKConfig
from langgraph.graph import END, StateGraph

logger = structlog.get_logger(__name__)


class CorrectingExecutorState(TypedDict):
    """
    Represents the state for a self-correcting code execution task.

    Attributes:
        code: The Python code to execute. This is modified by the correction loop.
        error_log: The error message from the last failed attempt.
        corrections_proposed: A dictionary mapping line numbers to the corrected code.
                              This is a transient field, used only to pass the fix
                              from the analysis node to the override node.
        current_retry: The current attempt number.
        max_retries: The maximum number of correction attempts allowed.
        final_result: The successful output of the code.
    """

    code: str
    expected_filenames: List[str]
    error_log: str
    corrections_proposed: Dict[int, str]
    current_retry: int
    max_retries: int
    final_result: str


def create_code_execution_graph(user_id: str, redis_storage: RedisStorage):
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

    async def patch_code(state: CorrectingExecutorState) -> Dict:
        """
        Patches the code to fix the error.
        """

        try:
            # Strip markdown formatting before processing
            clean_code = strip_markdown_code_blocks(state["code"])

        except Exception as e:
            logger.infor("Error cleaning code", error=str(e), exc_info=True)
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

        try:
            patched_code, expected_filenames = patch_plot_code_str(clean_code)
        except Exception as e:
            logger.info("Error patching code", error=str(e), exc_info=True)
            return {
                "error_log": "Error patching code: " + str(e),
            }

        return {"code": patched_code, "expected_filenames": expected_filenames}

    async def execute_code(state: CorrectingExecutorState) -> Dict:
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
                return {"error_log": "Error during code execution: " + str(exec_error)}

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
                    original_code_preview=state["code"][:200],
                )
                return {
                    "error_log": f"Error (Exit Code {response.exit_code}): {error_detail}"
                }

            # Debug: Check what we got from the response
            logger.info(
                "Daytona response",
                exit_code=response.exit_code,
                result_preview=str(response.result)[:500],
                artifacts=response.artifacts,
            )

            generation_timestamp = time.time()

            # Process expected filenames first
            for filename in state["expected_filenames"]:
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

            return {"final_result": result_str}

        except Exception as e:
            logger.error("Daytona code execution failed", error=str(e), exc_info=True)
            return {"error_log": "Error during Daytona code execution: " + str(e)}

    async def analyze_error_and_propose_fix(state: CorrectingExecutorState) -> Dict:
        """
        Node 2: Analyzes the error and gets a proposed fix from the simulated LLM.
        """
        print("\n--- Analyzing Error ---")
        proposed_fix = await llm_propose_fix(state["code"], state["error_log"])
        return {"corrections_proposed": proposed_fix}

    async def override_code(state: CorrectingExecutorState) -> Dict:
        """
        Node 3: Applies the proposed fix to the code in the state.
        """
        print("\n--- Overriding Code ---")
        corrections = state["corrections_proposed"]
        if not corrections:
            print("No corrections proposed. Halting.")
            return {}

        code_lines = state["code"].splitlines()
        for line_num, new_code in corrections.items():
            print(f"Applying fix at line {line_num}: '{new_code}'")
            # Adjust for 0-based index
            code_lines[line_num - 1] = new_code

        updated_code = "\n".join(code_lines)
        return {"code": updated_code}

    async def llm_propose_fix(code: str, error: str) -> Dict[int, str]:
        """
        Simulates an LLM call to get a code correction.
        In a real application, this would call an API like GPT-4 or Gemini.
        """
        print("🤖 LLM analyzing error and proposing a fix...")
        # Simulate the LLM's logic based on the error.
        if "No module named 'non_existent_library'" in error:
            # Find the line with the bad import and propose a fix.
            for i, line in enumerate(code.splitlines()):
                if "import non_existent_library" in line:
                    return {i + 1: "    import os  # Corrected import"}

        if "division by zero" in error:
            # Find the line with the division by zero and propose a fix.
            for i, line in enumerate(code.splitlines()):
                if "10 / 0" in line:
                    return {i + 1: "    result = 10 / 1  # Avoid division by zero"}

        # Default case if the error is unknown to the mock LLM.
        return {}

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
                print("\n--- Max Retries Reached ---")
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
                print("\n--- Max Retries Reached ---")
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
    workflow.add_edge("override_code", "execute_code")  # This creates the loop

    # Compile and return
    return workflow.compile()


async def main():
    """
    The main asynchronous function to run the graph.
    """
    # Define the initial buggy code to be passed as input.
    initial_buggy_code = (
        "def my_function():\n"
        "    # Intentionally buggy code\n"
        "    import non_existent_library\n"
        "    print('This will not run initially')\n"
        "\n"
        "my_function()"
    )

    # The graph now requires the 'code' and the retry logic to be in the initial input.
    initial_input = {
        "code": initial_buggy_code,
        "current_retry": 0,
        "max_retries": 3,
    }

    print("🚀 Starting Self-Correcting Subgraph (Async)...\n")
    # Invoke the graph asynchronously with ainvoke
    final_state = await create_code_execution_graph(None).ainvoke(initial_input)

    print("\n🏁 Subgraph Finished. Final State: 🏁")
    print("========================================")
    print(f"Successful: {'Yes' if final_state.get('final_result') else 'No'}")
    print(f"Result: {final_state.get('final_result', 'N/A')}")
    print(f"Final Code:\n{final_state['code']}")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(main())
