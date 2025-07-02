import asyncio
from typing import Dict, TypedDict

import structlog
from agents.storage.redis_service import SecureRedisService
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
    error_log: str
    corrections_proposed: Dict[int, str]
    current_retry: int
    max_retries: int
    final_result: str


def create_code_execution_graph(redis_client: SecureRedisService):
    logger.info("Creating code execution subgraph")

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

    async def execute_code(state: CorrectingExecutorState) -> Dict:
        """
        Node 1: Executes the code and updates the state with the result or error.
        """
        print(
            "\n--- Executing Code (Attempt {}) ---".format(state["current_retry"] + 1)
        )
        print(state["code"])
        print("------------------------------------")

        execution_output = await secure_sandbox_executor(state["code"])

        if execution_output["error"]:
            print(f"❌ Execution Failed: {execution_output['error']}")
            return {
                "error_log": execution_output["error"],
                "current_retry": state["current_retry"] + 1,
            }
        else:
            print("✅ Execution Succeeded!")
            return {"error_log": "", "final_result": execution_output["result"]}

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

    async def should_continue(state: CorrectingExecutorState) -> str:
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

    workflow.add_node("execute_code", execute_code)
    workflow.add_node("analyze_error_and_propose_fix", analyze_error_and_propose_fix)
    workflow.add_node("override_code", override_code)

    workflow.set_entry_point("execute_code")

    workflow.add_conditional_edges(
        "execute_code",
        should_continue,
        {"analyze_and_fix": "analyze_error_and_propose_fix", END: END},
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
