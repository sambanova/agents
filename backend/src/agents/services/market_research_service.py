import os
import json
import sys

# Ensure parent directory is in the path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils.envutils import EnvUtils
# Instead of SerperDevTool, we now use our ExaDevTool
from tools.exa_dev_tool import ExaDevTool

class MarketResearchService:
    def __init__(self):
        self.search_tool = ExaDevTool()

    def generate_market_research(
        self,
        industry: str = None,
        product: str = None
    ) -> str:
        """
        Generate a *basic* "market research" summary using Exa-based search results.
        
        :param industry: Target industry (e.g. "hardware", "retail", etc.)
        :param product: Specific product or technology (e.g. "AI in supply chain")
        :return: A textual summary of market insights from Exa's search results.
        """
        # Construct search query
        search_query = self._build_search_query(industry, product)
        
        # Use the ExaDevTool to run the search
        exa_response = self.search_tool.run(
            search_query=search_query,
            search_type="neural",        # or "auto"/"keyword" etc.
            text=True,
            use_autoprompt=True,
            num_results=20,
            api_key=self.api_key
        )

        # Build a summary from the results
        summary_text = self._create_summary_from_exa_results(exa_response, search_query)
        
        return summary_text

    def _build_search_query(self, industry: str, product: str) -> str:
        """
        Construct a search query from (industry, product).
        If none is provided, default to 'technology innovation'.
        """
        query_parts = []
        if product:
            query_parts.append(product)
        if industry:
            query_parts.append(industry)
        
        return " ".join(query_parts) if query_parts else "technology innovation"

    def _create_summary_from_exa_results(self, exa_results: dict, query: str) -> str:
        """
        Build a text-based summary from Exa's results. 
        We read the 'results' array from the exa_results dict.
        """
        results = exa_results.get("results", [])
        summary_lines = [f"Market Research Summary for: {query}\n"]

        for idx, res in enumerate(results, start=1):
            title = res.get("title", "")
            url = res.get("url", "")
            # We can use 'text' or 'highlights' from Exa. We'll pick 'text'.
            snippet = res.get("text", "")[:200]  # short snippet
            summary_lines.append(f"{idx}. {title}\n   Link: {url}\n   Snippet: {snippet}\n")

        return "\n".join(summary_lines)

def generate_market_research(
    industry: str = None,
    product: str = None
) -> str:
    """
    Convenience function if you want to call the service directly 
    without constructing MarketResearchService yourself.
    """
    service = MarketResearchService()
    return service.generate_market_research(industry, product)

def main():
    # Quick CLI test
    industry = input("Enter the target industry (optional): ").strip() or None
    product = input("Enter the specific product/technology (optional): ").strip() or None
    
    service = MarketResearchService()
    insights = service.generate_market_research(industry, product)
    
    print("\n--- Market Research Insights ---")
    print(insights)

if __name__ == "__main__":
    main()
