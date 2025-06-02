from crewai.tools import BaseTool
from typing import Optional
from pydantic import Field, ConfigDict
import sys
import os

# Ensure parent directory is in the path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now referencing the updated MarketResearchService that uses Exa
from services.market_research_service import MarketResearchService

class MarketResearchTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str = "Market Research Intelligence"
    description: str = (
        "Conduct a basic web search-based market research using Exa. "
        "Can search by industry, product, or specific technology. "
        "Returns a textual summary of market insights."
    )

    service: MarketResearchService = Field(default_factory=MarketResearchService)
    api_key: str = Field(default="")

    def _run(
        self,
        industry: Optional[str] = None,
        product: Optional[str] = None
    ) -> str:
        """
        Execute the market research intelligence search (Exa-based).
        
        Args:
            industry (str, optional): The target industry
            product (str, optional): Specific product or technology
        
        Returns:
            str: Market research insights
        """
        if not industry and not product:
            raise ValueError(
                "At least one search parameter must be provided (industry or product)."
            )
        
        self.service.api_key = self.api_key

        return self.service.generate_market_research(
            industry=industry,
            product=product
        )

if __name__ == "__main__":
    tool = MarketResearchTool(api_key="your_api_key_here")
    
    test_cases = [
        {
            "industry": "hardware",
            "product": "AI in edge computing"
        }
    ]
    
    for case in test_cases:
        print(f"\nTesting with parameters: {case}")
        result = tool._run(**case)
        print("Market Research Results:")
        print(result)
