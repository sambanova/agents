"""
Streaming state management for SWE agents.
Follows the same pattern as datagen for consistent frontend streaming.
"""
import operator
from typing import Annotated, Sequence, TypedDict, Optional
from langchain_core.messages import AnyMessage, BaseMessage, AIMessage, HumanMessage
from pydantic import BaseModel, Field
from agents.components.swe.agent.common.entities import ImplementationPlan


def add_messages(
    left: Sequence[AnyMessage], right: Sequence[AnyMessage]
) -> Sequence[AnyMessage]:
    """Custom reducer that adds messages to the state."""
    return left + right


def replace_messages(
    left: Sequence[AnyMessage], right: Sequence[AnyMessage]
) -> Sequence[AnyMessage]:
    """
    Custom reducer that replaces messages entirely with the new ones.
    Used for frontend messages that should be replaced per agent execution.
    """
    # If right is empty, keep left to avoid clearing messages unintentionally
    if not right:
        return left if left else []

    # Convert to list if needed
    if not isinstance(right, list):
        right = list(right)

    return right


def update_step_tracker(left: str, right: str) -> str:
    """Custom reducer for tracking SWE process steps."""
    if not right:
        return left
    return right


class SWEStreamingState(TypedDict):
    """
    Streaming state for SWE agents that supports frontend streaming.
    Follows the same pattern as datagen for consistency.
    """
    
    # Internal messages for agent-to-agent communication
    internal_messages: Annotated[Sequence[AnyMessage], add_messages]
    
    # Messages to be sent to the frontend (streaming)
    messages: Annotated[Sequence[AnyMessage], replace_messages]
    
    # Implementation research scratchpad (internal)
    implementation_research_scratchpad: Annotated[Sequence[AnyMessage], add_messages]
    
    # Atomic implementation research (internal)
    atomic_implementation_research: Annotated[Sequence[AnyMessage], add_messages]
    
    # Current step being executed
    current_step: Annotated[str, update_step_tracker]
    
    # Repository context
    repository_context: Annotated[dict, lambda left, right: right]
    
    # Implementation plan
    implementation_plan: Annotated[Optional[ImplementationPlan], lambda left, right: right]
    
    # Research next step
    research_next_step: Annotated[Optional[str], lambda left, right: right]
    
    # Validation flags
    is_valid_research_step: Annotated[Optional[bool], lambda left, right: right]
    
    # Atomic task tracking
    atomic_tasks_completed: Annotated[int, lambda left, right: right]
    total_atomic_tasks: Annotated[int, lambda left, right: right]
    
    # Current working directory in Daytona
    working_directory: Annotated[str, lambda left, right: right]
    
    # Git branch being worked on
    current_branch: Annotated[str, lambda left, right: right]
    
    # Progress tracking for frontend
    progress_percentage: Annotated[int, lambda left, right: right]
    
    # Status for frontend display
    status: Annotated[str, lambda left, right: right]


def create_step_message(step_name: str, description: str, status: str = "in_progress") -> AIMessage:
    """
    Create a standardized step message for frontend streaming.
    
    Args:
        step_name: Name of the current step
        description: Description of what's happening
        status: Status of the step (in_progress, completed, failed)
    
    Returns:
        AIMessage formatted for frontend consumption
    """
    icons = {
        "in_progress": "🔄",
        "completed": "✅",
        "failed": "❌",
        "research": "🔍",
        "planning": "📋",
        "implementation": "⚙️",
        "testing": "🧪",
        "github": "📁"
    }
    
    # Determine icon based on step name or status
    icon = icons.get(status, "🔄")
    if "research" in step_name.lower():
        icon = icons["research"]
    elif "plan" in step_name.lower():
        icon = icons["planning"]
    elif "implement" in step_name.lower():
        icon = icons["implementation"]
    elif "test" in step_name.lower():
        icon = icons["testing"]
    elif "github" in step_name.lower() or "repo" in step_name.lower():
        icon = icons["github"]
    
    content = f"{icon} **{step_name}**\n\n{description}"
    
    return AIMessage(
        content=content,
        additional_kwargs={
            "agent_type": "swe_step",
            "step_name": step_name,
            "status": status,
            "timestamp": "",  # Will be filled by the system
        }
    )


def create_progress_message(
    current_task: int, 
    total_tasks: int, 
    task_description: str,
    repository_name: str = ""
) -> AIMessage:
    """
    Create a progress update message for frontend streaming.
    
    Args:
        current_task: Current task number
        total_tasks: Total number of tasks
        task_description: Description of current task
        repository_name: Name of the repository being worked on
    
    Returns:
        AIMessage with progress information
    """
    # Safely handle None values
    current_task = current_task if current_task is not None else 0
    total_tasks = total_tasks if total_tasks is not None else 1
    task_description = task_description if task_description is not None else "Unknown task"
    repository_name = repository_name if repository_name is not None else ""
    
    percentage = int((current_task / total_tasks) * 100) if total_tasks > 0 else 0
    
    repo_info = f" in **{repository_name}**" if repository_name else ""
    
    content = f"""📊 **Progress Update**

**Task {current_task} of {total_tasks}** ({percentage}% complete){repo_info}

🎯 **Current Task:** {task_description}

---
*Working on implementation...*"""
    
    return AIMessage(
        content=content,
        additional_kwargs={
            "agent_type": "swe_progress",
            "current_task": current_task,
            "total_tasks": total_tasks,
            "percentage": percentage,
            "repository_name": repository_name,
        }
    )


def create_repository_context_message(repo_info: dict) -> AIMessage:
    """
    Create a repository context message for frontend display.
    
    Args:
        repo_info: Repository information dictionary
    
    Returns:
        AIMessage with repository context
    """
    # Safely handle None values and missing keys
    if not repo_info or not isinstance(repo_info, dict):
        repo_info = {}
    
    repo_name = repo_info.get("full_name", "Unknown Repository") or "Unknown Repository"
    description = repo_info.get("description", "No description available") or "No description available"
    language = repo_info.get("language", "Unknown") or "Unknown"
    branch = repo_info.get("branch", "main") or "main"
    
    content = f"""📁 **Repository Context Set**

**Repository:** {repo_name}
**Branch:** {branch}
**Language:** {language}

**Description:** {description}

🔄 Analyzing repository structure and preparing for implementation..."""
    
    # Create a clean repo_info dict without None values
    clean_repo_info = {}
    for key, value in repo_info.items():
        if value is not None:
            clean_repo_info[key] = value
    
    return AIMessage(
        content=content,
        additional_kwargs={
            "agent_type": "swe_repository_context",
            "repository": clean_repo_info,
        }
    )


def create_implementation_plan_message(plan: ImplementationPlan) -> AIMessage:
    """
    Create an implementation plan message for frontend display.
    
    Args:
        plan: Implementation plan object
    
    Returns:
        AIMessage with implementation plan details
    """
    if not plan or not plan.tasks:
        return AIMessage(
            content="📋 **Implementation Plan**\n\nNo specific tasks identified. Proceeding with general analysis.",
            additional_kwargs={"agent_type": "swe_implementation_plan"}
        )
    
    task_list = []
    for i, task in enumerate(plan.tasks[:10], 1):  # Show first 10 tasks
        task_list.append(f"{i}. **{task.logical_task}**\n   📄 File: `{task.file_path}`")
    
    if len(plan.tasks) > 10:
        task_list.append(f"... and {len(plan.tasks) - 10} more tasks")
    
    tasks_text = "\n\n".join(task_list)
    
    content = f"""📋 **Implementation Plan Created**

**Total Tasks:** {len(plan.tasks)}

**Implementation Steps:**

{tasks_text}

---
*Starting implementation process...*"""
    
    # Safely serialize the plan data to avoid None values
    plan_data = None
    try:
        if hasattr(plan, 'model_dump'):
            plan_data = plan.model_dump()
            # Remove any None values from the plan data
            if isinstance(plan_data, dict):
                plan_data = {k: v for k, v in plan_data.items() if v is not None}
        else:
            plan_data = str(plan)
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.warning("Failed to serialize implementation plan", error=str(e))
        plan_data = f"Implementation plan with {len(plan.tasks)} tasks"
    
    additional_kwargs = {
        "agent_type": "swe_implementation_plan",
        "total_tasks": len(plan.tasks),
    }
    
    # Only add plan data if it's safe to serialize
    if plan_data and plan_data != "":
        additional_kwargs["plan"] = plan_data
    
    return AIMessage(
        content=content,
        additional_kwargs=additional_kwargs
    )


# Helper functions for state updates
def update_streaming_state(
    state: SWEStreamingState,
    step_name: str = None,
    description: str = None,
    status: str = "in_progress",
    progress: tuple = None,  # (current, total)
    repository_context: dict = None,
    implementation_plan: ImplementationPlan = None,
) -> dict:
    """
    Helper function to update streaming state with frontend messages.
    
    Args:
        state: Current SWE streaming state
        step_name: Name of the current step
        description: Description of the step
        status: Status of the step
        progress: Tuple of (current_task, total_tasks)
        repository_context: Repository context dictionary
        implementation_plan: Implementation plan object
    
    Returns:
        Dictionary of state updates
    """
    updates = {}
    frontend_messages = []
    
    # Add step message if provided
    if step_name and description:
        frontend_messages.append(create_step_message(step_name, description, status))
        updates["current_step"] = step_name
        updates["status"] = status
    
    # Add progress message if provided
    if progress:
        current_task, total_tasks = progress
        repo_name = ""
        if repository_context:
            repo_name = repository_context.get("full_name", "")
        
        if step_name:
            task_desc = description or step_name
        else:
            task_desc = "Processing implementation task"
            
        frontend_messages.append(create_progress_message(current_task, total_tasks, task_desc, repo_name))
        updates["atomic_tasks_completed"] = current_task
        updates["total_atomic_tasks"] = total_tasks
        updates["progress_percentage"] = int((current_task / total_tasks) * 100) if total_tasks > 0 else 0
    
    # Add repository context message if provided
    if repository_context:
        frontend_messages.append(create_repository_context_message(repository_context))
        updates["repository_context"] = repository_context
    
    # Add implementation plan message if provided
    if implementation_plan:
        frontend_messages.append(create_implementation_plan_message(implementation_plan))
        updates["implementation_plan"] = implementation_plan
    
    # Update messages for frontend streaming
    if frontend_messages:
        updates["messages"] = frontend_messages
    
    return updates 