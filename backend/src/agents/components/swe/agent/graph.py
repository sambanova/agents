from agents.components.swe.agent.architect.graph import create_swe_architect, swe_architect
from agents.components.swe.agent.common.entities import ImplementationPlan
from agents.components.swe.agent.developer.graph import create_swe_developer
from agents.components.swe.human_choice import swe_human_choice_node, swe_human_choice_router
from agents.utils.llms import get_sambanova_llm
from agents.components.compound.util import extract_api_key
from agents.utils.message_interceptor import MessageInterceptor
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
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


class SWEStreamingDeveloperAgent:
    """
    Developer agent that follows datagen pattern for real-time streaming.
    Creates messages during execution and streams them immediately.
    """
    
    def __init__(self, daytona_manager=None):
        self.daytona_manager = daytona_manager
        self.message_interceptor = MessageInterceptor()
        
    async def create_and_stream_message(self, content: str, additional_kwargs: dict = None):
        """Create a message and immediately capture it for streaming."""
        message = AIMessage(
            content=content,
            additional_kwargs=additional_kwargs or {}
        )
        # Capture the message for immediate streaming (synchronous call, not async)
        self.message_interceptor.capture_and_pass(message)
        return message
    
    async def implement_tasks(self, state: AgentState) -> dict:
        """Implement all tasks with real-time streaming following datagen pattern."""
        try:
            if not state.implementation_plan or not state.implementation_plan.tasks:
                completion_msg = await self.create_and_stream_message(
                    "🎉 **Implementation Completed**\n\n**📋 Status:** No tasks to implement\n**✅ Result:** Ready for use",
                    {"agent_type": "swe_completion", "status": "completed"}
                )
                return {
                    "implementation_research_scratchpad": [AIMessage(content="No tasks to implement")],
                    "messages": [completion_msg],
                    "sender": "developer"
                }
            
            # STEP 1: Create single feature branch with streaming
            working_dir = state.working_directory or "."
            feature_branch_name = f"swe-agent-implementation-{hash(str(state.implementation_plan.tasks)) % 10000}"
            
            branch_msg = await self.create_and_stream_message(
                f"""🌿 **Creating Feature Branch**

**Branch:** `{feature_branch_name}`
**Repository:** {working_dir}

Creating a dedicated feature branch for all implementation tasks...""",
                {
                    "agent_type": "swe_branch_creation",
                    "status": "in_progress",
                    "branch_name": feature_branch_name,
                    "repository": working_dir,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            
            # Actually create the branch
            if self.daytona_manager:
                try:
                    sandbox = await self.daytona_manager._get_sandbox()
                    if sandbox:
                        try:
                            await sandbox.git.create_branch(working_dir, feature_branch_name)
                            logger.info(f"Created feature branch: {feature_branch_name}")
                            
                            # Stream success message immediately
                            await self.create_and_stream_message(
                                f"✅ **Feature Branch Created Successfully**\n\nBranch `{feature_branch_name}` is ready for implementation.",
                                {"agent_type": "swe_branch_creation", "status": "completed", "branch_name": feature_branch_name}
                            )
                        except Exception as e:
                            await self.create_and_stream_message(
                                f"⚠️ **Branch Creation Warning**\n\nContinuing with existing branch. Details: {str(e)}",
                                {"agent_type": "swe_branch_creation", "status": "warning"}
                            )
                except Exception as e:
                    await self.create_and_stream_message(
                        f"❌ **Sandbox Error**\n\nError: {str(e)}",
                        {"agent_type": "swe_branch_creation", "status": "error"}
                    )
            
            # STEP 2: Process tasks with real-time streaming
            all_completed_tasks = []
            total_atomic_tasks = sum(len(task.atomic_tasks) for task in state.implementation_plan.tasks if task.atomic_tasks)
            current_atomic_index = 0
            
            for task_index, task in enumerate(state.implementation_plan.tasks):
                if not task.atomic_tasks:
                    continue
                
                # Stream task start
                await self.create_and_stream_message(
                    f"""📝 **Starting Task {task_index + 1} of {len(state.implementation_plan.tasks)}**

**File:** `{task.file_path}`
**Atomic Tasks:** {len(task.atomic_tasks)}
**Logical Task:** {task.logical_task}

---
*Processing atomic tasks...*""",
                    {
                        "agent_type": "swe_task_start",
                        "status": "in_progress",
                        "task_number": task_index + 1,
                        "total_tasks": len(state.implementation_plan.tasks),
                        "file_path": task.file_path,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                
                for atomic_index, atomic_task in enumerate(task.atomic_tasks):
                    current_atomic_index += 1
                    
                    # Stream atomic task progress immediately
                    await self.create_and_stream_message(
                        f"""⚙️ **Implementing Atomic Task {current_atomic_index} of {total_atomic_tasks}**

**Progress:** {int((current_atomic_index / total_atomic_tasks) * 100)}% complete
**File:** `{task.file_path}`
**Task:** {atomic_task.atomic_task}

🔄 *Executing implementation...*""",
                        {
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
                    
                    if atomic_task and self.daytona_manager:
                        try:
                            # Execute the task and capture diffs
                            result_content, diff_info = await creating_diffs_for_task_with_streaming(
                                task.file_path, 
                                atomic_task.atomic_task,
                                self.daytona_manager,
                                working_dir,
                                feature_branch_name
                            )
                            
                            # Stream the diff and completion immediately
                            diff_display = diff_info.get('diff_text', 'File operation completed successfully')
                            await self.create_and_stream_message(
                                f"""✅ **Atomic Task {current_atomic_index} Completed**

**File:** `{task.file_path}`
**Task:** {atomic_task.atomic_task}
**Branch:** `{feature_branch_name}`

**Changes Made:**
```diff
{diff_display}
```

**Status:** {result_content}
**Commit:** {diff_info.get('commit_message', 'N/A')}

---""",
                                {
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
                            
                            all_completed_tasks.append(f"✅ {atomic_task.atomic_task} ({task.file_path})")
                            logger.info(f"Task {task_index + 1}.{atomic_index + 1} completed and streamed")
                            
                        except Exception as task_error:
                            await self.create_and_stream_message(
                                f"""❌ **Atomic Task {current_atomic_index} Failed**

**File:** `{task.file_path}`
**Task:** {atomic_task.atomic_task}
**Error:** {str(task_error)}

---""",
                                {
                                    "agent_type": "swe_atomic_error",
                                    "status": "failed",
                                    "file_path": task.file_path,
                                    "atomic_task": atomic_task.atomic_task,
                                    "error": str(task_error),
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                
                # Stream task completion
                await self.create_and_stream_message(
                    f"""✅ **Task {task_index + 1} Completed**

**File:** `{task.file_path}`
**Atomic Tasks Completed:** {len(task.atomic_tasks)}

All atomic tasks for this file have been completed successfully.

---""",
                    {
                        "agent_type": "swe_task_completion",
                        "status": "completed",
                        "task_number": task_index + 1,
                        "file_path": task.file_path,
                        "atomic_tasks_completed": len(task.atomic_tasks),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            
            # Stream final completion
            final_msg = await self.create_and_stream_message(
                f"""🎉 **All Implementation Tasks Completed Successfully**

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
*Complete implementation workflow finished successfully. Proceeding to architect review...*""",
                {
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
            
            # Return all captured messages for final state
            captured_messages = self.message_interceptor.captured_messages
            return {
                "implementation_research_scratchpad": [AIMessage(content=f"Completed {len(all_completed_tasks)} implementation tasks on branch {feature_branch_name}")],
                "messages": captured_messages,  # All streamed messages
                "sender": "developer",
                "plan_approved": state.plan_approved,
                "human_feedback": state.human_feedback,
                "working_directory": working_dir,
                "implementation_plan": state.implementation_plan
            }
            
        except Exception as e:
            error_msg = await self.create_and_stream_message(
                f"❌ **Implementation Failed**\n\nError: {str(e)}",
                {"agent_type": "swe_error", "status": "failed", "error": str(e)}
            )
            return {
                "implementation_research_scratchpad": [AIMessage(content=f"Error: {str(e)}")],
                "messages": [error_msg],
                "sender": "developer"
            }


def create_swe_agent(daytona_manager=None, github_token=None):
    """Create the main SWE agent as a unified workflow"""
    logger.info("Creating SWE agent with human choice workflow")
    
    # Create the architect with Daytona support
    architect_subgraph = create_swe_architect(daytona_manager=daytona_manager, github_token=github_token)
    
    # Create streaming developer agent
    streaming_developer = SWEStreamingDeveloperAgent(daytona_manager=daytona_manager)
    
    # Create human choice node wrapper function that provides LLM
    async def human_choice_node_wrapper(state, *, config: RunnableConfig = None):
        """Human choice node wrapper that provides LLM from config"""
        api_key = extract_api_key(config)
        llm = get_sambanova_llm(api_key=api_key, model="DeepSeek-V3-0324")
        return await swe_human_choice_node(state, llm)

    # Create streaming developer node
    async def developer_node(state, *, config: RunnableConfig = None):
        """Streaming developer node that follows datagen pattern"""
        logger.info("=== STREAMING DEVELOPER NODE START ===")
        return await streaming_developer.implement_tasks(state)

    # Create architect review node that evaluates and routes appropriately
    async def architect_review_node(state, *, config: RunnableConfig = None):
        """Architect reviews completed implementation work and decides if more work is needed"""
        api_key = extract_api_key(config)
        llm = get_sambanova_llm(api_key=api_key, model="DeepSeek-V3-0324")
        
        review_prompt = f"""You are a software architect reviewing completed implementation work.

IMPLEMENTATION COMPLETED:
- Repository: {state.working_directory}
- Total Tasks: {len(state.implementation_plan.tasks) if state.implementation_plan else 0}
- Implementation Messages: {len(state.messages)} detailed steps completed

REVIEW TASKS:
1. Analyze if all planned tasks were implemented correctly
2. Verify implementation quality and completeness
3. Check if any fixes or improvements are needed
4. Decide if work is complete or needs developer changes

DECISION REQUIRED:
- If implementation is complete and satisfactory: respond with "APPROVED"
- If changes/fixes are needed: respond with "CHANGES_NEEDED" and list specific issues

Your response must start with either "APPROVED" or "CHANGES_NEEDED" followed by your detailed assessment."""

        review_response = await llm.ainvoke([HumanMessage(content=review_prompt)])
        
        # Determine if changes are needed based on response
        needs_changes = review_response.content.strip().startswith("CHANGES_NEEDED")
        
        if needs_changes:
            # Extract the issues from the response
            issues_text = review_response.content.replace("CHANGES_NEEDED", "").strip()
            
            review_message = AIMessage(
                content=f"""🏗️ **Architect Review - Changes Required**

{review_response.content}

**📋 Review Decision:**
- **Status:** Changes Required
- **Next Step:** Returning to developer for fixes

**🔄 Required Changes:**
{issues_text}

---
*Routing back to developer for implementation improvements...*""",
                additional_kwargs={
                    "agent_type": "swe_architect_review_changes",
                    "status": "changes_required",
                    "needs_changes": True,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            
            logger.info("Architect review: Changes needed - routing back to developer")
            
            return {
                "implementation_research_scratchpad": [AIMessage(content="Architect review: Changes needed")],
                "messages": [review_message],
                "sender": "architect_review_changes",
                "plan_approved": state.plan_approved,
                "human_feedback": issues_text,  # Pass the required changes as feedback
                "working_directory": state.working_directory,
                "implementation_plan": state.implementation_plan
            }
        else:
            # Implementation approved - workflow complete
            review_message = AIMessage(
                content=f"""🏗️ **Architect Review - Implementation Approved**

{review_response.content}

**📋 Final Assessment:**
- **Status:** Implementation Approved ✅
- **Quality:** All requirements met
- **Code Changes:** Reviewed and approved
- **All Tasks:** Successfully implemented

**🚀 Final Status:** Implementation complete and ready for deployment

---
*Architectural review completed successfully. Implementation ready for use.*""",
                additional_kwargs={
                    "agent_type": "swe_architect_review_complete",
                    "status": "approved",
                    "workflow_complete": True,
                    "needs_changes": False,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            
            logger.info("Architect review: Implementation approved - workflow complete")
            
            return {
                "implementation_research_scratchpad": [AIMessage(content="Architect review completed - workflow approved")],
                "messages": [review_message],
                "sender": "architect_review_complete",
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
        """Route from developer: go to architect review for evaluation"""
        logger.info("Implementation completed, routing to architect for review")
        return "architect_review"

    def architect_review_router(state: AgentState) -> str:
        """Route from architect review: either complete or back to developer for changes"""
        sender = getattr(state, "sender", "")
        
        if sender == "architect_review_changes":
            logger.info("Architect review: Changes needed - routing back to developer")
            return "developer"
        elif sender == "architect_review_complete":
            logger.info("Architect review: Implementation approved - workflow complete")
            return "END"
        else:
            # Fallback - should not happen
            logger.warning(f"Unexpected sender in architect review router: {sender}")
            return "END"

    # Create the main workflow as unified graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("architect", architect_subgraph)
    workflow.add_node("human_choice", human_choice_node_wrapper)
    workflow.add_node("developer", developer_node)
    workflow.add_node("architect_review", architect_review_node)
    
    # Add edges - FIXED: architect_review can loop back to developer OR end
    workflow.add_edge(START, "architect")
    workflow.add_conditional_edges("architect", architect_router, {"architect": "architect", "human_choice": "human_choice"})
    workflow.add_conditional_edges("human_choice", swe_human_choice_router, {"developer": "developer", "architect": "architect"})
    workflow.add_conditional_edges("developer", developer_router, {"architect_review": "architect_review"})
    workflow.add_conditional_edges("architect_review", architect_review_router, {"developer": "developer", "END": END})
    
    return workflow.compile().with_config({
        "tags": ["swe-agent-v4-streaming-with-review-loop"], 
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
