"""
Helper functions for loading and processing prompt templates in the SWE components.
"""

import os
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate


def markdown_to_prompt_template(template_path: str) -> ChatPromptTemplate:
    """
    Load a markdown file and convert it to a ChatPromptTemplate.
    
    This function loads a markdown file containing a prompt template and
    converts it to a LangChain ChatPromptTemplate that can be used with LLMs.
    
    Args:
        template_path: Path to the markdown file (relative to the backend/src directory)
        
    Returns:
        ChatPromptTemplate object ready for use with LLMs
        
    Raises:
        FileNotFoundError: If the template file cannot be found
        ValueError: If the template file is empty or invalid
    """
    # Get the src directory by going up from this file's location
    # This file is in: src/agents/components/swe/helpers/prompts.py
    # So we need to go up 4 levels to get to src
    src_dir = Path(__file__).parent.parent.parent.parent.parent
    full_path = src_dir / template_path
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            template_content = f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt template file not found: {full_path}")
    
    if not template_content:
        raise ValueError(f"Prompt template file is empty: {full_path}")
    
    # Create a simple human message template from the markdown content
    # The content is expected to contain template variables in {variable} format
    return ChatPromptTemplate.from_messages([
        ("human", template_content)
    ])


def load_prompt_template(template_name: str, component: str = "swe") -> ChatPromptTemplate:
    """
    Convenience function to load prompt templates for SWE components.
    
    Args:
        template_name: Name of the template file (without .md extension)
        component: Component name (default: "swe")
        
    Returns:
        ChatPromptTemplate object
    """
    template_path = f"agents/components/{component}/prompts/{template_name}.md"
    return markdown_to_prompt_template(template_path)


def get_template_variables(template: ChatPromptTemplate) -> list:
    """
    Extract the input variables from a prompt template.
    
    Args:
        template: ChatPromptTemplate to analyze
        
    Returns:
        List of variable names used in the template
    """
    return template.input_variables


