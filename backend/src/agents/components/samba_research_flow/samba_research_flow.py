#!/usr/bin/env python
"""
Main module for the Educational Content Generation Flow.

This module implements a workflow for generating educational content using
multiple specialized AI crews. It handles the coordination between research
and content creation phases.
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Tuple

from agents.components.samba_research_flow.crews.edu_content_writer.edu_content_writer_crew import (
    EduContentWriterCrew,
)
from agents.components.samba_research_flow.crews.edu_doc_summariser.edu_doc_summariser_crew import (
    EduDocSummariserCrew,
)
from agents.components.samba_research_flow.crews.edu_research.edu_research_crew import (
    EducationalPlan,
    EduResearchCrew,
)
from crewai.flow.flow import Flow, listen, start
from dotenv import load_dotenv


class SambaResearchFlow(Flow):
    """
    Reseach and Educational content generation workflow manager.

    This class orchestrates the process of researching topics and generating
    educational content through multiple specialized AI crews.

    Attributes:
        input_variables (dict): Configuration for the educational content generation
        research_crew (Crew): Crew responsible for research phase
        content_crew (Crew): Crew responsible for content creation phase
    """

    input_variables = Dict[str, Any]

    def __init__(
        self,
        llm_api_key: str,
        provider: str,
        serper_key: str = None,
        user_id: str = None,
        run_id: str = None,
        docs_included: bool = False,
        verbose: bool = True,
    ) -> None:
        """Initialize the educational flow with research and content creation crews."""
        super().__init__()
        self.summariser = EduDocSummariserCrew(
            llm_api_key=llm_api_key,
            provider=provider,
            user_id=user_id,
            run_id=run_id,
            verbose=verbose,
        ).crew()
        self.research_crew = EduResearchCrew(
            llm_api_key=llm_api_key,
            provider=provider,
            serper_key=serper_key,
            user_id=user_id,
            run_id=run_id,
            verbose=verbose,
        ).crew()
        self.content_crew = EduContentWriterCrew(
            llm_api_key=llm_api_key,
            provider=provider,
            user_id=user_id,
            run_id=run_id,
            verbose=verbose,
        ).crew()
        self.docs_included = docs_included
        self.summariser_usage = None
        self.research_usage = None
        self.content_usage = None

    async def run_research_and_summarize(self) -> Tuple[EducationalPlan, Any]:
        """
        Run research and document summarization in parallel.

        Returns:
            Tuple[EducationalPlan, Any]: Research plan and document summaries
        """
        # Create tasks for parallel execution
        research_task = asyncio.create_task(
            asyncio.to_thread(lambda: self.research_crew.kickoff(self.input_variables))
        )

        summary_task = None
        if self.docs_included:
            summary_task = asyncio.create_task(
                asyncio.to_thread(lambda: self.summariser.kickoff(self.input_variables))
            )

        # Wait for research task and optionally summary task
        research_result = await research_task
        self.research_usage = dict(research_result.token_usage)
        summary_result = None
        if summary_task:
            summary_result = await summary_task
            self.summariser_usage = dict(summary_result.token_usage)
            summary_result = summary_result.raw
        else:
            self.summariser_usage = None

        return research_result.pydantic, summary_result

    @start()
    async def generate_reseached_content(self) -> Tuple[EducationalPlan, Any]:
        """
        Begin the content generation process with parallel research and summarization.

        Returns:
            Tuple[EducationalPlan, Any]: Research plan and document summaries
        """
        return await self.run_research_and_summarize()

    @listen(generate_reseached_content)
    def generate_educational_content(
        self, results: Tuple[EducationalPlan, Any]
    ) -> List[Dict]:
        """
        Generate educational content based on the research plan and summaries.

        Args:
            results (Tuple[EducationalPlan, Any]): The research plan and document summaries

        Returns:
            List[Dict]: List of sections with their plan and generated content.
        """
        plan, summaries = results
        sections_with_content = []
        self.content_usage = []

        for section in plan.sections:
            # Create section dict with all original fields
            section_dict = section.model_dump()

            # Generate content for this section
            writer_inputs = self.input_variables.copy()
            writer_inputs["section"] = section.model_dump_json()

            if summaries:
                writer_inputs["docs"] = summaries
            else:
                writer_inputs["docs"] = "None"

            # Add generated content to the section dict

            content_result = self.content_crew.kickoff(writer_inputs)
            self.content_usage.append(dict(content_result.token_usage))
            section_dict["generated_content"] = content_result.raw

            sections_with_content.append(section_dict)

        return sections_with_content


def kickoff() -> None:
    """Initialize and start the educational content generation process."""
    edu_flow = SambaResearchFlow()
    edu_flow.kickoff()


def plot() -> None:
    """Generate and display a visualization of the flow structure."""
    edu_flow = SambaResearchFlow()
    edu_flow.plot()


def test_flow() -> List[Dict]:
    """
    Helper function to test the educational flow with predefined inputs.
    Returns the generated content sections.
    """
    edu_flow = SambaResearchFlow(sambanova_key="fake", serper_key="fake")

    # Convert focus_areas list to comma-separated string
    focus_areas = ", ".join(
        ["technical comparison", "performance characteristics", "use cases"]
    )

    edu_flow.input_variables = {
        "topic": "SRAM and High Bandwidth Memory",
        "audience_level": "intermediate",
        "additional_context": focus_areas,  # Now a string instead of a dict
    }

    return edu_flow.kickoff()
