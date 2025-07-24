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
        input_text: User's implementation request (can include repository context)

    Returns:
        State dictionary for the SWE agent
    """
    # Parse input for repository context if provided
    # Format: "REPO: owner/repo\nBRANCH: main\n\nTask description here"
    repo_context = ""
    task_content = input_text
    repository_name = None  # Default to None - work with current directory like datagen
    
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
        prompt_content = f"""Repository Context:
{repo_context.strip()}

Implementation Task:
{task_content}

Please analyze the repository context and implement the requested changes. Use the GitHub tools to explore the repository structure, understand the codebase, and plan your implementation accordingly."""
    else:
        prompt_content = f"Please implement the following requirement: {task_content}"
    
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
    implementation_plan = result.get("implementation_plan")
    
    if implementation_plan:
        # Extract information from the implementation plan
        num_tasks = len(implementation_plan.tasks)
        task_summaries = []
        
        for i, task in enumerate(implementation_plan.tasks[:5], 1):  # Show first 5 tasks
            task_summaries.append(f"{i}. {task.logical_task} (file: {task.file_path})")
        
        if num_tasks > 5:
            task_summaries.append(f"... and {num_tasks - 5} more tasks")
        
        content = f"""Implementation Plan Created Successfully

**Total Tasks:** {num_tasks}

**Implementation Tasks:**
{chr(10).join(task_summaries)}

The SWE agent has analyzed your requirements and created a detailed implementation plan. Each task includes specific atomic steps for code changes. The implementation is ready to proceed with automated code generation and testing in the sandbox environment."""
    else:
        content = """SWE Analysis Complete

The SWE agent has analyzed your requirements and conducted research on the implementation approach. Additional context or clarification may be needed to proceed with implementation."""
    
    return AIMessage(
        content=content,
        additional_kwargs={
            "agent_type": "swe_end",
            "implementation_plan": implementation_plan.model_dump() if implementation_plan else None,
        },
    )


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