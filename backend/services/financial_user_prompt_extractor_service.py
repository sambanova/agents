import os
import json
import requests
import re
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config.model_registry import model_registry
from utils.envutils import EnvUtils

class FinancialPromptExtractor:
    """
    We use a SambaNova ChatCompletion endpoint to parse user prompt, 
    extracting 'company_name' and 'ticker'. 
    If LLM fails, fallback to a naive regex approach.
    """

    def __init__(self, llm_api_key: str, provider: str):
        self.env_utils = EnvUtils()
        self.api_key = llm_api_key
        # Example model name 
        model_info = model_registry.get_model_info(model_key="llama-3.1-8b", provider=provider)
        self.model_name = model_info["model"]
        self.url = model_info["long_url"]

    def extract_info(self, prompt: str):
        """
        Return (ticker, company_name).
        We do:
          1) LLM approach to parse the prompt for JSON {company_name, ticker}
          2) If empty, fallback to naive regex
        """
        ticker_llm, company_llm = self._call_sambanova_llm(prompt)
        if ticker_llm or company_llm:
            return (ticker_llm, company_llm)

        # fallback
        ticker = ""
        company = ""

        # If user typed "Apple (AAPL)" or "Analyze AAPL"
        pattern_ticker = r"\b[A-Z]{1,5}\b"
        found = re.findall(pattern_ticker, prompt.upper())
        if found:
            ticker = found[0]

        # If there's something like "Apple (AAPL)"
        match = re.search(r"([A-Za-z\s]+)\s*\(([A-Za-z]{1,5})\)", prompt)
        if match:
            company = match.group(1).strip()

        return (ticker, company)

    def _call_sambanova_llm(self, prompt: str):
        """
        Attempt to parse user prompt for JSON with keys {company_name, ticker} 
        via SambaNova ChatCompletion.
        """
        system_msg = (
            "You are an information extraction system. "
            "Extract exactly two keys: 'company_name' and 'ticker' (in the format 'EXCHANGE:TICKER')."
            "For example: "
            "{{"
            "  'company_name': 'Apple',"
            "  'ticker': 'NASDAQ:AAPL'"
            "}}"
            "{{"
            "  'company_name': 'General Motors',"
            "  'ticker': 'NYSE:GM'"
            "}}"
        )
        user_msg = f"""
        The user's prompt is: "{prompt}"

        Return valid JSON:
        {{
          "company_name": "...",
          "ticker": "..."
        }}

        If you cannot find them, leave them blank. 
        No extra text, just JSON.
        """

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.0,
            "stream": False
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            resp = requests.post(self.url, headers=headers, data=json.dumps(payload), timeout=30)
            resp.raise_for_status()
            jr = resp.json()
            if "choices" not in jr or len(jr["choices"]) == 0:
                return ("","")
            content = jr["choices"][0]["message"]["content"].strip()
            content = content.replace("```json","").replace("```","").strip()
            parsed = json.loads(content)
            company_name = parsed.get("company_name","")
            ticker = parsed.get("ticker","").upper()
            return (ticker, company_name)
        except Exception as e:
            print(f"[FinancialPromptExtractor] LLM call failed: {e}")
            return ("","")
