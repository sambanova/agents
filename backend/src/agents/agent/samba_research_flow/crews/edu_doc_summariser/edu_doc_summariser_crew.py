import os
import sys
from typing import Any, Dict, List

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from pydantic import BaseModel
from agents.agent.crewai_llm import CustomLLM
from agents.registry.model_registry import model_registry
from agents.utils.agent_thought import RedisConversationLogger

current_dir = os.getcwd()
repo_dir = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(repo_dir)


@CrewBase
class EduDocSummariserCrew:
    """
    Educational document summariser crew implementation.

    This crew is responsible for summarising educational documents.
    """

    agents_config: Dict[str, Any]  # Type hint for the config attribute
    tasks_config: Dict[str, Any]  # Type hint for the tasks config
    agents: List[Any]  # Type hint for the agents list
    tasks: List[Any]  # Type hint for the tasks list
    llm: LLM
    llm_api_key: str
    serper_key: str
    user_id: str
    run_id: str

    def __init__(
        self,
        llm_api_key: str,
        provider: str,
        user_id: str = None,
        run_id: str = None,
        verbose: bool = True,
    ) -> None:
        """Initialize the research crew with API keys."""
        super().__init__()
        self.agents_config = {}
        self.tasks_config = {}
        self.agents = []
        self.tasks = []
        self.llm_api_key = llm_api_key
        model_info = model_registry.get_model_info(model_key="llama-3.3-70b", provider=provider)
        self.llm = CustomLLM(
            model=model_info["crewai_prefix"] + "/" + model_info["model"],
            temperature=0.00,
            max_tokens=8192,
            api_key=self.llm_api_key,
        )
        self.user_id = user_id
        self.run_id = run_id
        self.verbose = verbose

    @agent
    def summariser(self) -> Agent:
        """
        Create the summariser agent.

        Returns:
            Agent: A configured planning agent
        """
        summariser = Agent(
            config=self.agents_config["summariser"],
            llm=self.llm,
            verbose=self.verbose,
        )
        summariser.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Summariser Agent",
            workflow_name="Research",
            llm_name=summariser.llm.model,
        )
        return summariser

    @task
    def summarise_task(self) -> Task:
        """
        Define the summarise task.

        Returns:
            Task: A configured research task
        """
        return Task(
            config=self.tasks_config["summarise_task"],
        )

    @crew
    def crew(self) -> Crew:
        """
        Create and configure the summariser crew.

        Returns:
            Crew: A configured crew with summarising capabilities
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=self.verbose,
        )
