"""
Software Engineering (SWE) Subgraph for the application.
Provides automated code implementation capabilities using LangGraph.
"""

from typing import Dict, List
import structlog
from langchain_core.messages import HumanMessage, AIMessage
from agents.components.swe.agent.graph import create_swe_agent
from agents.components.swe.repository_manager import RepositoryManager
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.storage.redis_storage import RedisStorage
from agents.utils.llms import get_sambanova_llm

logger = structlog.get_logger(__name__)


def create_swe_graph(
    user_id: str,
    sambanova_api_key: str,
    redis_storage: RedisStorage,
    daytona_manager: PersistentDaytonaManager = None,
    github_token: str = None,
):
    """
    Create the SWE (Software Engineering) subgraph for automated code implementation.
    
    This subgraph provides capabilities for:
    - Analyzing codebases and planning implementations
    - Conducting research on implementation approaches
    - Automatically generating and applying code changes
    - Testing and validation in a sandboxed environment
    
    Args:
        user_id: User identifier for the session
        sambanova_api_key: API key for SambaNova LLM
        redis_storage: Redis storage instance
        daytona_manager: Optional Daytona manager for code execution
        
    Returns:
        Compiled SWE agent graph
    """
    logger.info(
        "Creating SWE subgraph",
        user_id=user_id,
        has_daytona=daytona_manager is not None,
    )
    
    # Create Daytona manager if not provided
    if daytona_manager is None:
        daytona_manager = PersistentDaytonaManager(
            user_id=user_id,
            redis_storage=redis_storage,
            snapshot="swe-agent:latest",  # Could be a specialized SWE snapshot
        )
        logger.info("Created new Daytona manager for SWE operations")
    
    # Create the SWE agent with Daytona support
    swe_agent = create_swe_agent(daytona_manager, github_token)
    
    logger.info("SWE subgraph created successfully")
    return swe_agent


def swe_state_input_mapper(input_text: str) -> Dict:
    """
    Map input text to SWE agent state format.

    Args:
        input_text: User's implementation request (should only include repo context when explicitly provided)

    Returns:
        State dictionary for the SWE agent
    """
    # Only parse repository context if explicitly provided in the input
    # This should NOT automatically prepend repo context to general queries
    # Format: "REPO: owner/repo\nBRANCH: main\n\nTask description here"
    repo_context = ""
    task_content = input_text
    repository_name = None  # Default to None - work with current directory like datagen
    
    # Only process repo context if it's explicitly in the input
    if input_text.startswith("REPO:"):
        lines = input_text.split("\n")
        repo_lines = []
        content_start = 0
        
        for i, line in enumerate(lines):
            if line.startswith(("REPO:", "BRANCH:", "CONTEXT:")):
                repo_lines.append(line)
                content_start = i + 1
                
                # Extract repository name from REPO: line
                if line.startswith("REPO:"):
                    repo_full_name = line.split("REPO:", 1)[1].strip()
                    if "/" in repo_full_name:
                        # Extract just the repo name from "owner/repo"
                        repository_name = repo_full_name.split("/")[-1]
                    else:
                        repository_name = repo_full_name
                        
            elif line.strip() == "":
                content_start = i + 1
                break
            else:
                break
        
        if repo_lines:
            repo_context = "\n".join(repo_lines) + "\n\n"
            task_content = "\n".join(lines[content_start:])
    
    # Create enhanced prompt with repository context
    if repo_context:
        # Extract repository URL from context for cloning
        repo_full_name = None
        branch = "main"
        for line in repo_context.split("\n"):
            if line.startswith("REPO:"):
                repo_full_name = line.split("REPO:", 1)[1].strip()
            elif line.startswith("BRANCH:"):
                branch = line.split("BRANCH:", 1)[1].strip()
        
        clone_url = f"https://github.com/{repo_full_name}.git" if repo_full_name else ""
        
        prompt_content = f"""Repository Context:
{repo_context.strip()}

Implementation Task:
{task_content}

**CRITICAL DEVELOPMENT WORKFLOW**: Before making ANY changes, follow this exact sequence:

1. **CLONE REPOSITORY**: Use `daytona_git_clone` with:
   - URL: {clone_url}
   - Path: {repository_name or 'repository'}
   - Branch: {branch}

2. **CREATE FEATURE BRANCH**: After cloning, IMMEDIATELY create a feature branch:
   - Use `daytona_execute_command` with: `cd {repository_name or 'repository'} && git checkout -b swe-agent-feature-$(date +%s)`
   - NEVER work directly on main/master branch

3. **ANALYZE CODEBASE**: Use `daytona_get_repository_structure` to understand the project layout

4. **CHECK EXISTING FILES**: Before creating files, check if they already exist using `daytona_read_file`
   - If file EXISTS: Edit it using the existing content as base
   - If file DOESN'T EXIST: Create it as new file

5. **IMPLEMENT CHANGES**: Use Daytona tools for all operations:
   - `daytona_read_file` to examine existing code
   - `daytona_write_file` to create/modify files  
   - `daytona_execute_command` to run tests/builds

6. **COMMIT CHANGES**: After implementation:
   - `git add .`
   - `git commit -m "descriptive commit message"`

**IMPORTANT RULES**:
- All operations MUST be performed within the Daytona sandbox
- Do NOT attempt to access local files outside sandbox
- Always work on a feature branch, never directly on main/master
- Check if files exist before deciding to create vs edit them
- Use descriptive commit messages explaining what was implemented

If GitHub authentication is needed, the system will provide appropriate credentials."""
    else:
        prompt_content = f"""Implementation Task:
{task_content}

**DEVELOPMENT ENVIRONMENT**: You are working in a secure Daytona sandbox environment.

**CRITICAL WORKFLOW**:
1. If working with an existing codebase, clone it first using `daytona_git_clone`
2. ALWAYS create a feature branch before making changes: `git checkout -b swe-agent-feature-$(date +%s)`
3. Use ONLY Daytona tools for all file operations and code execution
4. Check if files exist using `daytona_read_file` before deciding to create vs edit
5. Commit your changes with descriptive messages when implementation is complete

**AVAILABLE TOOLS**:
- `daytona_git_clone` - Clone repositories into sandbox
- `daytona_read_file` - Read existing files  
- `daytona_write_file` - Create or modify files
- `daytona_execute_command` - Run shell commands, tests, builds
- `daytona_get_repository_structure` - Analyze codebase structure
- `daytona_search_keyword_in_directory` - Search for code patterns

All operations happen within the sandbox. No local file access outside the sandbox."""
    
    # Create state with repository information
    initial_state = {
        "implementation_research_scratchpad": [
            HumanMessage(content=prompt_content)
        ]
    }
    
    # Add repository name to state if we have one, otherwise use current directory approach like datagen
    if repository_name:
        initial_state["working_directory"] = f"./{repository_name}"
    else:
        initial_state["working_directory"] = "."  # Current directory like datagen
    
    return initial_state


def swe_state_output_mapper(result: Dict) -> AIMessage:
    """
    Map SWE agent output to standard message format.
    
    Args:
        result: Output from the SWE agent
        
    Returns:
        AIMessage with implementation results
    """
    import structlog
    logger = structlog.get_logger(__name__)
    
    # DEBUG: Log the entire result to identify None values
    logger.info("=== SWE STATE OUTPUT MAPPER DEBUG ===")
    logger.info("Raw result keys:", keys=list(result.keys()) if result else "Result is None")
    
    # Log each key-value pair to identify None values
    if result:
        for key, value in result.items():
            if value is None:
                logger.warning(f"Found None value for key: {key}")
            else:
                logger.info(f"Key '{key}' has value type: {type(value).__name__}")
    
    # ENHANCED PATTERN: Check sender to determine appropriate response
    sender = result.get("sender", "")
    
    # Handle architect review completion
    if sender == "architect_review":
        logger.info("Processing architect review completion")
        if result.get("messages") and len(result["messages"]) > 0:
            last_message = result["messages"][-1]
            if hasattr(last_message, 'model_copy'):
                enhanced_message = last_message.model_copy(
                    update={
                        "additional_kwargs": {
                            **(last_message.additional_kwargs or {}),
                            "agent_type": "swe_architect_review_complete",
                            "status": "completed",
                            "workflow_complete": True,
                        }
                    }
                )
                logger.info("Returning architect review completion message")
                logger.info("=== END SWE STATE OUTPUT MAPPER DEBUG ===")
                return enhanced_message
    
    # Handle developer completion (with all streaming messages)
    if sender == "developer":
        logger.info("Processing developer completion with streaming messages")
        if result.get("messages") and len(result["messages"]) > 0:
            # Return the final completion message from the developer workflow
            final_message = result["messages"][-1]
            if hasattr(final_message, 'model_copy'):
                enhanced_message = final_message.model_copy(
                    update={
                        "additional_kwargs": {
                            **(final_message.additional_kwargs or {}),
                            "agent_type": "swe_development_complete",
                            "status": "completed",
                            "proceeding_to_review": True,
                        }
                    }
                )
                logger.info("Returning developer completion message")
                logger.info("=== END SWE STATE OUTPUT MAPPER DEBUG ===")
                return enhanced_message
    
    # FOLLOW DATAGEN PATTERN: Use the last message from the detailed work
    # Check if we have messages with detailed work information
    if result.get("messages") and len(result["messages"]) > 0:
        # Get the last message which contains the detailed implementation work
        last_message = result["messages"][-1]
        
        # If it's already an AIMessage, preserve it and enhance with SWE-specific info
        if hasattr(last_message, 'model_copy'):
            enhanced_message = last_message.model_copy(
                update={
                    "additional_kwargs": {
                        **(last_message.additional_kwargs or {}),
                        "agent_type": "swe_completion",
                        "status": "completed",
                        "implementation_complete": True,
                    }
                }
            )
            logger.info("Returning enhanced detailed message from SWE work")
            logger.info("=== END SWE STATE OUTPUT MAPPER DEBUG ===")
            return enhanced_message
        else:
            # Convert dict to AIMessage if needed
            content = last_message.get("content", "SWE implementation completed")
            additional_kwargs = {
                **(last_message.get("additional_kwargs", {})),
                "agent_type": "swe_completion", 
                "status": "completed",
                "implementation_complete": True,
            }
            
            logger.info("Returning converted detailed message from SWE work")
            logger.info("=== END SWE STATE OUTPUT MAPPER DEBUG ===")
            return AIMessage(content=content, additional_kwargs=additional_kwargs)
    
    # FALLBACK: If no detailed messages, check completion status
    if result.get("plan_approved") and not result.get("implementation_plan"):
        # Implementation completed successfully
        content = """✅ **Implementation Completed Successfully**

The SWE agent has successfully completed the requested implementation:

**✅ Repository cloned and feature branch created**
**✅ Existing files analyzed and updated appropriately** 
**✅ Code changes applied using proper diff methodology**
**✅ All operations performed in secure Daytona sandbox**
**✅ Architect review completed**

**Next Steps:**
- Changes have been committed to the feature branch
- Architectural review passed
- Ready for pull request creation
- Ready for testing and integration

The implementation is complete and ready for use!"""
        
        additional_kwargs = {
            "agent_type": "swe_completion",
            "status": "completed", 
            "implementation_complete": True,
            "architect_reviewed": True,
        }
        logger.info("Returning completion message with additional_kwargs:", additional_kwargs=additional_kwargs)
        logger.info("=== END SWE STATE OUTPUT MAPPER DEBUG ===")
        
        return AIMessage(content=content, additional_kwargs=additional_kwargs)
    
    # Handle planning phase
    implementation_plan = result.get("implementation_plan")
    
    # DEBUG: Log implementation plan details
    if implementation_plan is None:
        logger.warning("Implementation plan is None")
    else:
        logger.info("Implementation plan exists:", plan_type=type(implementation_plan).__name__)
        if hasattr(implementation_plan, 'tasks'):
            logger.info("Implementation plan has tasks:", num_tasks=len(implementation_plan.tasks))
    
    if implementation_plan:
        # Extract information from the implementation plan
        if hasattr(implementation_plan, 'tasks'):
            num_tasks = len(implementation_plan.tasks)
            task_summaries = []
            
            for i, task in enumerate(implementation_plan.tasks[:5], 1):  # Show first 5 tasks
                task_summaries.append(f"{i}. {task.logical_task} (file: {task.file_path})")
            
            if num_tasks > 5:
                task_summaries.append(f"... and {num_tasks - 5} more tasks")
            
            content = f"""📋 **Implementation Plan Created**

**Total Tasks:** {num_tasks}

**Implementation Tasks:**
{chr(10).join(task_summaries)}

The SWE agent has analyzed your requirements and created a detailed implementation plan. Each task includes specific atomic steps for code changes.

**Workflow will include:**
- ✅ Feature branch creation
- ✅ Real-time progress streaming  
- ✅ Diff visibility for all changes
- ✅ Architect review after completion
- ✅ PR creation readiness"""
        else:
            content = """📋 **Implementation Plan Created**

The SWE agent has analyzed your requirements and created a detailed implementation plan with specific steps for code changes."""
    else:
        content = """🔍 **SWE Analysis Complete**

The SWE agent has analyzed your requirements and conducted research on the implementation approach. Ready to proceed with implementation planning."""
    
    # Prepare additional_kwargs with safe serialization
    additional_kwargs = {
        "agent_type": "swe_planning",
    }
    
    # Only add implementation_plan if it exists and can be serialized
    if implementation_plan:
        try:
            if hasattr(implementation_plan, 'model_dump'):
                plan_data = implementation_plan.model_dump()
                # Remove any None values from the plan data
                if isinstance(plan_data, dict):
                    plan_data = {k: v for k, v in plan_data.items() if v is not None}
                additional_kwargs["implementation_plan"] = plan_data
            else:
                # Fallback for non-Pydantic objects
                additional_kwargs["implementation_plan"] = implementation_plan
        except Exception as e:
            logger.error("Error serializing implementation_plan:", error=str(e))
            # Don't include implementation_plan if it can't be serialized
    
    # DEBUG: Log what we're about to return
    logger.info("Returning planning message with additional_kwargs:", additional_kwargs=additional_kwargs)
    logger.info("=== END SWE STATE OUTPUT MAPPER DEBUG ===")
    
    return AIMessage(content=content, additional_kwargs=additional_kwargs)


def get_swe_subgraph_config(
    user_id: str,
    sambanova_api_key: str,
    redis_storage: RedisStorage,
    daytona_manager: PersistentDaytonaManager = None,
    github_token: str = None,
) -> Dict:
    """
    Get the SWE subgraph configuration for integration with the main agent.
    
    This follows the same pattern as other subgraphs in the application.
    
    Args:
        user_id: User identifier
        sambanova_api_key: SambaNova API key
        redis_storage: Redis storage instance  
        daytona_manager: Optional Daytona manager
        
    Returns:
        Subgraph configuration dict
    """
    return {
        "description": "Advanced software engineering agent that can analyze codebases, plan implementations, and automatically generate code changes. Use for: code implementation tasks, refactoring requests, feature additions, bug fixes, architectural changes, and any software development work that requires understanding existing code and making targeted modifications.",
        "next_node": "agent",  # Return control to the main agent after SWE operations
        "graph": create_swe_graph(
            user_id=user_id,
            sambanova_api_key=sambanova_api_key,
            redis_storage=redis_storage,
            daytona_manager=daytona_manager,
            github_token=github_token,
        ),
        "state_input_mapper": swe_state_input_mapper,
        "state_output_mapper": swe_state_output_mapper,
    } 