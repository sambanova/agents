import structlog
from agents.components.datagen.agent.code_agent import create_code_agent
from agents.components.datagen.agent.hypothesis_agent import create_hypothesis_agent
from agents.components.datagen.agent.note_agent import create_note_agent
from agents.components.datagen.agent.process_agent import create_process_agent
from agents.components.datagen.agent.quality_review_agent import (
    create_quality_review_agent,
)
from agents.components.datagen.agent.refiner_agent import create_refiner_agent
from agents.components.datagen.agent.report_agent import create_report_agent
from agents.components.datagen.agent.search_agent import create_search_agent
from agents.components.datagen.agent.visualization_agent import (
    create_visualization_agent,
)
from agents.components.datagen.node import (
    agent_node,
    human_choice_node,
    human_review_node,
    note_agent_node,
    refiner_node,
)
from agents.components.datagen.router import (
    QualityReview_router,
    hypothesis_router,
    process_router,
)
from agents.components.datagen.state import State
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

logger = structlog.get_logger(__name__)


class WorkflowManager:
    def __init__(self, language_models):
        """
        Initialize the workflow manager with language models.

        Args:
            language_models (dict): Dictionary containing language model instances
        """
        self.language_models = language_models
        self.workflow = None
        self.memory = None
        self.graph = None
        self.members = [
            "Hypothesis",
            "Process",
            "Visualization",
            "Search",
            "Coder",
            "Report",
            "QualityReview",
            "Refiner",
        ]
        self.agents = self.create_agents()
        self.setup_workflow()

        # Persistent Daytona manager
        self.daytona_manager = None

    def create_agents(self):
        """Create all system agents"""
        # Get language models
        llm = self.language_models["llm"]
        power_llm = self.language_models["power_llm"]
        json_llm = self.language_models["json_llm"]

        # Create agents dictionary
        agents = {}

        # Create each agent using their respective creation functions
        agents["hypothesis_agent"] = create_hypothesis_agent(llm, self.members)

        agents["process_agent"] = create_process_agent(power_llm)

        agents["visualization_agent"] = create_visualization_agent(
            llm,
            self.members,
        )

        agents["code_agent"] = create_code_agent(power_llm, self.members)

        agents["searcher_agent"] = create_search_agent(llm, self.members)

        agents["report_agent"] = create_report_agent(power_llm, self.members)

        agents["quality_review_agent"] = create_quality_review_agent(llm, self.members)

        agents["note_agent"] = create_note_agent(json_llm)

        agents["refiner_agent"] = create_refiner_agent(power_llm, self.members)

        return agents

    def setup_workflow(self):
        """Set up the workflow graph"""
        self.workflow = StateGraph(State)

        # Create async wrapper functions for agent nodes
        async def hypothesis_node(state):
            return await agent_node(
                state, self.agents["hypothesis_agent"], "hypothesis_agent", "hypothesis"
            )

        async def process_node(state):
            return await agent_node(
                state, self.agents["process_agent"], "process_agent", "process_decision"
            )

        async def visualization_node(state):
            return await agent_node(
                state,
                self.agents["visualization_agent"],
                "visualization_agent",
                "visualization_state",
            )

        async def search_node(state):
            return await agent_node(
                state, self.agents["searcher_agent"], "searcher_agent", "searcher_state"
            )

        async def coder_node(state):
            return await agent_node(
                state, self.agents["code_agent"], "code_agent", "code_state"
            )

        async def report_node(state):
            return await agent_node(
                state, self.agents["report_agent"], "report_agent", "report_section"
            )

        async def quality_review_node(state):
            name = "quality_review_agent"
            agent = self.agents[name]
            logger.info(f"Processing special agent: {name}")
            try:
                result = await agent.ainvoke(state)
                output_message = result.get("output")

                if output_message is None:
                    raise ValueError("Agent output is missing the 'output' key.")

                # Special logic for quality review: check for "revision needed"
                content = (
                    output_message.content
                    if hasattr(output_message, "content")
                    else str(output_message)
                )
                needs_revision = "revision needed" in content.lower()
                logger.info(f"Quality review updated. Needs revision: {needs_revision}")

                return {
                    "messages": state["messages"] + [output_message],
                    "quality_review": output_message,
                    "needs_revision": needs_revision,
                    "sender": name,
                }
            except Exception as e:
                logger.error(
                    f"Error occurred while processing agent {name}: {str(e)}",
                    exc_info=True,
                )
                error_message = AIMessage(
                    content=f"Error in {name}: {str(e)}", name=name
                )
                return {"messages": state["messages"] + [error_message]}

        async def note_taker_node(state):
            return await note_agent_node(state, self.agents["note_agent"], "note_agent")

        async def refiner_node_async(state):
            return await refiner_node(
                state, self.agents["refiner_agent"], "refiner_agent"
            )

        # Add nodes
        self.workflow.add_node("Hypothesis", hypothesis_node)
        self.workflow.add_node("Process", process_node)
        self.workflow.add_node("Visualization", visualization_node)
        self.workflow.add_node("Search", search_node)
        self.workflow.add_node("Coder", coder_node)
        self.workflow.add_node("Report", report_node)
        self.workflow.add_node("QualityReview", quality_review_node)
        self.workflow.add_node("NoteTaker", note_taker_node)
        self.workflow.add_node("HumanChoice", human_choice_node)
        self.workflow.add_node("HumanReview", human_review_node)
        self.workflow.add_node("Refiner", refiner_node_async)

        # Add edges
        self.workflow.add_edge(START, "Hypothesis")
        self.workflow.add_edge("Hypothesis", "HumanChoice")

        self.workflow.add_conditional_edges(
            "HumanChoice",
            hypothesis_router,
            {"Hypothesis": "Hypothesis", "Process": "Process"},
        )

        self.workflow.add_conditional_edges(
            "Process",
            process_router,
            {
                "Coder": "Coder",
                "Search": "Search",
                "Visualization": "Visualization",
                "Report": "Report",
                "Process": "Process",
                "Refiner": "Refiner",
            },
        )

        for member in ["Visualization", "Search", "Coder", "Report"]:
            self.workflow.add_edge(member, "QualityReview")

        self.workflow.add_conditional_edges(
            "QualityReview",
            QualityReview_router,
            {
                "Visualization": "Visualization",
                "Search": "Search",
                "Coder": "Coder",
                "Report": "Report",
                "NoteTaker": "NoteTaker",
            },
        )

        self.workflow.add_edge("NoteTaker", "Process")
        self.workflow.add_edge("Refiner", "HumanReview")

        self.workflow.add_conditional_edges(
            "HumanReview",
            lambda state: (
                "Process" if state and state.get("needs_revision", False) else "END"
            ),
            {"Process": "Process", "END": END},
        )

        # Compile workflow
        self.memory = MemorySaver()
        self.graph = self.workflow.compile()

    def get_graph(self):
        """Return the compiled workflow graph"""
        return self.graph

    async def initialize_persistent_daytona(
        self, user_id: str, redis_storage=None, data_sources=None
    ):
        """Initialize the persistent Daytona client for the workflow."""
        try:
            self.daytona_manager = await PersistentDaytonaManager.initialize(
                user_id=user_id, redis_storage=redis_storage, data_sources=data_sources
            )
            logger.info("Persistent Daytona client initialized for workflow")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize persistent Daytona: {e}")
            return False

    async def cleanup_persistent_daytona(self):
        """Clean up the persistent Daytona client."""
        if self.daytona_manager:
            try:
                await self.daytona_manager.cleanup()
                self.daytona_manager = None
                logger.info("Persistent Daytona client cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up persistent Daytona: {e}")

    async def run_with_persistent_daytona(
        self, initial_state, config, user_id: str, redis_storage=None, data_sources=None
    ):
        """
        Run the workflow with persistent Daytona client.

        Args:
            initial_state: Initial state for the workflow
            config: Configuration for the workflow
            user_id: User ID for the Daytona session
            redis_storage: Redis storage instance (optional)
            data_sources: List of file paths to upload to sandbox root folder (optional)

        Returns:
            Generator of events from the workflow
        """
        # Initialize persistent Daytona
        await self.initialize_persistent_daytona(user_id, redis_storage, data_sources)

        try:
            # Run the workflow
            async for event in self.graph.astream(
                initial_state, config, stream_mode="values"
            ):
                yield event
        finally:
            # Always cleanup Daytona when done
            await self.cleanup_persistent_daytona()
