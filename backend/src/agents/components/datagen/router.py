import json
import re
from typing import Dict, List, Literal, Optional, Union

import structlog
from agents.components.datagen.state import State, SupervisorDecision
from langchain_core.messages import AIMessage

# Set up logger
logger = structlog.getLogger(__name__)

# Define types for node routing
NodeType = Literal[
    "Visualization",
    "Search",
    "Coder",
    "Report",
    "Process",
    "NoteTaker",
    "Hypothesis",
    "QualityReview",
]
ProcessNodeType = Literal[
    "Coder", "Search", "Visualization", "Report", "Process", "Refiner"
]


def human_choice_router(state: State) -> NodeType:
    """
    Route based on human choice: regenerate hypothesis or continue to process.

    Args:
        state (State): The current state of the system.

    Returns:
        NodeType: 'Hypothesis' if user chose to regenerate, 'Process' if continuing.
    """
    logger.info("Entering human_choice_router")

    # Check if user chose to regenerate hypothesis (choice 1)
    if "modification_areas" in state and state["modification_areas"]:
        logger.info("User chose to regenerate hypothesis. Routing to: Hypothesis")
        return "Hypothesis"

    # Check if user chose to continue (choice 2)
    process_content = state.get("process", "")
    if "continue the research process" in str(process_content).lower():
        logger.info("User chose to continue research. Routing to: Process")
        return "Process"

    # Default to Process if unclear
    logger.info("Unclear choice, defaulting to: Process")
    return "Process"


def hypothesis_router(state: State) -> NodeType:
    """
    Route based on the presence of a hypothesis in the state and tool usage.

    If hypothesis agent used tools (ReAct pattern), route back to Hypothesis for next iteration.
    Otherwise, continue to Process.

    Args:
        state (State): The current state of the system.

    Returns:
        NodeType: 'Hypothesis' if no hypothesis exists or tools were used, otherwise 'Process'.
    """
    logger.info("Entering hypothesis_router")
    hypothesis: Union[AIMessage, str, None] = state.get("hypothesis")

    try:
        if isinstance(hypothesis, AIMessage):
            hypothesis_content = hypothesis.content
            logger.debug("Hypothesis is an AIMessage")
        elif isinstance(hypothesis, str):
            hypothesis_content = hypothesis
            logger.debug("Hypothesis is a string")
        else:
            hypothesis_content = ""
            logger.warning(f"Unexpected hypothesis type: {type(hypothesis)}")

        if not isinstance(hypothesis_content, str):
            hypothesis_content = str(hypothesis_content)
            logger.warning("Converting hypothesis content to string")
    except Exception as e:
        logger.error(f"Error processing hypothesis: {e}")
        hypothesis_content = ""

    # If no hypothesis content, route back to Hypothesis
    if not hypothesis_content.strip():
        result = "Hypothesis"
        logger.info(f"No hypothesis content found. Routing to: {result}")
        return result

    # Check if the hypothesis agent used tools (ReAct pattern)
    # Look for tool usage indicators: <tool>, <observation>, or other tool-related patterns
    used_tools = (
        "<tool>" in hypothesis_content
        or "<observation>" in hypothesis_content
        or "</tool_input>" in hypothesis_content
    )

    if used_tools:
        result = "Hypothesis"
        logger.info(
            f"Hypothesis agent used tools. Continuing ReAct loop. Routing to: {result}"
        )
    else:
        # If it's not clearly final and no tools were used, continue one more iteration
        result = "HumanChoice"
        logger.info(f"Final hypothesis detected. Routing to: {result}")

    return result


def QualityReview_router(state: State) -> NodeType:
    """
    Route based on the quality review outcome and process decision.

    Args:
    state (State): The current state of the system.

    Returns:
    NodeType: The next node to route to based on the quality review and process decision.
    """
    logger.info("Entering QualityReview_router")
    messages = state.get("internal_messages", [])
    message_before_revision = messages[-2] if len(messages) > 1 else None

    # Check if revision is needed
    if state.get("needs_revision", False):
        previous_node = (
            message_before_revision.sender if message_before_revision else ""
        )
        revision_routes = {
            "visualization_agent": "Visualization",
            "search_agent": "Search",
            "code_agent": "Coder",
            "report_agent": "Report",
        }
        result = revision_routes.get(previous_node, "NoteTaker")
        logger.info(f"Revision needed. Routing to: {result}")
        return result

    else:
        return "NoteTaker"


def process_router(state: State) -> ProcessNodeType:
    """
    Route based on the process decision in the state.

    Args:
        state (State): The current state of the system.

    Returns:
        ProcessNodeType: The next process node to route to based on the process decision.
    """
    logger.info("Entering process_router")
    process_decision: Union[AIMessage, Dict, str, None] = state.get(
        "process_decision", ""
    )

    decision_str: str = ""

    try:
        if isinstance(process_decision, AIMessage):
            # Parse decision from AIMessage content
            # Expected format: "Decision: Coder\nTask: ..."
            content = process_decision.content
            decision_match = re.search(r"Decision:\s*(\w+)", content)
            if decision_match:
                decision_str = decision_match.group(1)
            logger.debug(f"Parsed decision from AIMessage: {decision_str}")
        elif isinstance(process_decision, dict):
            decision_str = str(process_decision.get("next", ""))
        else:
            decision_str = str(process_decision)
    except Exception as e:
        logger.error(f"Error processing decision: {e}")
        decision_str = ""

    # Define valid decisions
    valid_decisions = {"Coder", "Search", "Visualization", "Report"}

    if decision_str in valid_decisions:
        logger.info(f"Valid process decision: {decision_str}")
        return decision_str

    if decision_str == "FINISH":
        logger.info("Process decision is FINISH. Ending process.")
        return "Refiner"

    # If decision_str is empty or not a valid decision, return "Process"
    if not decision_str or decision_str not in valid_decisions:
        logger.warning(
            f"Invalid or empty process decision: {decision_str}. Defaulting to 'Process'."
        )
        return "Process"

    # Default to "Process"
    logger.info("Defaulting to 'Process'")
    return "Process"


logger.info("Router module initialized")
