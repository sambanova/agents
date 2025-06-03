import os
from typing import Any, Dict

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

# Tools
from crewai_tools import SerperDevTool

# For logging user <-> agent conversation in Redis (optional but recommended)
from agents.components.crewai_llm import CustomLLM
from agents.utils.agent_thought import RedisConversationLogger


@CrewBase
class ConvoNewsletterCrew:
    """
    Conversation-focused Newsletter crew that can generate outlines,
    write newsletters, and edit them. Refactored to accept user/conversation
    parameters and includes SerperDevTool for search capabilities.
    """

    agents_config: Dict[str, Any]  # e.g. loaded from your config/agents.yaml
    tasks_config: Dict[str, Any]  # e.g. loaded from your config/tasks.yaml

    def __init__(
        self,
        sambanova_key: str = None,
        serper_key: str = None,
        user_id: str = None,
        conversation_id: str = None,
    ) -> None:
        """
        Initialize the ConvoNewsletterCrew with API keys and user metadata.
        """
        super().__init__()
        # In an actual implementation, you'd load config from your local YAML files:
        # self.agents_config = ...
        # self.tasks_config = ...
        # For brevity, we assume they're read automatically or injected.

        # Initialize your LLM with the SambaNova key
        self.llm = CustomLLM(
            model="sambanova/Meta-Llama-3.1-70B-Instruct",
            temperature=0.0,
            max_tokens=8192,
            api_key=sambanova_key,
        )

        # Optionally set the SERPER key in environment so the tool can read it
        if serper_key:
            os.environ["SERPER_API_KEY"] = serper_key

        self.user_id = user_id
        # We will store conversation logs under "run_id" or "conversation_id" for clarity
        self.conversation_id = conversation_id
        self.serper_key = serper_key

        # Agents and tasks will be appended when decorated with @agent, @task
        self.agents_config = {}
        self.tasks_config = {}
        self.agents = []
        self.tasks = []

    @agent
    def synthesizer(self) -> Agent:
        """
        Synthesizes a subject line and outline for the newsletter.
        """
        # Example logger usage
        synthesizer = Agent(
            config=self.agents_config.get("synthesizer", {}),
            verbose=True,
            llm=self.llm,
            tools=[SerperDevTool()],
        )
        synthesizer.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.conversation_id,
            agent_name="Synthesizer Agent",
            workflow_name="Newsletter",
            llm_name=synthesizer.llm.model,
        )
        return synthesizer

    @agent
    def newsletter_writer(self) -> Agent:
        """
        Writes the newsletter draft, includes a WordCounterTool and SerperDevTool.
        """
        # Attach a search tool (SerperDevTool) plus your WordCounterTool

        serper_tool = SerperDevTool()
        newsletter_writer = Agent(
            config=self.agents_config.get("newsletter_writer", {}),
            tools=[serper_tool],
            verbose=True,
            llm=self.llm,
        )
        newsletter_writer.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.conversation_id,
            agent_name="Newsletter Writer Agent",
            workflow_name="Newsletter",
            llm_name=newsletter_writer.llm.model,
        )
        return newsletter_writer

    @agent
    def newsletter_editor(self) -> Agent:
        """
        Edits and polishes the newsletter draft.
        """
        newsletter_editor = Agent(
            config=self.agents_config.get("newsletter_editor", {}),
            verbose=True,
            llm=self.llm,
        )
        newsletter_editor.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.conversation_id,
            agent_name="Newsletter Editor Agent",
            workflow_name="Newsletter",
            llm_name=newsletter_editor.llm.model,
        )

        return newsletter_editor

    @task
    def generate_outline_task(self) -> Task:
        return Task(
            config=self.tasks_config.get("generate_outline_task", {}), llm=self.llm
        )

    @task
    def write_newsletter_task(self) -> Task:
        return Task(
            config=self.tasks_config.get("write_newsletter_task", {}),
            output_file="newsletter_draft.md",
            llm=self.llm,
            context=[self.generate_outline_task()],
        )

    @task
    def review_newsletter_task(self) -> Task:
        return Task(
            config=self.tasks_config.get("review_newsletter_task", {}),
            output_file="final_newsletter.md",
            llm=self.llm,
            context=[self.write_newsletter_task()],
        )

    @crew
    def crew(self) -> Crew:
        """
        Creates the conversation-enabled Newsletter crew.
        We pass `chat_llm=self.llm` so that it can be used in a normal chat flow.
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            chat_llm=self.llm,  # <--- This is critical for "chat" use
        )
