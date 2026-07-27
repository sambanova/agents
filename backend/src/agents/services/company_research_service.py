# file: services/company_research_service.py

import os
import json
import sys
from datetime import datetime, timezone

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from agents.utils.envutils import EnvUtils
from agents.tools.exa_dev_tool import ExaDevTool

class CompanyIntelligenceService:
    """
    Step 1: Perform aggregator search for user criteria 
    Return the raw Exa results.
    """
    def __init__(self):
        self.env_utils = EnvUtils()
        self.search_tool = ExaDevTool()
    

    def get_company_intelligence(
        self,
        industry=None,
        company_name=None,
        product=None,
        company_stage=None,
        geography=None,
        funding_stage=None
    ) -> str:
        """
        Return the raw Exa search JSON, with text+summary for each result,
        then return as a JSON string.
        """
        exa_results = self.get_raw_search_results(
            industry=industry,
            company_name=company_name,
            product=product,
            company_stage=company_stage,
            geography=geography,
            funding_stage=funding_stage
        )
        return json.dumps(exa_results, indent=2)

    def get_raw_search_results(
        self,
        industry=None,
        company_name=None,
        product=None,
        company_stage=None,
        geography=None,
        funding_stage=None
    ) -> dict:
        query = self._build_search_query(industry, company_name, product, company_stage, geography, funding_stage)
        exa_results = self.search_tool.run(
            search_query=query,
            search_type="auto",
            category="company",
            num_results=20,
            text=True,
            summary=True,
            livecrawl="always",
            api_key=self.api_key
        )
        if not isinstance(exa_results, dict) or "results" not in exa_results:
            return {
                "companies": [],
                "search_criteria": {
                    "industry": industry or "",
                    "company_name": company_name or "",
                    "product": product or "",
                    "company_stage": company_stage or "",
                    "geography": geography or "",
                    "funding_stage": funding_stage or ""
                },
                "total_companies": 0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # Reformat exa_results into the same shape
        # We'll put final data under "companies"
        # each item might have "title, url, text, summary"
        companies = []
        for r in exa_results.get("results", []):
            c = {
                "name": r.get("title","Unknown"),
                "website": r.get("url",""),
                # put aggregator text in "description"
                "description": (r.get("summary") or "") + "\n" + (r.get("text") or "")
            }
            companies.append(c)

        output = {
            "companies": companies,
            "search_criteria": {
                "industry": industry or "",
                "company_name": company_name or "",
                "product": product or "",
                "company_stage": company_stage or "",
                "geography": geography or "",
                "funding_stage": funding_stage or ""
            },
            "total_companies": len(companies),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        return output

    def _build_search_query(self, industry, company_name, product, company_stage, geography, funding_stage):
        parts = []
        if company_name: parts.append(company_name)
        if product: parts.append(product)
        if industry: parts.append(f"{industry} industry")
        if company_stage: parts.append(f"{company_stage} stage")
        if geography: parts.append(f"in {geography}")
        if funding_stage: parts.append(f"{funding_stage} funding")

        if not parts:
            return "technology companies"
        return " ".join(parts)