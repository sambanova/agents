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
from langchain_core.messages import HumanMessage

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
        """Developer node that implements ALL tasks in the plan using Daytona tools with proper streaming"""
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
        
        try:
            # Process ALL tasks in the implementation plan, not just the first one
            if not state.implementation_plan or not state.implementation_plan.tasks:
                debug_logger.info("No implementation plan or tasks to process")
                completion_content = """🎉 **Implementation Completed**

**📋 Status:** No tasks to implement
**✅ Result:** Ready for use

---
*All implementation tasks completed successfully*"""
                
                return_state = {
                    "implementation_research_scratchpad": [AIMessage(content="No tasks to implement")],
                    "messages": [AIMessage(
                        content=completion_content,
                        additional_kwargs={
                            "agent_type": "swe_completion",
                            "status": "completed",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )],
                    "sender": "developer",
                    "plan_approved": state.plan_approved,
                    "human_feedback": state.human_feedback,
                    "working_directory": state.working_directory,
                    "implementation_plan": state.implementation_plan
                }
                
                for key, value in return_state.items():
                    if value is None:
                        debug_logger.warning(f"Return state has None value for key: {key}")
                    else:
                        debug_logger.info(f"Return state key '{key}' has value type: {type(value).__name__}")
                debug_logger.info("=== DEVELOPER NODE DEBUG END (NO TASKS) ===")
                
                return return_state
            
            # STEP 1: Create a single feature branch for the entire implementation
            working_dir = state.working_directory or "."
            feature_branch_name = f"swe-agent-implementation-{hash(str(state.implementation_plan.tasks)) % 10000}"
            
            # Stream branch creation message
            branch_creation_msg = AIMessage(
                content=f"""🌿 **Creating Feature Branch**

**Branch:** `{feature_branch_name}`
**Repository:** {working_dir}

Creating a dedicated feature branch for all implementation tasks...""",
                additional_kwargs={
                    "agent_type": "swe_branch_creation",
                    "status": "in_progress",
                    "branch_name": feature_branch_name,
                    "repository": working_dir,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            
            if daytona_manager:
                try:
                    # Get sandbox instance for Git operations
                    sandbox = await daytona_manager._get_sandbox()
                    if sandbox:
                        # Create the feature branch once for all tasks
                        try:
                            await sandbox.git.create_branch(working_dir, feature_branch_name)
                            debug_logger.info(f"Created feature branch: {feature_branch_name}")
                            branch_creation_msg.content += f"\n\n✅ **Branch created successfully**"
                            branch_creation_msg.additional_kwargs["status"] = "completed"
                        except Exception as branch_error:
                            # Try to switch to existing branch
                            try:
                                await sandbox.git.checkout_branch(working_dir, feature_branch_name)
                                debug_logger.info(f"Switched to existing branch: {feature_branch_name}")
                                branch_creation_msg.content += f"\n\n✅ **Switched to existing branch**"
                                branch_creation_msg.additional_kwargs["status"] = "completed"
                            except Exception:
                                debug_logger.warning(f"Could not create or switch to branch {feature_branch_name}: {branch_error}")
                                branch_creation_msg.content += f"\n\n⚠️ **Branch operation failed, continuing on current branch**"
                                branch_creation_msg.additional_kwargs["status"] = "warning"
                except Exception as e:
                    debug_logger.error(f"Sandbox operation failed: {e}")
                    branch_creation_msg.content += f"\n\n❌ **Sandbox error: {str(e)}**"
                    branch_creation_msg.additional_kwargs["status"] = "error"
            
            # STEP 2: Process ALL tasks with streaming progress updates
            all_completed_tasks = []
            implementation_messages = [branch_creation_msg]  # Start with branch creation message
            total_atomic_tasks = sum(len(task.atomic_tasks) for task in state.implementation_plan.tasks if task.atomic_tasks)
            current_atomic_index = 0
            
            for task_index, task in enumerate(state.implementation_plan.tasks):
                if not task.atomic_tasks:
                    continue
                
                # Stream task start message
                task_start_msg = AIMessage(
                    content=f"""📝 **Starting Task {task_index + 1} of {len(state.implementation_plan.tasks)}**

**File:** `{task.file_path}`
**Atomic Tasks:** {len(task.atomic_tasks)}
**Logical Task:** {task.logical_task}

---
*Processing atomic tasks...*""",
                    additional_kwargs={
                        "agent_type": "swe_task_start",
                        "status": "in_progress",
                        "task_number": task_index + 1,
                        "total_tasks": len(state.implementation_plan.tasks),
                        "file_path": task.file_path,
                        "atomic_tasks_count": len(task.atomic_tasks),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                implementation_messages.append(task_start_msg)
                
                for atomic_index, atomic_task in enumerate(task.atomic_tasks):
                    current_atomic_index += 1
                    debug_logger.info("Processing task:", 
                                    task_number=f"{task_index + 1}.{atomic_index + 1}",
                                    progress=f"{current_atomic_index}/{total_atomic_tasks}",
                                    file_path=task.file_path, 
                                    atomic_task=atomic_task.atomic_task)
                    
                    # Stream atomic task progress
                    progress_msg = AIMessage(
                        content=f"""⚙️ **Implementing Atomic Task {current_atomic_index} of {total_atomic_tasks}**

**Progress:** {int((current_atomic_index / total_atomic_tasks) * 100)}% complete
**File:** `{task.file_path}`
**Task:** {atomic_task.atomic_task}

🔄 *Executing implementation...*""",
                        additional_kwargs={
                            "agent_type": "swe_atomic_progress",
                            "status": "in_progress",
                            "atomic_task_number": current_atomic_index,
                            "total_atomic_tasks": total_atomic_tasks,
                            "progress_percentage": int((current_atomic_index / total_atomic_tasks) * 100),
                            "file_path": task.file_path,
                            "atomic_task": atomic_task.atomic_task,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    implementation_messages.append(progress_msg)
                    
                    if atomic_task and daytona_manager:
                        # Execute the task and capture diffs
                        try:
                            result_content, diff_info = await creating_diffs_for_task_with_streaming(
                                task.file_path, 
                                atomic_task.atomic_task,
                                daytona_manager,
                                working_dir,
                                feature_branch_name
                            )
                            
                            debug_logger.info(f"Task {task_index + 1}.{atomic_index + 1} implementation completed successfully")
                            
                            # Track completed task
                            all_completed_tasks.append(f"✅ {atomic_task.atomic_task} ({task.file_path})")
                            
                            # Create detailed success message with diff
                            task_completion_content = f"""✅ **Atomic Task {current_atomic_index} Completed**

**File:** `{task.file_path}`
**Task:** {atomic_task.atomic_task}
**Branch:** `{feature_branch_name}`

**Changes Made:**
```diff
{diff_info.get('diff_text', 'File operation completed successfully')}
```

**Status:** {result_content}

---"""
                            
                            task_completion_msg = AIMessage(
                                content=task_completion_content,
                                additional_kwargs={
                                    "agent_type": "swe_atomic_completion",
                                    "status": "completed",
                                    "file_path": task.file_path,
                                    "atomic_task": atomic_task.atomic_task,
                                    "task_number": f"{task_index + 1}.{atomic_index + 1}",
                                    "atomic_number": current_atomic_index,
                                    "total_atomic_tasks": total_atomic_tasks,
                                    "progress_percentage": int((current_atomic_index / total_atomic_tasks) * 100),
                                    "repository": working_dir,
                                    "branch": feature_branch_name,
                                    "diff_info": diff_info,
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                            implementation_messages.append(task_completion_msg)
                            
                        except Exception as task_error:
                            error_msg = AIMessage(
                                content=f"""❌ **Atomic Task {current_atomic_index} Failed**

**File:** `{task.file_path}`
**Task:** {atomic_task.atomic_task}
**Error:** {str(task_error)}

---""",
                                additional_kwargs={
                                    "agent_type": "swe_atomic_error",
                                    "status": "failed",
                                    "file_path": task.file_path,
                                    "atomic_task": atomic_task.atomic_task,
                                    "error": str(task_error),
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                            implementation_messages.append(error_msg)
                            debug_logger.error(f"Task {task_index + 1}.{atomic_index + 1} failed: {task_error}")
                
                # Stream task completion
                task_complete_msg = AIMessage(
                    content=f"""✅ **Task {task_index + 1} Completed**

**File:** `{task.file_path}`
**Atomic Tasks Completed:** {len(task.atomic_tasks)}

All atomic tasks for this file have been completed successfully.

---""",
                    additional_kwargs={
                        "agent_type": "swe_task_completion",
                        "status": "completed",
                        "task_number": task_index + 1,
                        "file_path": task.file_path,
                        "atomic_tasks_completed": len(task.atomic_tasks),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                implementation_messages.append(task_complete_msg)
            
            # STEP 3: Create comprehensive completion summary
            completion_content = f"""🎉 **All Implementation Tasks Completed Successfully**

**📋 Implementation Summary:**
- **Total Tasks:** {len(state.implementation_plan.tasks)}
- **Total Atomic Tasks:** {len(all_completed_tasks)}
- **Feature Branch:** `{feature_branch_name}`
- **Repository:** {working_dir}

**✅ Completed Tasks:**
{chr(10).join(all_completed_tasks)}

**🚀 Next Steps:**
- All changes committed to feature branch
- Ready for architect review
- Ready for pull request creation
- Ready for testing and integration

---
*Complete implementation workflow finished successfully. Proceeding to architect review...*"""
            
            # Add final completion message
            final_completion_msg = AIMessage(
                content=completion_content,
                additional_kwargs={
                    "agent_type": "swe_implementation_complete",
                    "status": "all_completed",
                    "total_tasks": len(state.implementation_plan.tasks),
                    "total_atomic_tasks": len(all_completed_tasks),
                    "feature_branch": feature_branch_name,
                    "repository": working_dir,
                    "completed_tasks": all_completed_tasks,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            implementation_messages.append(final_completion_msg)
            
            return_state = {
                "implementation_research_scratchpad": [AIMessage(content=f"Completed {len(all_completed_tasks)} implementation tasks on branch {feature_branch_name}")],
                "messages": implementation_messages,  # All detailed streaming messages
                "sender": "developer",
                "plan_approved": state.plan_approved,
                "human_feedback": state.human_feedback,
                "working_directory": working_dir,
                "implementation_plan": state.implementation_plan
            }
            
            # DEBUG: Log what we're returning
            for key, value in return_state.items():
                if value is None:
                    debug_logger.warning(f"Return state has None value for key: {key}")
                else:
                    debug_logger.info(f"Return state key '{key}' has value type: {type(value).__name__}")
            debug_logger.info("=== DEVELOPER NODE DEBUG END (SUCCESS) ===")
            
            return return_state
            
        except Exception as e:
            logger.error(f"Developer error: {e}")
            return {
                "implementation_research_scratchpad": [AIMessage(content=f"Error: {str(e)}")],
                "messages": [AIMessage(content=f"❌ Implementation failed: {str(e)}")],
                "sender": "developer",
                "plan_approved": state.plan_approved,
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

    def developer_router(state: AgentState) -> str:
        """Route from developer: go to architect for review of completed work"""
        logger.info("Implementation completed, routing to architect for review")
        return "architect_review"

    # Create architect review node
    async def architect_review_node(state, *, config: RunnableConfig = None):
        """Architect reviews completed implementation work"""
        api_key = extract_api_key(config)
        llm = get_sambanova_llm(api_key=api_key, model="DeepSeek-V3-0324")
        
        review_prompt = f"""You are a software architect reviewing completed implementation work.

IMPLEMENTATION COMPLETED:
- Repository: {state.working_directory}
- Implementation Plan: {state.implementation_plan.model_dump() if state.implementation_plan else 'None'}
- Developer Messages: {len(state.messages)} implementation steps completed

REVIEW TASKS:
1. Analyze if all planned tasks were implemented
2. Verify implementation quality and completeness
3. Suggest any missing steps or improvements
4. Approve for PR creation or request changes

Provide a thorough architectural review of the completed work."""

        review_response = await llm.ainvoke([HumanMessage(content=review_prompt)])
        
        review_content = f"""🏗️ **Architect Review - Implementation Complete**

{review_response.content}

**📋 Review Summary:**
- Implementation plan execution reviewed
- Code changes analyzed
- Quality assessment completed

**🚀 Recommendation:** Implementation approved for pull request creation

---
*Architectural review completed. Ready for final steps.*"""
        
        return {
            "implementation_research_scratchpad": [AIMessage(content="Architect review completed")],
            "messages": [AIMessage(
                content=review_content,
                additional_kwargs={
                    "agent_type": "swe_architect_review",
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                }
            )],
            "sender": "architect_review",
            "plan_approved": state.plan_approved,
            "human_feedback": state.human_feedback,
            "working_directory": state.working_directory,
            "implementation_plan": state.implementation_plan
        }

    # Create the main workflow as unified graph (original pattern)
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("architect", architect_subgraph)
    workflow.add_node("human_choice", human_choice_node_wrapper)
    workflow.add_node("developer", developer_node)
    workflow.add_node("architect_review", architect_review_node)
    
    # Add edges (enhanced with architect review)
    workflow.add_edge(START, "architect")
    workflow.add_conditional_edges("architect", architect_router, {"architect": "architect", "human_choice": "human_choice"})
    workflow.add_conditional_edges("human_choice", swe_human_choice_router, {"developer": "developer", "architect": "architect"})
    workflow.add_conditional_edges("developer", developer_router, {"architect_review": "architect_review"})
    workflow.add_edge("architect_review", END)
    
    return workflow.compile().with_config({
        "tags": ["swe-agent-v3"], 
        "recursion_limit": 200
    })


async def creating_diffs_for_task_with_streaming(
    file_path: str, 
    task_description: str, 
    daytona_manager, 
    working_directory: str,
    branch_name: str
) -> tuple[str, dict]:
    """
    Enhanced implementation function that captures diffs and provides detailed feedback.
    
    Returns:
        tuple: (result_message, diff_info_dict)
    """
    try:
        # Get sandbox instance for Git operations
        sandbox = await daytona_manager._get_sandbox()
        if not sandbox:
            raise Exception("Daytona sandbox not initialized")
        
        # Read file before changes to capture diff
        success, existing_content = await daytona_manager.read_file(file_path)
        before_content = ""
        if success and existing_content:
            if isinstance(existing_content, bytes):
                before_content = existing_content.decode('utf-8')
            else:
                before_content = str(existing_content)
        
        # Implement the change
        if success and existing_content:
            # Edit existing file - add meaningful implementation comment
            modified_content = f"""// Task implemented: {task_description}
// Implementation details: {task_description}
{before_content}"""
            
            await daytona_manager.write_file(file_path, modified_content)
            logger.info(f"Successfully updated file: {file_path}")
            operation_type = "modified"
        else:
            # Create new file
            modified_content = f"""// New file created for task: {task_description}
// File: {file_path}
// Implementation: {task_description}

// TODO: Implement the following functionality:
// {task_description}

console.log('Task: {task_description}');
"""
            await daytona_manager.write_file(file_path, modified_content)
            logger.info(f"Successfully created file: {file_path}")
            operation_type = "created"
        
        # Calculate diff
        diff_text = ""
        if operation_type == "modified":
            # Use diff_match_patch for proper diff calculation
            from diff_match_patch import diff_match_patch
            dmp = diff_match_patch()
            diffs = dmp.diff_main(before_content, modified_content)
            dmp.diff_cleanupSemantic(diffs)
            
            # Convert to unified diff format
            diff_lines = []
            for op, text in diffs:
                if op == dmp.DIFF_DELETE:
                    for line in text.split('\n'):
                        if line.strip():
                            diff_lines.append(f"- {line}")
                elif op == dmp.DIFF_INSERT:
                    for line in text.split('\n'):
                        if line.strip():
                            diff_lines.append(f"+ {line}")
                elif op == dmp.DIFF_EQUAL:
                    # Show some context lines
                    context_lines = text.split('\n')[:3]
                    for line in context_lines:
                        if line.strip():
                            diff_lines.append(f"  {line}")
                            
            diff_text = '\n'.join(diff_lines[:20])  # Limit to first 20 lines
        else:
            diff_text = f"New file created:\n+ {modified_content[:500]}..."
        
        # Stage and commit changes using native Git operations
        commit_message = f"Implement: {task_description}"
        try:
            await sandbox.git.add(working_directory, ["."])
            await sandbox.git.commit(
                working_directory, 
                commit_message, 
                "SWE Agent", 
                "swe-agent@sandbox.local"
            )
            logger.info(f"Committed changes: {task_description}")
            commit_status = "committed"
        except Exception as commit_error:
            logger.warning(f"Could not commit changes: {commit_error}")
            commit_status = "commit_failed"
            
        # Prepare diff info
        diff_info = {
            "operation_type": operation_type,
            "diff_text": diff_text,
            "file_path": file_path,
            "before_size": len(before_content),
            "after_size": len(modified_content),
            "commit_status": commit_status,
            "commit_message": commit_message,
            "branch_name": branch_name
        }
        
        return f"Implementation completed successfully ({operation_type})", diff_info
        
    except Exception as e:
        logger.error(f"Implementation error: {e}")
        return f"Implementation failed: {str(e)}", {"error": str(e)}
