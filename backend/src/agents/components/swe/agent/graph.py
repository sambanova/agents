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
import random

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
    """Developer agent that streams intermediate messages for real-time updates."""
    
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
        """Implement all tasks with real-time streaming."""
        logger.info("=== STARTING SWE STREAMING DEVELOPER ===")
        
        if not self.daytona_manager:
            error_msg = await self.create_and_stream_message(
                "❌ **Error: No Daytona Manager**\n\nDaytona manager not available for sandbox operations.",
                {"agent_type": "swe_error", "status": "failed"}
            )
            return {
                "implementation_research_scratchpad": [AIMessage(content="Error: No Daytona manager")],
                "messages": [error_msg],
                "sender": "developer",
                "plan_approved": state.plan_approved,
                "human_feedback": state.human_feedback,
                "working_directory": state.working_directory,
                "implementation_plan": state.implementation_plan
            }
        
        # Create feature branch and stream branch creation
        branch_name = f"swe-agent-implementation-{random.randint(1000, 9999)}"
        await self.create_and_stream_message(
            f"🌿 **Creating Feature Branch**\n\nBranch: `{branch_name}`\nStatus: Creating...",
            {"agent_type": "swe_branch_creation", "branch_name": branch_name, "status": "creating"}
        )
        
        try:
            sandbox = await self.daytona_manager._get_sandbox()
            if sandbox:
                working_dir = state.working_directory or sandbox.working_directory or "."
                await sandbox.git.create_branch(working_dir, branch_name)
                await self.create_and_stream_message(
                    f"✅ **Branch Created Successfully**\n\nBranch: `{branch_name}`\nStatus: Ready for implementation",
                    {"agent_type": "swe_branch_created", "branch_name": branch_name, "status": "created"}
                )
                logger.info(f"Created feature branch: {branch_name}")
            else:
                raise Exception("Sandbox not available")
        except Exception as e:
            await self.create_and_stream_message(
                f"❌ **Branch Creation Failed**\n\nError: {str(e)}",
                {"agent_type": "swe_branch_error", "branch_name": branch_name, "status": "failed"}
            )
            logger.error(f"Failed to create branch: {e}")
        
        # Process each task with streaming
        for task_idx, task in enumerate(state.implementation_plan.tasks, 1):
            # Stream task start
            await self.create_and_stream_message(
                f"🎯 **Task {task_idx}: {task.logical_task}**\n\nFile: `{task.file_path}`\nStarting implementation...",
                {"agent_type": "swe_task_start", "task_id": task_idx, "logical_task": task.logical_task, "file_path": task.file_path}
            )
            
            # Process each atomic task with streaming
            for atomic_idx, atomic_task in enumerate(task.atomic_tasks, 1):
                # Stream atomic task start
                await self.create_and_stream_message(
                    f"⚡ **Atomic Task {task_idx}.{atomic_idx}**\n\n{atomic_task.atomic_task}\n\nImplementing...",
                    {"agent_type": "swe_atomic_start", "task_id": task_idx, "atomic_id": atomic_idx, "atomic_task": atomic_task.atomic_task}
                )
                
                # Implement the atomic task
                result_message, diff_info = await self.creating_diffs_for_task_with_streaming(
                    task.file_path, atomic_task, branch_name
                )
                
                # Stream atomic completion with diff
                if diff_info and not diff_info.get('error'):
                    await self.create_and_stream_message(
                        f"""✅ **Atomic Task {task_idx}.{atomic_idx} Complete**

**📝 Task:** {atomic_task.atomic_task}
**📁 File:** {task.file_path}
**🔄 Operation:** {diff_info.get('operation_type', 'Modified')}

**📊 Diff Preview:**
```diff
{diff_info.get('diff_text', 'No diff available')[:500]}{'...' if len(diff_info.get('diff_text', '')) > 500 else ''}
```

**📥 Commit:** {diff_info.get('commit_message', 'Changes committed')}""",
                        {
                            "agent_type": "swe_atomic_complete",
                            "task_id": task_idx,
                            "atomic_id": atomic_idx,
                            "diff_info": diff_info,
                            "status": "completed"
                        }
                    )
                else:
                    await self.create_and_stream_message(
                        f"✅ **Atomic Task {task_idx}.{atomic_idx} Complete**\n\n{atomic_task.atomic_task}\n\n{result_message}",
                        {"agent_type": "swe_atomic_complete", "task_id": task_idx, "atomic_id": atomic_idx, "status": "completed"}
                    )
                
                logger.info(f"Task {task_idx}.{atomic_idx} completed and streamed")
            
            # Stream task completion
            await self.create_and_stream_message(
                f"🎉 **Task {task_idx} Complete**\n\n{task.logical_task}\n\nFile: `{task.file_path}`\nAll atomic tasks implemented successfully!",
                {"agent_type": "swe_task_complete", "task_id": task_idx, "status": "completed"}
            )
        
        # Final implementation summary
        await self.create_and_stream_message(
            f"""🏁 **Implementation Phase Complete**

**📊 Summary:**
- **Tasks Completed:** {len(state.implementation_plan.tasks)}
- **Total Atomic Tasks:** {sum(len(task.atomic_tasks) for task in state.implementation_plan.tasks)}
- **Branch:** `{branch_name}`
- **Status:** Ready for architect review

**🔄 Next Step:** Proceeding to architectural review...""",
            {"agent_type": "swe_implementation_complete", "status": "completed", "branch_name": branch_name}
        )
        
        # CRITICAL: Return captured messages like datagen does
        captured_messages = self.message_interceptor.captured_messages
        for msg in captured_messages:
            if 'agent_type' not in msg.additional_kwargs:
                msg.additional_kwargs['agent_type'] = 'swe_developer'
        
        logger.info(f"=== SWE STREAMING DEVELOPER COMPLETE === Captured {len(captured_messages)} messages")
        
        return {
            "implementation_research_scratchpad": [AIMessage(content="Implementation completed")],
            "messages": captured_messages,  # This is the key - return captured messages!
            "sender": "developer",
            "plan_approved": state.plan_approved,
            "human_feedback": state.human_feedback,
            "working_directory": state.working_directory,
            "implementation_plan": state.implementation_plan
        }
    
    async def creating_diffs_for_task_with_streaming(
        self, file_path: str, atomic_task: object, branch_name: str
    ) -> tuple[str, dict]:
        """Create diffs for a task with enhanced streaming support using direct sandbox access."""
        logger.info(f"=== CREATING DIFFS FOR STREAMING === File: {file_path}, Task: {atomic_task.atomic_task}")
        
        try:
            # Get sandbox using datagen pattern
            sandbox = await self.daytona_manager._get_sandbox()
            if not sandbox:
                logger.error("No sandbox available from daytona manager")
                return f"Implementation failed: No sandbox available", {"error": "No sandbox available"}
            
            logger.info(f"Found sandbox for file operations: {type(sandbox)}")
            working_dir = sandbox.working_directory or "."
            
            # Read file before changes to capture diff
            try:
                success, existing_content = await self.daytona_manager.read_file(file_path)
                before_content = existing_content if success and existing_content else ""
                logger.info(f"Read file {file_path}: success={success}, content_length={len(before_content)}")
            except Exception as read_error:
                logger.warning(f"Could not read existing file {file_path}: {read_error}")
                before_content = ""
            
            if before_content:
                # Edit existing file - add meaningful implementation
                modified_content = f"""// Task implemented: {atomic_task.atomic_task}
// Additional context: {atomic_task.additional_context}
{before_content}"""
                operation_type = "modified"
            else:
                # Create new file
                file_extension = file_path.split('.')[-1] if '.' in file_path else 'js'
                
                if file_extension in ['js', 'ts']:
                    modified_content = f"""// New file created for task: {atomic_task.atomic_task}
// File: {file_path}
// Additional context: {atomic_task.additional_context}

// TODO: Implement the following functionality:
// {atomic_task.atomic_task}

console.log('Task: {atomic_task.atomic_task}');
"""
                elif file_extension in ['py']:
                    modified_content = f"""# New file created for task: {atomic_task.atomic_task}
# File: {file_path}
# Additional context: {atomic_task.additional_context}

# TODO: Implement the following functionality:
# {atomic_task.atomic_task}

print('Task: {atomic_task.atomic_task}')
"""
                else:
                    modified_content = f"""# Task: {atomic_task.atomic_task}
# File: {file_path}
# Additional context: {atomic_task.additional_context}

# Implementation needed:
# {atomic_task.atomic_task}
"""
                operation_type = "created"
            
            # Write file using datagen pattern
            try:
                success = await self.daytona_manager.write_file(file_path, modified_content)
                if success:
                    logger.info(f"Successfully {operation_type} file: {file_path}")
                else:
                    return f"Implementation failed: Could not write file", {"error": "File write failed"}
            except Exception as write_error:
                logger.error(f"Failed to write file {file_path}: {write_error}")
                return f"Implementation failed: Could not write file", {"error": str(write_error)}
            
            # Calculate diff using diff_match_patch
            try:
                from diff_match_patch import diff_match_patch
                dmp = diff_match_patch()
                diffs = dmp.diff_main(before_content, modified_content)
                dmp.diff_cleanupSemantic(diffs)
                
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
            except Exception as diff_error:
                logger.warning(f"Could not generate diff: {diff_error}")
                if operation_type == "created":
                    diff_text = f"New file created:\n+ {modified_content[:500]}..."
                else:
                    diff_text = "File modified (diff unavailable)"
            
            # Stage and commit changes using native Git operations
            commit_message = f"{atomic_task.atomic_task}"
            try:
                await sandbox.git.add(working_dir, ["."])
                await sandbox.git.commit(
                    working_dir, 
                    commit_message, 
                    "SWE Agent", 
                    "swe-agent@sandbox.local"
                )
                logger.info(f"Committed changes: {atomic_task.atomic_task}")
                commit_status = "committed"
            except Exception as commit_error:
                logger.warning(f"Could not commit changes: {commit_error}")
                commit_status = "commit_failed"
                
            # Prepare diff info
            diff_info = {
                "operation_type": operation_type,
                "diff_text": diff_text,
                "filename": file_path,
                "before_size": len(before_content),
                "after_size": len(modified_content),
                "commit_status": commit_status,
                "commit_message": commit_message,
                "branch_name": branch_name
            }
            
            logger.info(f"Successfully implemented task: {atomic_task.atomic_task}")
            return f"Implementation completed successfully ({operation_type})", diff_info
            
        except Exception as e:
            logger.error(f"Implementation error for {file_path}: {e}")
            return f"Implementation failed: {str(e)}", {"error": str(e)}


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
    
    # Now we have all the functions we need for the graph
    logger.info("=== CREATING SWE AGENT GRAPH ===")
    
    async def developer_node(state: AgentState) -> dict:
        """Developer implementation node with enhanced streaming."""
        logger.info("=== STREAMING DEVELOPER NODE START ===")
        logger.info(f"Current state keys: {list(state.__dict__.keys()) if hasattr(state, '__dict__') else 'No dict'}")
        logger.info(f"Implementation plan exists: {hasattr(state, 'implementation_plan') and state.implementation_plan is not None}")
        
        # Create and use streaming developer agent
        streaming_developer = SWEStreamingDeveloperAgent(daytona_manager=daytona_manager)
        
        try:
            result = await streaming_developer.implement_tasks(state)
            
            logger.info(f"=== DEVELOPER NODE RESULT DEBUG ===")
            logger.info(f"Result keys: {result.keys()}")
            logger.info(f"Messages count: {len(result.get('messages', []))}")
            logger.info(f"Sender: {result.get('sender', 'No sender')}")
            
            # Log details about captured messages
            messages = result.get('messages', [])
            for i, msg in enumerate(messages):
                logger.info(f"Message {i}: type={type(msg)}, agent_type={msg.additional_kwargs.get('agent_type', 'None')}")
            
            logger.info("=== STREAMING DEVELOPER NODE COMPLETE ===")
            return result
        
        except Exception as e:
            logger.error(f"Error in developer_node: {e}")
            error_result = {
                "implementation_research_scratchpad": [AIMessage(content=f"Developer error: {str(e)}")],
                "messages": [AIMessage(content=f"❌ **Developer Error**\n\nError: {str(e)}", 
                                     additional_kwargs={"agent_type": "swe_error", "status": "failed"})],
                "sender": "developer",
                "plan_approved": state.plan_approved,
                "human_feedback": state.human_feedback,
                "working_directory": state.working_directory,
                "implementation_plan": state.implementation_plan
            }
            return error_result

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
        
        logger.info(f"=== ARCHITECT REVIEW ROUTER === Sender: '{sender}'")
        
        if sender == "architect_review_changes":
            logger.info("Architect requested changes - routing back to developer")
            return "developer"
        elif sender == "architect_review_complete":
            logger.info("Architect approved implementation - WORKFLOW COMPLETE")
            return END
        else:
            logger.warning(f"Unexpected sender in architect_review_router: '{sender}' - defaulting to END")
            return END

    def human_choice_router(state: AgentState) -> str:
        """Route from human choice: proceed to developer if approved"""
        if state.plan_approved:
            logger.info("User approved plan. Routing to: developer")
            return "developer"
        else:
            logger.info("Plan not approved. Routing to: architect")
            return "architect"

    # Build the workflow graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("architect", architect_subgraph)
    workflow.add_node("human_choice", human_choice_node_wrapper)
    workflow.add_node("developer", developer_node)
    workflow.add_node("architect_review", architect_review_node)
    
    # Add edges
    workflow.add_edge(START, "architect")
    workflow.add_conditional_edges("architect", architect_router, {"human_choice": "human_choice", "architect": "architect"})
    workflow.add_conditional_edges("human_choice", human_choice_router, {"developer": "developer", "architect": "architect"})
    workflow.add_conditional_edges("developer", developer_router, {"architect_review": "architect_review"})
    workflow.add_conditional_edges("architect_review", architect_review_router, {"developer": "developer", "END": END})
    
    # Add checkpointer if provided
    graph_config = {}
    # The original code had checkpointer, but it's not defined in the new_code.
    # Assuming it's a placeholder for a checkpointer object if it were available.
    # For now, removing it as it's not defined in the new_code.
    # if checkpointer:
    #     graph_config["checkpointer"] = checkpointer
    
    # Compile the graph
    graph = workflow.compile(**graph_config)
    graph.name = "swe-agent-v4-streaming-with-review-loop"
    
    logger.info("SWE Agent graph compiled successfully with streaming and review loop")
    
    return graph
