import json
import os
import re
from typing import List
from diff_match_patch import diff_match_patch
from agents.utils.llms import get_sambanova_llm
from agents.components.compound.util import extract_api_key
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END, START
from langgraph.graph import  StateGraph
from agents.components.swe.helpers.prompts import markdown_to_prompt_template
from agents.components.swe.agent.developer.state import SoftwareDeveloperState, Diffs
from agents.components.swe.agent.common.entities import ImplementationPlan
from typing import TypedDict, Optional
from langgraph.prebuilt import ToolNode
from agents.components.swe.agent.tools.search import search_tools
from agents.components.swe.agent.tools.codemap import codemap_tools
from agents.components.swe.agent.tools.github_tools import get_github_tools
from agents.components.swe.agent.tools.write import get_files_structure
from agents.components.swe.agent.tools.daytona_tools import get_swe_daytona_tools
import structlog

logger = structlog.get_logger(__name__)

# Load the extract diff prompt
extract_diffs_tasks_prompt = markdown_to_prompt_template("agents/components/swe/agent/developer/prompts/create_diff_prompt.md")
implement_diffs_prompt = markdown_to_prompt_template("agents/components/swe/agent/developer/prompts/implement_diff.md")
implement_new_file_prompt = markdown_to_prompt_template("agents/components/swe/agent/developer/prompts/implement_new_file.md")

# Create LLM factory function that extracts API key from config
def get_swe_llm(*, config: RunnableConfig = None):
    """Get SambaNova LLM with API key from config"""
    api_key = extract_api_key(config)
    return get_sambanova_llm(api_key=api_key, model="DeepSeek-V3-0324")

# Create the runnable with the prompt and model - these will be called with config to get the LLM instance
def create_extract_diff_runnable(config: RunnableConfig = None):
    llm = get_swe_llm(config=config)
    return extract_diffs_tasks_prompt | llm | StrOutputParser()

def create_edit_according_to_diff_runnable(config: RunnableConfig = None):
    llm = get_swe_llm(config=config)
    return implement_diffs_prompt | llm | StrOutputParser()

def create_create_new_file_runnable(config: RunnableConfig = None):
    llm = get_swe_llm(config=config)
    return implement_new_file_prompt | llm | StrOutputParser()

# Load the get clear implementation plan prompt
get_clear_implementation_plan_prompt = markdown_to_prompt_template("agents/components/swe/agent/developer/prompts/get_clear_implementation_plan.md")

# Create the runnable with the prompt and model
def create_get_clear_implementation_plan_runnable(config: RunnableConfig = None, daytona_tools=None):
    llm = get_swe_llm(config=config)
    
    # Use ONLY Daytona tools when available to avoid local file access conflicts
    if daytona_tools:
        # Use only Daytona-based tools when sandbox is available
        all_tools = daytona_tools
    else:
        # Fallback to basic tools when no Daytona manager (for testing)
        all_tools = search_tools + codemap_tools
    
    return get_clear_implementation_plan_prompt | llm.bind_tools(all_tools)

dmp = diff_match_patch()

# Define input/output types for the developer workflow
class SoftwareDeveloperInput(TypedDict):
    implementation_plan: Optional[ImplementationPlan]
    working_directory: Optional[str]

class SoftwareDeveloperOutput(TypedDict):
    implementation_plan: Optional[ImplementationPlan]
    working_directory: Optional[str]

def start_implementing(state: SoftwareDeveloperState):
    return {
        "current_task_idx": 0,
        "current_atomic_task_idx": 0
    }


def proceed_to_next_atomic_task(state: SoftwareDeveloperState):
    # Get current indices
    current_task_idx = state.current_task_idx
    current_atomic_task_idx = state.current_atomic_task_idx
    
    # Get the implementation plan
    plan = state.implementation_plan
    
    # Get current task
    current_task = plan.tasks[current_task_idx]
    atomic_tasks = current_task.atomic_tasks
    
    # If we've completed all atomic tasks in current task
    if current_atomic_task_idx >= len(atomic_tasks) - 1:
        # Move to next main task and reset atomic task index
        return {
            "current_task_idx": current_task_idx + 1,
            "current_atomic_task_idx": 0
        }
    # Otherwise, move to next atomic task
    return {
        "current_task_idx": current_task_idx,
        "current_atomic_task_idx": current_atomic_task_idx + 1
    }


async def prepare_for_implementation(state: SoftwareDeveloperState, daytona_manager=None):
    """
    Prepare for implementation by reading file content using ONLY Daytona tools.
    No local file access - everything happens in the sandbox.
    """
    current_task = state.implementation_plan.tasks[state.current_task_idx]
    file_path = current_task.file_path
    
    # Use Daytona manager to check if file exists and read content
    file_content = "This is a new file"
    codebase_structure = ""
    
    if daytona_manager:
        try:
            # Try to read the file from Daytona sandbox
            success, content = await daytona_manager.read_file(file_path)
            if success:
                # Ensure content is a string, not bytes
                if isinstance(content, bytes):
                    try:
                        file_content = content.decode('utf-8')
                    except UnicodeDecodeError:
                        file_content = content.decode('utf-8', errors='ignore')
                else:
                    file_content = str(content)
            else:
                # File doesn't exist - that's okay, we'll create it
                file_content = "This is a new file"
                
            # Get repository structure using Daytona
            try:
                # Get repository structure from the working directory
                working_dir = state.working_directory or "."
                all_files = await daytona_manager.get_all_files_recursive(working_dir)
                
                # Create a simple tree structure
                structure_lines = []
                for file_info in all_files[:50]:  # Limit to first 50 files for brevity
                    structure_lines.append(f"  {file_info['path']}")
                
                codebase_structure = f"Repository structure (showing first 50 files):\n" + "\n".join(structure_lines)
                
            except Exception as e:
                codebase_structure = f"Repository structure unavailable: {str(e)}"
                
        except Exception as e:
            # If Daytona operation fails, use fallback
            file_content = "This is a new file"
            codebase_structure = f"Error accessing sandbox: {str(e)}"
    else:
        # Fallback to local operations only when no Daytona manager (testing)
        try:
            with open(file_path, "r") as file:
                file_content = file.read()
        except FileNotFoundError:
            file_content = "This is a new file"
            
        codebase_structure = get_files_structure.invoke({"directory": state.working_directory or "."})

    return {
        "current_file_content": file_content,
        "codebase_structure": codebase_structure,
        "atomic_implementation_research": None
    }


def is_implementation_complete(state: SoftwareDeveloperState):
    """
    Check if we've completed all implementation tasks.
    """
    current_task_idx = state.current_task_idx
    plan = state.implementation_plan
    return END if current_task_idx >= len(plan.tasks) else "continue"

def convert_tools_messages_to_ai_and_human(implementation_research_scratchpad: List[AnyMessage]):
    messages = []
    for message in implementation_research_scratchpad:
        if message.type == "ai":
            if message.tool_calls:
                tool_name = message.tool_calls[0]["name"]
                tool_args = json.dumps(message.tool_calls[0]["args"])
                messages.append(AIMessage(content=f"I want to call the tool {tool_name} with the following arguments: {tool_args}"))
            else:
                messages.append(message)
        elif message.type == "tool":
            messages.append(HumanMessage(content=f"When executing Tool {message.name} \n The result was {message.content} was called"))
        else:
            messages.append(message)
    return messages

async def creating_diffs_for_task(state: SoftwareDeveloperState, daytona_manager=None, *, config: RunnableConfig = None):
    """
    Create diffs for the current task using ONLY Daytona tools.
    Includes proper Git branching and file handling.
    """
    # Get current task information
    current_task = state.implementation_plan.tasks[state.current_task_idx]
    current_atomic_task = current_task.atomic_tasks[state.current_atomic_task_idx]
    file_path = current_task.file_path

    if not daytona_manager:
        # Fallback to local operations only for testing
        return await _creating_diffs_for_task_local(state, config)

    try:
        # STEP 1: Create a feature branch for this implementation
        working_dir = state.working_directory or "."
        branch_name = f"swe-agent-implementation-{hash(current_atomic_task.atomic_task) % 10000}"
        
        # Check if we're already on a feature branch or create one
        try:
            current_branch_result = await daytona_manager.execute(f"cd {working_dir} && git rev-parse --abbrev-ref HEAD")
            current_branch = current_branch_result.strip()
            
            if current_branch in ["main", "master", "develop"]:
                # Create and switch to feature branch
                branch_result = await daytona_manager.execute(f"cd {working_dir} && git checkout -b {branch_name}")
                logger.info(f"Created feature branch: {branch_name}")
            else:
                # Already on a feature branch, continue using it
                branch_name = current_branch
                logger.info(f"Continuing with existing branch: {branch_name}")
                
        except Exception as e:
            logger.warning(f"Git branching failed: {e}, continuing without branch")

        # STEP 2: Check if file exists in sandbox
        success, existing_content = await daytona_manager.read_file(file_path)
        
        # Ensure content is a string, not bytes
        if success and existing_content:
            if isinstance(existing_content, bytes):
                try:
                    existing_content = existing_content.decode('utf-8')
                except UnicodeDecodeError:
                    existing_content = existing_content.decode('utf-8', errors='ignore')
        
        file_exists = success and existing_content and existing_content != "This is a new file"
        
        if not file_exists:
            # STEP 3A: Create new file
            logger.info(f"Creating new file: {file_path}")
            new_file_content = create_create_new_file_runnable(config).invoke({
                "task": current_atomic_task.atomic_task,
                "additional_context": current_atomic_task.additional_context,
                "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research),
                "file_path": file_path
            })
            
            # Write the new file using Daytona
            await daytona_manager.write_file(file_path, new_file_content)
            logger.info(f"Successfully created new file: {file_path}")
            
        else:
            # STEP 3B: Edit existing file
            logger.info(f"Editing existing file: {file_path}")
            
            # Add line numbers to existing content for diff creation
            lines = []
            for i, line in enumerate(existing_content.splitlines(), start=1):
                lines.append(f"{i}| {line}")
            file_content_with_lines = "\n".join(lines)

            # Generate diffs for the existing file
            diffs_tasks = create_extract_diff_runnable(config).invoke({
                "task": current_atomic_task.atomic_task,
                "additional_context": current_atomic_task.additional_context,
                "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research),
                "file_path": file_path,
                "file_content": file_content_with_lines,
                "output_format": JsonOutputParser(pydantic_object=Diffs).get_format_instructions()
            })
            
            # Apply diffs to the file
            modified_content = await _apply_diffs_to_content(diffs_tasks, existing_content, daytona_manager, file_path)
            
            # Write the modified content back using Daytona
            await daytona_manager.write_file(file_path, modified_content)
            logger.info(f"Successfully updated existing file: {file_path}")

        # DEBUG: Log what we're about to return
        return_dict = {
            "current_branch": branch_name,
            "atomic_implementation_research": []  # Clear research after implementation
        }
        
        import structlog
        debug_logger = structlog.get_logger(__name__)
        debug_logger.info("=== CREATING_DIFFS_FOR_TASK DEBUG ===")
        for key, value in return_dict.items():
            if value is None:
                debug_logger.warning(f"creating_diffs_for_task returning None value for key: {key}")
            else:
                debug_logger.info(f"creating_diffs_for_task returning key '{key}' with type: {type(value).__name__}")
        debug_logger.info("=== END CREATING_DIFFS_FOR_TASK DEBUG ===")
        
        return return_dict
            
    except Exception as e:
        logger.error(f"Error in creating_diffs_for_task: {e}")
        
        error_return = {
            "atomic_implementation_research": [
                AIMessage(content=f"Error implementing task: {str(e)}")
            ]
        }
        
        import structlog
        debug_logger = structlog.get_logger(__name__)
        debug_logger.info("=== CREATING_DIFFS_FOR_TASK ERROR DEBUG ===")
        for key, value in error_return.items():
            if value is None:
                debug_logger.warning(f"creating_diffs_for_task error returning None value for key: {key}")
            else:
                debug_logger.info(f"creating_diffs_for_task error returning key '{key}' with type: {type(value).__name__}")
        debug_logger.info("=== END CREATING_DIFFS_FOR_TASK ERROR DEBUG ===")
        
        return error_return


async def _apply_diffs_to_content(diffs_tasks: str, original_content: str, daytona_manager, file_path: str) -> str:
    """Apply diffs to content and return modified content"""
    try:
        # Ensure original_content is a string
        if isinstance(original_content, bytes):
            try:
                original_content = original_content.decode('utf-8')
            except UnicodeDecodeError:
                original_content = original_content.decode('utf-8', errors='ignore')
        
        # Find all content between <code_change_request> and </code_change_request>
        blocks = re.findall(
            r"<code_change_request>(.*?)</code_change_request>", diffs_tasks, re.DOTALL
        )

        current_content = original_content
        
        for block in blocks:
            # Extract original and edited code snippets
            match = re.search(
                r"original_code_snippet:\s*(.*?)\s*edit_code_snippet:\s*(.*)",
                block,
                re.DOTALL,
            )
            if match:
                original_code = match.group(1).strip()
                edited_code = match.group(2).strip()
                
                # Parse line numbers from original code
                orig_lines = original_code.splitlines()
                if orig_lines:
                    try:
                        first_line = int(orig_lines[0].split("|")[0].strip())
                        last_line = int(orig_lines[-1].split("|")[0].strip())
                        
                        # Apply the change - ensure all operations work with strings
                        content_lines = current_content.splitlines()
                        new_content_lines = (
                            content_lines[: first_line - 1]
                            + edited_code.splitlines()
                            + content_lines[last_line:]
                        )
                        current_content = "\n".join(new_content_lines)
                        
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Could not parse line numbers from diff: {e}")
                        continue
                        
        # Ensure we return a string
        return str(current_content)
        
    except Exception as e:
        logger.error(f"Error applying diffs: {e}")
        # Ensure we return the original content as a string
        if isinstance(original_content, bytes):
            try:
                return original_content.decode('utf-8')
            except UnicodeDecodeError:
                return original_content.decode('utf-8', errors='ignore')
        return str(original_content)


async def _creating_diffs_for_task_local(state: SoftwareDeveloperState, config: RunnableConfig = None):
    """Fallback local implementation for testing without Daytona"""
    # Get current task information  
    current_task = state.implementation_plan.tasks[state.current_task_idx]
    current_atomic_task = current_task.atomic_tasks[state.current_atomic_task_idx]
    file_path = current_task.file_path

    # check if file is new
    if not os.path.exists(file_path):
        new_file_content = create_create_new_file_runnable(config).invoke({
            "task": current_atomic_task.atomic_task,
            "additional_context": current_atomic_task.additional_context,
            "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research),
            "file_path": file_path
        })
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as file:
            file.write(new_file_content)
            file.flush()
    else:
        # Get the diffs
        with open(file_path, "r") as file:
            file_content = file.read()
        # add line numbers
        lines = []
        for i, line in enumerate(file_content.splitlines(), start=1):
            lines.append(f"{i}| {line}")
        file_content = "\n".join(lines)

        diffs_tasks = create_extract_diff_runnable(config).invoke({
            "task": current_atomic_task.atomic_task,
            "additional_context": current_atomic_task.additional_context,
            "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research),
            "file_path": file_path,
            "file_content": file_content,
            "output_format": JsonOutputParser(pydantic_object=Diffs).get_format_instructions()
        })
        # Find all content between <code_change_request> and </code_change_request>
        blocks = re.findall(
            r"<code_change_request>(.*?)</code_change_request>", diffs_tasks, re.DOTALL
        )

        for block in blocks:
            # Use regex to extract the original code snippet and the task description.
            # The re.DOTALL flag allows the dot (.) to match newline characters.
            match = re.search(
                r"original_code_snippet:\s*(.*?)\s*edit_code_snippet:\s*(.*)",
                block,
                re.DOTALL,
            )
            if match:
                with open(file_path, "r") as f:
                    file_content = f.read()
                original_code = match.group(1).strip()
                edited_code = match.group(2).strip()
                orig_lines = original_code.splitlines()
                first_line = int(orig_lines[0].split("|")[0].strip())
                last_line = int(orig_lines[-1].split("|")[0].strip())
                new_content = file_content.splitlines()
                new_content = (
                    new_content[: first_line - 1]
                    + edited_code.splitlines()
                    + new_content[last_line:]
                )
                with open(file_path, "w") as f:
                    f.write("\n".join(new_content))
                    f.flush()
    
    return {"atomic_implementation_research": []}

def get_clear_implementation_plan_for_atomic_task(state: SoftwareDeveloperState, *, config: RunnableConfig = None, daytona_tools=None):
    """Get clear implementation plan for the atomic task"""
    current_task = state.implementation_plan.tasks[state.current_task_idx]
    current_atomic_task = current_task.atomic_tasks[state.current_atomic_task_idx]
    result = create_get_clear_implementation_plan_runnable(config, daytona_tools).invoke({
        "development_task": current_atomic_task.atomic_task,
        "file_content": state.current_file_content,
        "target_file": current_task.file_path,
        "codebase_structure": state.codebase_structure,
        "additional_context": current_atomic_task.additional_context,
        "atomic_implementation_research": state.atomic_implementation_research
    })
    return {"atomic_implementation_research": [result]}

def should_continue_implementation_research(state: SoftwareDeveloperState):
    """Router function to determine if tools should be called"""
    last_research_step = state.atomic_implementation_research[-1]

    if last_research_step.tool_calls:
        return "should_continue_research"

    return "implement_plan"

# Create tool node
# Default research_tool_node for backward compatibility (without Daytona tools)
research_tool_node = ToolNode(search_tools + codemap_tools, messages_key="atomic_implementation_research")

# Create the workflow graph
workflow = StateGraph(SoftwareDeveloperState)

# Add nodes
workflow.add_node("start_implementing", start_implementing)
workflow.add_node("prepare_for_implementation", prepare_for_implementation)
workflow.add_node("proceed_to_next_atomic_task", proceed_to_next_atomic_task)
workflow.add_node("get_clear_implementation_plan_for_atomic_task", get_clear_implementation_plan_for_atomic_task)
workflow.add_node("research_tool_node", research_tool_node )
workflow.add_node("creating_diffs_for_task", creating_diffs_for_task)

# Add edges
# Reset the system and load the file from the context of atomic task (if not new file)
workflow.add_edge(START, "start_implementing")
# Read file content and reset previous implementation research
workflow.add_edge("start_implementing", "prepare_for_implementation")
# Go to research about how to implement the atomic task
workflow.add_edge("prepare_for_implementation", "get_clear_implementation_plan_for_atomic_task")
# Check if research is done or we should continue research
workflow.add_conditional_edges(
    "get_clear_implementation_plan_for_atomic_task",
    should_continue_implementation_research,
    {
        "should_continue_research": "research_tool_node",
        "implement_plan": "creating_diffs_for_task"
    }
)
# Go back from executing a research tool to research about implementation
workflow.add_edge("research_tool_node", "get_clear_implementation_plan_for_atomic_task")
# After the research lets apply the diffs
workflow.add_edge("creating_diffs_for_task", "proceed_to_next_atomic_task")
# If next atomic task exists rest and go back to research if not end as everything was implemented
workflow.add_conditional_edges(
    "proceed_to_next_atomic_task",
    is_implementation_complete,
    {
        "continue": "prepare_for_implementation",
        END: END
    }
)

def create_swe_developer(daytona_manager=None, github_token=None):
    """Create the SWE developer workflow with Daytona tools support"""
    
    # IMPORTANT: Use ONLY Daytona tools for SWE operations to avoid local file access conflicts
    if daytona_manager:
        # Use only Daytona-based tools when sandbox is available
        daytona_tools = get_swe_daytona_tools(daytona_manager)
        github_tools = get_github_tools(github_token) if github_token else []
        all_tools = daytona_tools + github_tools
    else:
        # Fallback to basic tools when no Daytona manager (for testing)
        all_tools = codemap_tools + search_tools
        if github_token:
            all_tools += get_github_tools(github_token)
    
    tool_node = ToolNode(all_tools)
    
    # Create workflow
    workflow = StateGraph(SoftwareDeveloperState)
    
    # Import functools for partial application
    from functools import partial
    
    # Add nodes with daytona_manager passed as parameter
    workflow.add_node("prepare_for_implementation", partial(prepare_for_implementation, daytona_manager=daytona_manager))
    workflow.add_node("get_clear_implementation_plan_for_atomic_task", partial(get_clear_implementation_plan_for_atomic_task, daytona_tools=all_tools))
    workflow.add_node("tools", tool_node)
    workflow.add_node("implement_plan", partial(creating_diffs_for_task, daytona_manager=daytona_manager))
    
    # Add edges
    workflow.add_edge(START, "prepare_for_implementation")
    workflow.add_edge("prepare_for_implementation", "get_clear_implementation_plan_for_atomic_task")
    workflow.add_conditional_edges("get_clear_implementation_plan_for_atomic_task", should_continue_implementation_research, {"should_continue_research": "tools", "implement_plan": "implement_plan"})
    workflow.add_edge("tools", "get_clear_implementation_plan_for_atomic_task")
    workflow.add_edge("implement_plan", END)
    
    return workflow.compile()

# Default developer without Daytona tools for backward compatibility
swe_developer = workflow.compile().with_config({"tags": ["developer-agent-v3"]})
