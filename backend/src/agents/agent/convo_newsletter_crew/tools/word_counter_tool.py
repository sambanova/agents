from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class WordCounterInput(BaseModel):
    """Input schema for WordCounterTool."""

    text: str = Field(..., description="The text to count words in.")


class WordCounterTool(BaseTool):
    name: str = "Word Counter Tool"
    description: str = "Counts the number of words in a given text."
    args_schema: Type[BaseModel] = WordCounterInput

    def _run(self, text: str) -> int:
        # Count the number of words in the text
        word_count = len(text.split())
        return word_count


if __name__ == "__main__":
    # Test the WordCounterTool
    tool = WordCounterTool()

    test_text = "This is a sample text to count the number of words."

    # Run the tool and print the result
    result = tool._run(text=test_text)
    print("Word Count:", result)
