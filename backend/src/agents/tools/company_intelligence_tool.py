# file: tools/company_intelligence_tool.py

from crewai.tools import BaseTool
from typing import Dict, Any, Optional
from pydantic import Field, ConfigDict
import sys
import os
import json

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now referencing the new Exa-based service
from services.company_research_service import CompanyIntelligenceService

class CompanyIntelligenceTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str = "Company Intelligence Search"
    description: str = (
        "Search for company intelligence using Exa-based searching. "
        "Can search by industry, company name, product, company stage, geography, and funding stage. "
        "Returns detailed company information including description, headquarters, funding status, etc."
    )
    service: CompanyIntelligenceService = Field(default_factory=CompanyIntelligenceService)

    api_key: str = Field(default="")

    def _run(
        self, 
        industry: Optional[str] = None,
        company_stage: Optional[str] = None,
        geography: Optional[str] = None,
        funding_stage: Optional[str] = None,
        product: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute the company intelligence search using Exa.
        """
        try:
            # Accept empty or None for the optional fields
            valid_stages = ["startup", "smb", "enterprise", "growing", "none", ""]
            if company_stage and company_stage.lower() not in valid_stages:
                raise ValueError(
                    f"Invalid company_stage. Must be one of {valid_stages}."
                )

            # Prepare parameters
            clean_params = {
                "industry": industry,
                "company_stage": (company_stage.lower() if company_stage else None),
                "geography": geography,
                "funding_stage": funding_stage,
                "company_name": None,   # Not used currently
                "product": product      # We pass product directly
            }

            # At least one field must not be all None/empty
            non_empty = [v for k, v in clean_params.items() if v]
            if not non_empty:
                raise ValueError(
                    "At least one search parameter must be provided "
                    "(industry, company_stage, geography, funding_stage, or product)."
                )

            # Make the service call
            self.service.api_key = self.api_key
            result_json_string = self.service.get_company_intelligence(**clean_params)
            return json.loads(result_json_string)

        except Exception as e:
            return {"error": str(e)}

    def _format_result(self, result: str) -> Dict[str, Any]:
        """
        If needed, parse string to dict or do final formatting.
        """
        try:
            if isinstance(result, str):
                return json.loads(result)
            return result
        except Exception as ex:
            return {
                "error": f"Error formatting result: {str(ex)}",
                "raw_result": result
            }


if __name__ == "__main__":
    # Example usage:
    tool = CompanyIntelligenceTool()

    # For a quick test:
    test_params = {
        "industry": "hardware",
        "company_stage": "startup",
        "geography": "bay area",
        "funding_stage": None
    }
    results = tool._run(**test_params)
    print(json.dumps(results, indent=2))