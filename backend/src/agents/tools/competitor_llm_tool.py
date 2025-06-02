import os
import json
import requests
from typing import Type, List
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class CompetitorLLMInput(BaseModel):
    """Input schema for CompetitorLLMTool."""
    company_name: str = Field(..., description="Name of the company to find competitors for")

class CompetitorLLMTool(BaseTool):
    name: str = "competitor llm tool"
    description: str = "Calls SambaNova ChatCompletion to guess up to 3 US-traded competitor tickers for a given company name. Returns tickers like ['MSFT','GOOGL']."
    args_schema: Type[BaseModel] = CompetitorLLMInput
    sambanova_api_key: str = Field(default="")
    

    def _run(self, company_name: str) -> List[str]:
        """
        Calls SambaNova ChatCompletion to guess up to 3 US-traded competitor tickers
        for the given company_name. Returns a list of strings like ["MSFT","GOOGL"].
        """

        if not company_name:
            return []

        # Build request
        system_msg = (
            "You are a financial expert with deep knowledge of US stock tickers. "
            "Given a company name, list 1-3 top competitor TICKERS, e.g. AAPL, MSFT, etc. "
            "Return them as a JSON array of uppercase strings: [\"TICKER\", ...]."
        )
        user_msg = f"""
        Company name: "{company_name}"

        Please respond with ONLY valid JSON, e.g.:
        ["MSFT","GOOGL","AMD"]
        If uncertain, return an empty array: []
        """

        payload = {
            "model": "Meta-Llama-3.1-8B-Instruct",
            "messages": [
                {"role":"system","content":system_msg},
                {"role":"user","content":user_msg}
            ],
            "temperature": 0.0,
            "stream": False
        }
        headers = {
            "Authorization": f"Bearer {self.sambanova_api_key}",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post("https://api.sambanova.ai/v1/chat/completions",
                                headers=headers,
                                data=json.dumps(payload),
                                timeout=30)
            resp.raise_for_status()
            jr = resp.json()
            if "choices" not in jr or len(jr["choices"])==0:
                return []
            content = jr["choices"][0]["message"]["content"].strip()
            content = content.replace("```json","").replace("```","").strip()

            # Attempt to parse as JSON array
            arr = json.loads(content)
            # Ensure it's a list of strings
            final_list = []
            for item in arr:
                if isinstance(item, str):
                    final_list.append(item.upper())
            return final_list[:3]
        except Exception as e:
            print(f"[competitor_llm_tool] LLM call error: {e}")
            return []
