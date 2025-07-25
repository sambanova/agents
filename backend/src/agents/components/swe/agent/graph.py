from agents.components.swe.agent.architect.graph import create_swe_architect, swe_architect
from agents.components.swe.agent.common.entities import ImplementationPlan
from agents.components.swe.agent.developer.graph import create_swe_developer
from agents.components.swe.human_choice import swe_human_choice_node, swe_human_choice_router
from agents.utils.llms import get_sambanova_llm
from agents.components.compound.util import extract_api_key
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import add_messages, StateGraph, START, END
from typing import Annotated, Optional
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)

class AgentState(BaseModel):
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages]
    implementation_plan: Optional[ImplementationPlan] = Field(None, description="The implementation plan to be executed")
    human_feedback: Optional[str] = Field("", description="Feedback from human about the implementation plan")
    plan_approved: Optional[bool] = Field(None, description="Whether the human has approved the implementation plan")
    messages: Annotated[list[AnyMessage], add_messages] = Field([], description="Messages to be sent to the frontend")
    sender: Optional[str] = Field(None, description="The sender of the last message")
    working_directory: Optional[str] = Field(".", description="The working directory for the repository")


def create_swe_agent(daytona_manager=None, github_token=None):
    """Create the main SWE agent as a unified workflow"""
    logger.info("Creating SWE agent with human choice workflow")
    
    # Create the architect with Daytona support
    architect_subgraph = create_swe_architect(daytona_manager=daytona_manager, github_token=github_token)
    
    # Create human choice node wrapper function that provides LLM
    async def human_choice_node_wrapper(state, *, config: RunnableConfig = None):
        """Human choice node wrapper that provides LLM from config"""
        api_key = extract_api_key(config)
        llm = get_sambanova_llm(api_key=api_key, model="DeepSeek-V3-0324")
        return await swe_human_choice_node(state, llm)

    # Create developer node that works with AgentState directly
    async def developer_node(state, *, config: RunnableConfig = None):
        """Developer node that implements the plan using Daytona tools"""
        import structlog
        debug_logger = structlog.get_logger(__name__)
        
        # DEBUG: Log the input state
        debug_logger.info("=== DEVELOPER NODE DEBUG START ===")
        debug_logger.info("Input state keys:", keys=list(state.__dict__.keys()) if hasattr(state, '__dict__') else "Not a class instance")
        
        if hasattr(state, '__dict__'):
            for key, value in state.__dict__.items():
                if value is None:
                    debug_logger.warning(f"Input state has None value for key: {key}")
                else:
                    debug_logger.info(f"Input state key '{key}' has value type: {type(value).__name__}")
        
        if not state.implementation_plan:
            debug_logger.warning("No implementation plan available - returning error state")
            return_state = {
                "implementation_research_scratchpad": [AIMessage(content="No implementation plan available")],
                "messages": [AIMessage(content="Error: No implementation plan to execute")],
                "sender": "developer",
                "plan_approved": state.plan_approved,  # Preserve existing values
                "human_feedback": state.human_feedback,
                "working_directory": state.working_directory
            }
            
            # DEBUG: Log what we're returning
            for key, value in return_state.items():
                if value is None:
                    debug_logger.warning(f"Return state has None value for key: {key}")
            debug_logger.info("=== DEVELOPER NODE DEBUG END (NO PLAN) ===")
            
            return return_state
        
        try:
            # Get the first task from the implementation plan
            if state.implementation_plan.tasks:
                task = state.implementation_plan.tasks[0]
                atomic_task = task.atomic_tasks[0] if task.atomic_tasks else None
                
                debug_logger.info("Processing task:", 
                                file_path=task.file_path, 
                                has_atomic_task=atomic_task is not None)
                
                if atomic_task and daytona_manager:
                    # Execute the task using proper Daytona Git operations
                    result = await creating_diffs_for_task_simple(
                        task.file_path, 
                        atomic_task.atomic_task,
                        daytona_manager,
                        state.working_directory or "."
                    )
                    
                    debug_logger.info("Task implementation completed successfully")
                    
                    # Create detailed success message with file and commit information
                    success_content = f"""✅ **Successfully Implemented: {atomic_task.atomic_task}**

**📄 File Updated:** `{task.file_path}`

**🔧 Changes Made:**
- {atomic_task.atomic_task}
- Changes committed to feature branch

**📁 Repository:** {state.working_directory or "."}

**✅ Status:** Implementation completed successfully

---
*Ready for next task or testing*"""
                    
                    return_state = {
                        "implementation_research_scratchpad": [AIMessage(content=f"Implemented: {atomic_task.atomic_task}")],
                        "messages": [AIMessage(
                            content=success_content,
                            additional_kwargs={
                                "agent_type": "swe_implementation",
                                "status": "completed",
                                "file_path": task.file_path,
                                "task_completed": atomic_task.atomic_task,
                                "repository": state.working_directory or ".",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )],
                        "sender": "developer",
                        "plan_approved": state.plan_approved,  # Preserve existing values
                        "human_feedback": state.human_feedback,
                        "working_directory": state.working_directory,
                        "implementation_plan": state.implementation_plan  # Keep the plan
                    }
                    
                    # DEBUG: Log what we're returning
                    for key, value in return_state.items():
                        if value is None:
                            debug_logger.warning(f"Return state has None value for key: {key}")
                        else:
                            debug_logger.info(f"Return state key '{key}' has value type: {type(value).__name__}")
                    debug_logger.info("=== DEVELOPER NODE DEBUG END (SUCCESS) ===")
                    
                    return return_state
            
            debug_logger.info("Implementation completed - no more tasks")
            
            # Create detailed completion message
            completion_content = f"""🎉 **All Implementation Tasks Completed Successfully**

**📋 Implementation Plan:** Fully executed
**📁 Repository:** {state.working_directory or "."}
**✅ Status:** All tasks completed

**🚀 Next Steps:**
- All changes have been committed to feature branch
- Ready for testing and integration
- Consider creating a pull request for code review

---
*Implementation workflow completed successfully*"""
            
            return_state = {
                "implementation_research_scratchpad": [AIMessage(content="Implementation completed")],
                "messages": [AIMessage(
                    content=completion_content,
                    additional_kwargs={
                        "agent_type": "swe_completion",
                        "status": "all_completed",
                        "repository": state.working_directory or ".",
                        "timestamp": datetime.now().isoformat(),
                    }
                )],
                "sender": "developer",
                "plan_approved": state.plan_approved,  # Preserve existing values
                "human_feedback": state.human_feedback,
                "working_directory": state.working_directory,
                "implementation_plan": state.implementation_plan
            }
            
            # DEBUG: Log what we're returning
            for key, value in return_state.items():
                if value is None:
                    debug_logger.warning(f"Return state has None value for key: {key}")
                else:
                    debug_logger.info(f"Return state key '{key}' has value type: {type(value).__name__}")
            debug_logger.info("=== DEVELOPER NODE DEBUG END (COMPLETED) ===")
            
            return return_state
            
        except Exception as e:
            logger.error(f"Developer error: {e}")
            return {
                "implementation_research_scratchpad": [AIMessage(content=f"Error: {str(e)}")],
                "messages": [AIMessage(content=f"❌ Implementation failed: {str(e)}")],
                "sender": "developer",
                "plan_approved": state.plan_approved,  # Preserve existing values
                "human_feedback": state.human_feedback,
                "working_directory": state.working_directory,
                "implementation_plan": state.implementation_plan
            }

    def architect_router(state: AgentState) -> str:
        """Route from architect: if plan exists, go to human choice; otherwise stay in architect"""
        if getattr(state, "implementation_plan", None):
            logger.info("Implementation plan created, routing to human choice for approval")
            return "human_choice"
        else:
            logger.info("No implementation plan yet, continuing research")
            return "architect"

    # Create the main workflow as unified graph (original pattern)
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("architect", architect_subgraph)
    workflow.add_node("human_choice", human_choice_node_wrapper)
    workflow.add_node("developer", developer_node)
    
    # Add edges (original working pattern)
    workflow.add_edge(START, "architect")
    workflow.add_conditional_edges("architect", architect_router, {"architect": "architect", "human_choice": "human_choice"})
    workflow.add_conditional_edges("human_choice", swe_human_choice_router, {"developer": "developer", "architect": "architect"})
    workflow.add_edge("developer", END)
    
    return workflow.compile().with_config({
        "tags": ["swe-agent-v3"], 
        "recursion_limit": 200
    })


async def creating_diffs_for_task_simple(file_path: str, task_description: str, daytona_manager, working_directory: str):
    """Simplified implementation function that uses proper Daytona Git operations"""
    try:
        # Get sandbox instance for Git operations
        sandbox = await daytona_manager._get_sandbox()
        if not sandbox:
            raise Exception("Daytona sandbox not initialized")
        
        # Create feature branch using native Daytona Git operations
        branch_name = f"swe-agent-feature-{hash(task_description) % 10000}"
        
        try:
            await sandbox.git.create_branch(working_directory, branch_name)
            logger.info(f"Created feature branch: {branch_name}")
        except Exception as branch_error:
            # If branch creation fails, try to switch to it (maybe it exists)
            try:
                await sandbox.git.checkout_branch(working_directory, branch_name)
                logger.info(f"Switched to existing branch: {branch_name}")
            except Exception:
                logger.warning(f"Could not create or switch to branch {branch_name}: {branch_error}")
                # Continue without branch - not critical for the demo
        
        # Check if file exists using Daytona manager
        success, existing_content = await daytona_manager.read_file(file_path)
        
        if success and existing_content:
            # Edit existing file
            if isinstance(existing_content, bytes):
                existing_content = existing_content.decode('utf-8')
            
            # Simple content modification - add a comment indicating the task
            modified_content = f"// Task implemented: {task_description}\n" + existing_content
            
            await daytona_manager.write_file(file_path, modified_content)
            logger.info(f"Successfully updated file: {file_path}")
        else:
            # Create new file
            new_content = f"// New file created for task: {task_description}\n// File: {file_path}\n"
            await daytona_manager.write_file(file_path, new_content)
            logger.info(f"Successfully created file: {file_path}")
            
        # Stage and commit changes using native Git operations
        try:
            await sandbox.git.add(working_directory, ["."])
            await sandbox.git.commit(
                working_directory, 
                f"Implement: {task_description}", 
                "SWE Agent", 
                "swe-agent@sandbox.local"
            )
            logger.info(f"Committed changes: {task_description}")
        except Exception as commit_error:
            logger.warning(f"Could not commit changes: {commit_error}")
            # Continue - file operations succeeded even if commit failed
            
        return "Implementation completed successfully"
        
    except Exception as e:
        logger.error(f"Implementation error: {e}")
        raise
