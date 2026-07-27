"""
Educational research crew module for content generation.

This module implements a specialized crew for conducting research and planning
educational content.
"""

import os
import sys
from typing import Any, Dict, List

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool
from pydantic import BaseModel
from agents.components.crewai_llm import CustomLLM
from agents.registry.model_registry import model_registry
from agents.utils.agent_thought import RedisConversationLogger

current_dir = os.getcwd()
repo_dir = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(repo_dir)


class Section(BaseModel):
    """
    Represents a section in the educational content plan.

    Attributes:
        title: The section title
        high_level_goal: The main objective of the section
        why_important: Explanation of the section's importance
        sources: List of reference sources
        content_outline: Structured outline of the section content
    """

    title: str
    high_level_goal: str
    why_important: str
    sources: List[str]
    content_outline: List[str]


class EducationalPlan(BaseModel):
    """
    Represents the complete educational content plan.

    Attributes:
        sections: List of content sections
    """

    sections: List[Section] = []


@CrewBase
class EduResearchCrew:
    """
    Educational research crew implementation.

    This crew is responsible for conducting research and planning educational
    content structure.
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
        serper_key: str = None,
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
        self.serper_key = serper_key
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
    def researcher(self) -> Agent:
        """
        Create the researcher agent.

        Returns:
            Agent: A configured research agent with search capabilities
        """
        # Temporarily set serper key in environment for this tool instance
        os.environ["SERPER_API_KEY"] = self.serper_key
        tool = SerperDevTool()

        researcher = Agent(
            config=self.agents_config["researcher"],
            llm=self.llm,
            verbose=self.verbose,
            tools=[tool],
        )
        researcher.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Researcher Agent",
            workflow_name="Research",
            llm_name=researcher.llm.model,
        )
        return researcher

    @agent
    def planner(self) -> Agent:
        """
        Create the planner agent.

        Returns:
            Agent: A configured planning agent
        """
        planner = Agent(
            config=self.agents_config["planner"],
            llm=self.llm,
            verbose=self.verbose,
        )
        planner.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Planner Agent",
            workflow_name="Research",
            llm_name=planner.llm.model,
        )
        return planner

    @task
    def research_task(self) -> Task:
        """
        Define the research task.

        Returns:
            Task: A configured research task
        """
        return Task(
            config=self.tasks_config["research_task"],
        )

    @task
    def planning_task(self) -> Task:
        """
        Define the planning task.

        Returns:
            Task: A configured planning task with EducationalPlan output
        """
        return Task(
            config=self.tasks_config["planning_task"], output_pydantic=EducationalPlan
        )

    @crew
    def crew(self) -> Crew:
        """
        Create and configure the research crew.

        Returns:
            Crew: A configured crew with research and planning capabilities
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=self.verbose,
        )
