"""
Human choice handling for SWE agent workflow.
Similar to datagen's human interrupt implementation.
"""

import uuid
import structlog
from typing import Dict, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.types import interrupt

logger = structlog.get_logger(__name__)


def drop_think_section(content: str) -> str:
    """Remove any <think> sections from content"""
    if "<think>" in content and "</think>" in content:
        # Remove everything between <think> and </think>
        import re
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
    return content.strip()


async def swe_human_choice_node(state: Dict[str, Any], llm: BaseChatModel) -> Dict[str, Any]:
    """
    Handle human input to choose the next step in the SWE process.
    If user provides feedback, incorporate it. If approved, continue.
    """
    logger.info("Processing SWE human choice node")
    
    # Get the current implementation plan from state
    current_plan = getattr(state, "implementation_plan", "No implementation plan yet.")
    
    # Format the plan for display
    if hasattr(current_plan, 'model_dump'):
        plan_display = f"Implementation Plan:\n{current_plan.model_dump()}"
    elif isinstance(current_plan, dict):
        plan_display = f"Implementation Plan:\n{current_plan}"
    else:
        plan_display = f"Implementation Plan:\n{str(current_plan)}"
    
    prompt = (
        "Please <b>review the implementation plan</b> and either approve it or provide feedback.\n\n"
        + plan_display
        + "\n\nOptions:\n"
        + "- Say 'approved' to proceed with implementation\n"
        + "- Provide specific feedback to refine the plan\n"
        + "- Ask questions about the approach"
    )

    feedback = interrupt(prompt)
    logger.debug(f"Received SWE feedback: {feedback}")

    # Classify the feedback
    classification_prompt = f"""
TASK: Classify user feedback for SWE implementation plan. Respond with a single label only.
LABELS: APPROVE, REVISE
RULE: Any question, doubt, suggestion, or request for changes requires the REVISE label.

---
Input: Looks great, let's implement it.
Output: APPROVE

Input: approved
Output: APPROVE

Input: Can we use a different approach for authentication?
Output: REVISE

Input: What about error handling?
Output: REVISE

Input: ok let's go
Output: APPROVE
---
Input: {feedback}
Output:
"""

    result = await llm.ainvoke(
        [SystemMessage(content=classification_prompt), HumanMessage(content=feedback)]
    )

    result.additional_kwargs = result.additional_kwargs or {}
    result.additional_kwargs["agent_type"] = "swe_human_choice"

    update_state = {}
    cleaned_feedback = drop_think_section(result.content)

    if "APPROVE" in cleaned_feedback:
        content = "Implementation plan approved - proceed with development"
        update_state["human_feedback"] = ""
        update_state["plan_approved"] = True
        logger.info("Human approved SWE plan - proceeding with implementation")
    elif "REVISE" in cleaned_feedback:
        human_feedback = feedback
        content = f"Plan needs revision. Feedback: {human_feedback}"
        update_state["human_feedback"] = human_feedback
        update_state["plan_approved"] = False
        update_state["implementation_plan"] = None  # Clear plan to trigger regeneration
        logger.info("Human provided SWE feedback - plan needs revision")
        logger.debug(f"Feedback: {human_feedback}")
    else:
        # Default to approve if unclear
        content = "Implementation plan approved - proceed with development"
        update_state["human_feedback"] = ""
        update_state["plan_approved"] = True
        logger.info("Unclear feedback - defaulting to approval")

    human_message = HumanMessage(content=content, id=str(uuid.uuid4()))

    logger.info("SWE human choice node processing completed")
    return {
        **update_state,
        "implementation_research_scratchpad": [human_message],
        "messages": [result],
        "sender": "human",
    }


def swe_human_choice_router(state: Dict[str, Any]) -> str:
    """
    Route based on human choice: regenerate plan or continue to implementation.
    """
    logger.info("Entering SWE human choice router")
    
    # Check if user wants to revise the plan
    if getattr(state, "human_feedback", None) and not getattr(state, "plan_approved", False):
        logger.info("User requested plan revision. Routing to: architect")
        return "architect"
    elif getattr(state, "plan_approved", False):
        logger.info("User approved plan. Routing to: developer")
        return "developer"
    
    # Default to architect if unclear
    logger.info("Unclear choice, defaulting to: architect")
    return "architect" 