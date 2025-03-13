# file: tools/exa_dev_tool.py

import os
import json
import time
import requests
from typing import Any, Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from utils.logging import logger
class ExaDevToolSchema(BaseModel):
    search_query: str = Field(..., description="Search query for Exa semantic search.")
    search_type: str = Field(default="auto", description="Search type: 'auto', 'neural', etc.")
    category: str = Field(default="company", description="Search category")
    num_results: int = Field(default=20, description="Number of results to retrieve")
    text: bool = Field(default=True, description="Whether to retrieve the 'text' field")
    summary: bool = Field(default=True, description="Whether to retrieve the 'summary' field")
    livecrawl: str = Field(default="always", description="Use 'always' for fresh results")

class ExaDevTool(BaseTool):
    name: str = "Exa Search Tool"
    description: str = "Use Exa to perform semantic search with raw HTTP POST. Returns JSON with title, url, text, summary, etc."
    args_schema = ExaDevToolSchema

    def _run(self, **kwargs: Any) -> Any:
        search_query = kwargs.get("search_query")
        search_type = kwargs.get("search_type", "auto")
        category = kwargs.get("category", "company")
        num_results = kwargs.get("num_results", 20)
        #text = kwargs.get("text", True)
        summary = kwargs.get("summary", True)
        livecrawl = kwargs.get("livecrawl", "always")
        api_key = kwargs.get("api_key")

        payload = {
            "query": search_query,
            "type": search_type,
            "category": category,
            "numResults": num_results,
            "contents": {
                #"text": text,
                "highlights": {},
                "summary": summary,
                "livecrawl": livecrawl
            }
        }


        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": api_key
        }

        try:
            start_time = time.time()
            response = requests.post("https://api.exa.ai/search", headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            elapsed_time = time.time() - start_time
            if elapsed_time > 10:
                logger.warning(f"Exa Dev Tool took {elapsed_time:.2f} seconds to complete search for query: {search_query}")
            else:
                logger.info(f"Exa Dev Tool took {elapsed_time:.2f} seconds to complete search for query: {search_query}")
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Exa search request failed: {e}"}
        except json.JSONDecodeError:
            return {"error": "Could not decode JSON from Exa response."}