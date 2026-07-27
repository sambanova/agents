import json
from typing import Any, Dict, Optional

from agents.services.company_research_service import CompanyIntelligenceService
from crewai.tools import BaseTool
from pydantic import ConfigDict, Field


class CompanyIntelligenceTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "Company Intelligence Search"
    description: str = (
        "Search for company intelligence using Exa-based searching. "
        "Can search by industry, company name, product, company stage, geography, and funding stage. "
        "Returns detailed company information including description, headquarters, funding status, etc."
    )
    service: CompanyIntelligenceService = Field(
        default_factory=CompanyIntelligenceService
    )

    api_key: str = Field(default="")

    def _run(
        self,
        industry: Optional[str] = None,
        company_stage: Optional[str] = None,
        geography: Optional[str] = None,
        funding_stage: Optional[str] = None,
        product: Optional[str] = None,
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
                "company_name": None,  # Not used currently
                "product": product,  # We pass product directly
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
                "raw_result": result,
            }
