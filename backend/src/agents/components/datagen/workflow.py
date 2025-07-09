import re
import uuid

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
from agents.components.datagen.message_capture_agent import MessageCaptureAgent
from agents.components.datagen.node import (
    agent_node,
    human_choice_node,
    note_agent_node,
    refiner_node,
)
from agents.components.datagen.router import (
    human_choice_router,
    hypothesis_router,
    process_router,
    quality_review_router,
)
from agents.components.datagen.state import State
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.storage.redis_storage import RedisStorage
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

logger = structlog.get_logger(__name__)


class WorkflowManager:
    def __init__(
        self,
        language_models,
        user_id: str,
        redis_storage: RedisStorage,
        daytona_manager: PersistentDaytonaManager,
        directory_content: list[str],
    ):
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
        self.user_id = user_id
        self.agents = {}
        self.redis_storage = redis_storage
        self.daytona_manager = daytona_manager
        self.directory_content = directory_content
        self.agents = self.create_agents()
        self.setup_workflow()

    def create_agents(self):
        """Create all system agents"""
        # Get language models
        llm = self.language_models["llm"]
        report_agent_llm = self.language_models["report_agent_llm"]
        code_agent_llm = self.language_models["code_agent_llm"]
        note_agent_llm = self.language_models["note_agent_llm"]
        hypothesis_agent_llm = self.language_models["hypothesis_agent_llm"]
        process_agent_llm = self.language_models["process_agent_llm"]
        quality_review_agent_llm = self.language_models["quality_review_agent_llm"]
        refiner_agent_llm = self.language_models["refiner_agent_llm"]

        # Create agents dictionary
        agents = {}

        # Create each agent using their respective creation functions
        agents["hypothesis_agent"] = create_hypothesis_agent(
            hypothesis_agent_llm=hypothesis_agent_llm,
            members=self.members,
            daytona_manager=self.daytona_manager,
            directory_content=self.directory_content,
        )

        agents["process_agent"] = create_process_agent(
            process_agent_llm=process_agent_llm
        )

        agents["visualization_agent"] = create_visualization_agent(
            llm=llm,
            members=self.members,
            daytona_manager=self.daytona_manager,
            directory_content=self.directory_content,
        )

        agents["code_agent"] = create_code_agent(
            code_agent_llm=code_agent_llm,
            members=self.members,
            daytona_manager=self.daytona_manager,
            directory_content=self.directory_content,
        )

        agents["searcher_agent"] = create_search_agent(
            llm=llm,
            members=self.members,
            daytona_manager=self.daytona_manager,
            directory_content=self.directory_content,
        )

        agents["report_agent"] = create_report_agent(
            report_agent_llm=report_agent_llm,
            members=self.members,
            daytona_manager=self.daytona_manager,
            directory_content=self.directory_content,
        )

        agents["quality_review_agent"] = create_quality_review_agent(
            quality_review_agent_llm=quality_review_agent_llm,
        )

        agents["note_agent"] = create_note_agent(
            note_agent_llm=note_agent_llm,
            daytona_manager=self.daytona_manager,
        )

        agents["refiner_agent"] = create_refiner_agent(
            refiner_agent_llm=refiner_agent_llm,
        )

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
            output_processor = {
                "task": lambda x: re.search(r"Task:\s*(.*)", x).group(1)
            }
            return await agent_node(
                state=state,
                agent=self.agents["process_agent"],
                name="process_agent",
                state_key="process_decision",
                output_processor=output_processor,
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
                state, self.agents["report_agent"], "report_agent", "report_state"
            )

        async def quality_review_node(state):
            name = "quality_review_agent"
            agent: MessageCaptureAgent = self.agents[name]
            logger.info(f"Processing agent in quality review node: {name}")
            try:

                # Provide more context by including the last 5 messages instead of just 2
                # This gives the quality review agent better context for decision making
                trimmed_state = {
                    **state,
                    "internal_messages": (
                        state["internal_messages"][-5:]
                        if len(state["internal_messages"]) > 5
                        else state["internal_messages"]
                    ),
                }
                output_message = await agent.ainvoke(trimmed_state)

                interceptor_messages = agent.llm_interceptor.captured_messages
                fixing_interceptor_messages = (
                    agent.llm_fixing_interceptor.captured_messages
                )
                captured_messages = interceptor_messages + fixing_interceptor_messages
                for m in captured_messages:
                    m.additional_kwargs["agent_type"] = f"data_science_{name}"
                logger.debug(
                    f"Captured {len(captured_messages)} messages from MessageCaptureAgent"
                )

                output_ai_message = AIMessage(
                    content=f"Quality review: Passed: {output_message.passed}, Reason: {output_message.reason}",
                    id=str(uuid.uuid4()),
                    sender=name,
                )

                return {
                    "internal_messages": [output_ai_message],
                    "messages": captured_messages,
                    "quality_review": output_message.model_dump(),
                    "sender": name,
                }
            except Exception as e:
                logger.error(
                    f"Error occurred while processing agent in quality review node {name}: {str(e)}",
                    exc_info=True,
                )
                error_message = AIMessage(
                    content=f"Error in {name}: {str(e)}",
                    id=str(uuid.uuid4()),
                    sender=name,
                )
                return {
                    "internal_messages": state["internal_messages"] + [error_message],
                }

        async def note_taker_node(state):
            return await note_agent_node(state, self.agents["note_agent"], "note_agent")

        async def refiner_node_async(state):
            return await refiner_node(
                state=state,
                agent=self.agents["refiner_agent"],
                name="refiner_agent",
                daytona_manager=self.daytona_manager,
                redis_storage=self.redis_storage,
                user_id=self.user_id,
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
        self.workflow.add_node("Refiner", refiner_node_async)
        self.workflow.add_node("Cleanup", self.cleanup_node)

        # Add edges
        self.workflow.add_edge(START, "Hypothesis")

        # Add conditional edge from Hypothesis for ReAct loop
        self.workflow.add_conditional_edges(
            "Hypothesis",
            hypothesis_router,
            {"Hypothesis": "Hypothesis", "HumanChoice": "HumanChoice"},
        )

        self.workflow.add_conditional_edges(
            "HumanChoice",
            human_choice_router,
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
            quality_review_router,
            {
                "Visualization": "Visualization",
                "Search": "Search",
                "Coder": "Coder",
                "Report": "Report",
                "NoteTaker": "NoteTaker",
            },
        )

        self.workflow.add_edge("NoteTaker", "Process")
        self.workflow.add_edge("Refiner", "Cleanup")
        self.workflow.add_edge("Cleanup", END)

        self.graph = self.workflow.compile()

    async def cleanup_node(self, state: dict) -> dict:
        """Node to perform cleanup."""
        logger.info("Executing cleanup node.")
        await self.cleanup()
        return {}

    async def cleanup(self):
        """Clean up the persistent Daytona manager."""
        if self.daytona_manager:
            await self.daytona_manager.cleanup()
            self.daytona_manager = None
