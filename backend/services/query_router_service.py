import asyncio
from datetime import datetime
import time
from typing import Dict, Any, Optional
import json
from fastapi import WebSocket
import aiohttp
from pydantic import BaseModel
import redis
import requests
from fastapi.websockets import WebSocketState
import re  # Added for quick pattern matching to detect multiple companies

from api.websocket_interface import WebSocketInterface
from utils.json_utils import extract_json_from_string
from config.model_registry import model_registry
from utils.logging import logger

class QueryType(BaseModel):
    # Possible types: "sales_leads", "educational_content", "financial_analysis", or "deep_research"
    type: str
    parameters: Dict[str, Any]

# Keep this for backwards compatibility
class QueryRouterService:
    def __init__(self, sambanova_key: str):
        self.sambanova_key = sambanova_key
        self.api_url = "https://api.sambanova.ai/v1/chat/completions"
        
        # Expanded / refined keywords for educational content (including some "report", "compare", etc.)
        self.edu_keywords = [
            "explain", "guide", "learn", "teach", "understand", "what is",
            "how does", "tutorial", "course", "education", "training",
            "concepts", "fundamentals", "basics", "advanced", "intermediate",
            "beginner", "introduction", "deep dive", "overview", "study",
            "technology", "architecture", "design", "implementation",
            "comparison", "compare", "comparing", "performance", "methodology",
            "framework", "system", "protocol", "algorithm", "mechanism",
            "theory", "principle", "structure", "process",
            # Newly added cues for research/educational style requests:
            "report", "tell me about", "describe", "differences", "similarities"
        ]
        
        # Sales leads keywords
        self.sales_keywords = [
            "find", "search", "companies", "startups", "leads", "vendors",
            "identify", "discover", "list", "funding", "funded", "investors",
            "market research", "competitors", "industry", "geography",
            "series", "seed", "venture", "investment", "firm", "corporation",
            "business", "enterprise", "provider", "supplier", "manufacturer"
        ]

        # Financial keywords - removing generic "analysis" to avoid over-triggering
        self.financial_keywords = [
            "stock",
            "fundamental analysis", 
            "technical analysis", 
            "price target", 
            "investment strategy", 
            "ticker",
            "financial analysis",
            "ratios", 
            "eps", 
            "balance sheet", 
            "income statement",
            "market cap",
            "valuation"
        ]

        # Additional phrases for override
        self.override_phrases = [
            "fundamental analysis",
            "technical analysis",
            "fundamental & technical analysis"
        ]

        # A small set of known big company names to help push "analysis" queries to financial
        self.known_big_companies = [
            "google", "amazon", "apple", "tesla", "microsoft", "netflix",
            "meta", "alphabet", "nvidia", "amd", "intel"
        ]
        # Tickers for some known big companies
        self.known_tickers = [
            "goog", "googl", "amzn", "aapl", "tsla", "msft",
            "nflx", "meta", "nvda", "amd", "intc"
        ]

    def _get_default_response(self, detected_type: str) -> str:
        """Return a default structured JSON string based on the detected type."""
        if detected_type == "educational_content":
            return json.dumps({
                "type": "educational_content",
                "parameters": {
                    "topic": "",
                    "audience_level": "intermediate",
                    "focus_areas": ["key concepts", "practical applications"]
                }
            })
        elif detected_type == "financial_analysis":
            return json.dumps({
                "type": "financial_analysis",
                "parameters": {
                    "query_text": "",
                    "ticker": "",
                    "company_name": ""
                }
            })
        elif detected_type == "deep_research":
            return json.dumps({
                "type": "deep_research",
                "parameters": {
                    "deep_research_topic": ""
                }
            })
        # else, fallback => sales
        return json.dumps({
            "type": "sales_leads",
            "parameters": {
                "industry": "",
                "company_stage": "",
                "geography": "",
                "funding_stage": "",
                "product": ""
            }
        })

    def _normalize_educational_params(self, params: Dict) -> Dict:
        """Normalize educational content parameters with safe defaults."""
        focus_areas = params.get("focus_areas", [])
        if isinstance(focus_areas, str):
            focus_areas = [area.strip() for area in focus_areas.split(",")]
        elif not focus_areas:
            focus_areas = ["key concepts", "practical applications"]

        valid_levels = ["beginner", "intermediate", "advanced"]
        audience_level = params.get("audience_level", "intermediate").lower()
        if audience_level not in valid_levels:
            audience_level = "intermediate"

        return {
            "topic": params.get("topic", ""),
            "audience_level": audience_level,
            "focus_areas": focus_areas
        }

    def _normalize_sales_params(self, params: Dict) -> Dict:
        """Normalize sales leads parameters with safe defaults."""
        return {
            "industry": params.get("industry", ""),
            "company_stage": params.get("company_stage", ""),
            "geography": params.get("geography", ""),
            "funding_stage": params.get("funding_stage", ""),
            "product": params.get("product", "")
        }

    def _normalize_financial_params(self, params: Dict) -> Dict:
        """Normalize financial analysis parameters with safe defaults."""
        return {
            "query_text": params.get("query_text",""),
            "ticker": params.get("ticker",""),
            "company_name": params.get("company_name","")
        }

    def _normalize_deep_research_params(self, params: Dict) -> Dict:
        """Normalize deep research parameters with safe defaults."""
        return {
            "deep_research_topic": params.get("deep_research_topic", "")
        }

    def _detect_query_type(self, query: str) -> str:
        """
        Score-based approach for edu, sales, finance, plus
        special checks for multi-company or IPO/S-1 => 'deep_research'.
        """
        query_lower = query.lower()

        # Quick checks for S-1 or IPO => deep_research
        if "s-1" in query_lower or "s1" in query_lower or "ipo" in query_lower:
            return "deep_research"

        # Additional pattern checks for "S&P" (multiple companies in an index)
        if "s&p" in query_lower or "s & p" in query_lower:
            return "deep_research"

        # Check if there's an obvious multi-company or compare scenario => deep_research
        multi_keywords = ["compare", " vs ", " between "]
        if any(mk in query_lower for mk in multi_keywords):
            return "deep_research"

        # Also check if the user specifically requests "X companies" => deep_research
        num_companies_match = re.search(r'(\d+)\s+companies', query_lower)
        if num_companies_match:
            return "deep_research"

        # Quick check if the user explicitly references multiple known big companies/tickers
        count_known_cos = sum(1 for co in self.known_big_companies + self.known_tickers if co in query_lower)
        # If more than 1 recognized => deep_research
        if count_known_cos > 1:
            return "deep_research"

        # 1) If user explicitly says "fundamental analysis" or "technical analysis" => finance
        if "fundamental analysis" in query_lower or "technical analysis" in query_lower:
            return "financial_analysis"

        # 2) Tally normal keywords (but remove "analysis" from direct financial scoring)
        edu_score = sum(1 for keyword in self.edu_keywords if keyword in query_lower)
        sales_score = sum(1 for keyword in self.sales_keywords if keyword in query_lower)
        fin_score = sum(1 for keyword in self.financial_keywords if keyword in query_lower)

        # 3) Special logic for the words 'analysis' or 'analyze' 
        #    => check if they appear alongside strong finance signals
        if ("analysis" in query_lower or "analyze" in query_lower):
            # If user also mentions known big cos, tickers, or finance words like 'stock'
            # or explicit finance terms, treat as finance:
            if any(big_co in query_lower for big_co in self.known_big_companies + self.known_tickers):
                fin_score += 5  # strongly finance
            elif any(x in query_lower for x in ["stock", "price target", "investment strategy"]):
                fin_score += 5  # strongly finance
            # If none of these appear, do NOT boost finance

        # 4) Decide based on highest score
        if fin_score > edu_score and fin_score > sales_score:
            return "financial_analysis"
        if edu_score >= sales_score:
            return "educational_content"
        return "sales_leads"

    def _final_override(self, user_query: str, chosen_type: str) -> str:
        """
        If user query explicitly mentions certain override phrases 
        (like 'fundamental analysis' or 'technical analysis'),
        we force 'financial_analysis'.

        Also, if we've chosen 'financial_analysis' but we detect
        it's either an S-1 scenario, multiple companies, or references
        to S&P, revert to 'deep_research'.
        """
        qlower = user_query.lower()

        # Always override with fundamental/technical analysis if found
        for phrase in self.override_phrases:
            if phrase in qlower:
                return "financial_analysis"

        # Additional logic: if chosen type is financial_analysis,
        # but there's an S-1/IPO or multiple companies, or user
        # is comparing, or referencing S&P, override to deep_research
        if chosen_type == "financial_analysis":
            if "s-1" in qlower or "s1" in qlower or "ipo" in qlower:
                return "deep_research"
            if "s&p" in qlower or "s & p" in qlower:
                return "deep_research"

            multi_keywords = ["compare", " vs ", " between "]
            if any(mk in qlower for mk in multi_keywords):
                return "deep_research"

            # Also check if user says "X companies"
            num_companies_match = re.search(r'(\d+)\s+companies', qlower)
            if num_companies_match:
                return "deep_research"

            # If multiple known big cos are recognized
            count_known_cos = sum(1 for co in self.known_big_companies + self.known_tickers if co in qlower)
            if count_known_cos > 1:
                return "deep_research"

        return chosen_type

    def _call_llm(self, system_message: str, user_message: str) -> str:
        """
        Make an API call to SambaNova's LLM, returning raw string content.
        """
        headers = {
            "Authorization": f"Bearer {self.sambanova_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "Meta-Llama-3.1-8B-Instruct",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.0,
            "stream": False
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            json_response = response.json()
            
            if "choices" not in json_response or len(json_response["choices"]) == 0:
                return self._get_default_response(self._detect_query_type(user_message))

            content = json_response["choices"][0]["message"]["content"].strip()
            return content.replace("```json", "").replace("```", "").strip()
            
        except Exception as e:
            print(f"Error calling LLM: {str(e)}")
            return self._get_default_response(self._detect_query_type(user_message))

    def route_query(self, query: str) -> QueryType:
        """
        Main routing method:
          1) Detect type using _detect_query_type
          2) Call LLM with few-shot system prompt
          3) Parse or fall back to a default if LLM fails
          4) Normalize parameters
          5) Final override check
        """
        detected_type = self._detect_query_type(query)
        
        system_message = f"""
        You are a query routing expert that categorizes queries and extracts structured information.
        Always return a valid JSON object with 'type' and 'parameters'.

        We have four possible types: 'sales_leads', 'educational_content', 'financial_analysis', or 'deep_research'.

        Rules:
        1. For 'educational_content':
           - Extract the FULL topic from the query
           - Do NOT truncate or summarize the topic
           - If multiple concepts are present, keep them in 'topic'
        2. For 'sales_leads': 
           - Extract specific industry, location, or other business parameters if any
        3. For 'financial_analysis': 
           - Provide 'query_text' (the user's full finance question)
           - Provide 'ticker' if recognized
           - Provide 'company_name' if recognized
           - This route is only for single public companies. 
             If the query references multiple companies, or a not-yet-public company (S-1), revert to 'deep_research'.
        4. For 'deep_research':
           - Provide 'deep_research_topic' (the user's full query for in-depth or multi-company research)

        Examples:

        Query: "Dark Matter, Black Holes and Quantum Physics"
        {{
          "type": "educational_content",
          "parameters": {{
            "topic": "Dark Matter, Black Holes and Quantum Physics",
            "audience_level": "intermediate",
            "focus_areas": ["key concepts", "theoretical foundations", "current research"]
          }}
        }}

        Query: "Explain the relationship between quantum entanglement and teleportation"
        {{
          "type": "educational_content",
          "parameters": {{
            "topic": "relationship between quantum entanglement and teleportation",
            "audience_level": "intermediate",
            "focus_areas": ["key concepts", "theoretical principles", "practical applications"]
          }}
        }}

        Query: "Find AI startups in Boston"
        {{
          "type": "sales_leads",
          "parameters": {{
            "industry": "AI",
            "company_stage": "startup",
            "geography": "Boston",
            "funding_stage": "",
            "product": ""
          }}
        }}

        Query: "Analyze Google"
        {{
          "type": "financial_analysis",
          "parameters": {{
            "query_text": "Analyze Google",
            "ticker": "GOOGL",
            "company_name": "Google"
          }}
        }}

        Query: "Perform a fundamental analysis on Tesla stock"
        {{
          "type": "financial_analysis",
          "parameters": {{
            "query_text": "Perform a fundamental analysis on Tesla stock",
            "ticker": "TSLA",
            "company_name": "Tesla"
          }}
        }}

        Query: "Compare cloud revenue growth between Microsoft Azure and AWS only"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Compare cloud revenue growth between Microsoft Azure and AWS only"
          }}
        }}

        Query: "Analyze the stock market sell off today and tell me three S&P companies I should not invest in based on their stock price"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Analyze the stock market sell off today and tell me three S&P companies I should not invest in based on their stock price"
          }}
        }}

        Query: "Analyze Coreweave and the S-1"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Analyze Coreweave and the S-1"
          }}
        }}

        Query: "Ai chip companies based in geneva"
        {{
          "type": "sales_leads",
          "parameters": {{
            "industry": "AI chip",
            "company_stage": "",
            "geography": "Geneva",
            "funding_stage": "",
            "product": ""
          }}
        }}

        Query: "Quantum computing and qubits"
        {{
          "type": "educational_content",
          "parameters": {{
            "topic": "Quantum computing and qubits",
            "audience_level": "intermediate",
            "focus_areas": ["foundational principles", "recent advances"]
          }}
        }}

        User query: "{query}"
        Initial type detection suggests: {detected_type}

        Return ONLY JSON with 'type' and 'parameters'.
        """

        user_message = "Please classify and extract parameters."

        try:
            llm_result_str = self._call_llm(system_message, user_message)
            parsed_result = json.loads(llm_result_str)

            # If LLM didn't provide "type", fallback
            if "type" not in parsed_result:
                parsed_result["type"] = detected_type

            # Param normalization
            if parsed_result["type"] == "educational_content":
                parsed_result["parameters"] = self._normalize_educational_params(
                    parsed_result.get("parameters", {})
                )
            elif parsed_result["type"] == "financial_analysis":
                parsed_result["parameters"] = self._normalize_financial_params(
                    parsed_result.get("parameters", {})
                )
            elif parsed_result["type"] == "deep_research":
                parsed_result["parameters"] = self._normalize_deep_research_params(
                    parsed_result.get("parameters", {})
                )
            else:
                parsed_result["parameters"] = self._normalize_sales_params(
                    parsed_result.get("parameters", {})
                )

            # Final override check
            final_type = self._final_override(query, parsed_result["type"])
            parsed_result["type"] = final_type

            return QueryType(**parsed_result)
            
        except json.JSONDecodeError as e:
            print(f"[route_query] JSON decode error: {str(e)}")
            # fallback if LLM fails
            fallback_json = self._get_default_response(detected_type)
            fallback_dict = json.loads(fallback_json)
            # also final override
            fallback_dict["type"] = self._final_override(query, fallback_dict["type"])
            return QueryType(**fallback_dict)


class QueryRouterServiceChat:

    def __init__(
        self,
        llm_api_key: str,
        provider: str,
        model_name: str,
        message_id: str,
        websocket_manager: WebSocketInterface,
        redis_client: Optional[redis.Redis] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ):
        self.llm_api_key = llm_api_key
        self.provider = provider
        self.model_name = self._resolve_model_name(model_name, provider)
        self.websocket_manager = websocket_manager
        self.redis_client = redis_client
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.message_id = message_id

        # Expanded / refined keywords for educational content (including some "report", "compare", etc.)
        self.edu_keywords = [
            "explain", "guide", "learn", "teach", "understand", "what is",
            "how does", "tutorial", "course", "education", "training",
            "concepts", "fundamentals", "basics", "advanced", "intermediate",
            "beginner", "introduction", "deep dive", "overview", "study",
            "technology", "architecture", "design", "implementation",
            "comparison", "compare", "comparing", "performance", "methodology",
            "framework", "system", "protocol", "algorithm", "mechanism",
            "theory", "principle", "structure", "process",
            # Newly added cues for research/educational style requests:
            "report", "tell me about", "describe", "differences", "similarities"
        ]

        # Sales leads keywords
        self.sales_keywords = [
            "find", "search", "companies", "startups", "leads", "vendors",
            "identify", "discover", "list", "funding", "funded", "investors",
            "market research", "competitors", "industry", "geography",
            "series", "seed", "venture", "investment", "firm", "corporation",
            "business", "enterprise", "provider", "supplier", "manufacturer"
        ]

        # Financial keywords - removing generic "analysis" to avoid over-triggering
        self.financial_keywords = [
            "stock",
            "fundamental analysis", 
            "technical analysis", 
            "price target", 
            "investment strategy", 
            "ticker",
            "financial analysis",
            "ratios", 
            "eps", 
            "balance sheet", 
            "income statement",
            "market cap",
            "valuation"
        ]

        # Additional phrases for override
        self.override_phrases = [
            "fundamental analysis",
            "technical analysis",
            "fundamental & technical analysis"
        ]

        # A small set of known big company names to help push "analysis" queries to financial
        self.known_big_companies = [
            "google", "amazon", "apple", "tesla", "microsoft", "netflix",
            "meta", "alphabet", "nvidia", "amd", "intel"
        ]
        # Tickers for some known big companies
        self.known_tickers = [
            "goog", "googl", "amzn", "aapl", "tsla", "msft",
            "nflx", "meta", "nvda", "amd", "intc"
        ]

    @staticmethod
    def _resolve_model_name(model_name: str, provider: str) -> str:
        """
        Resolve the model name to the correct model name.
        """
        if provider == "fireworks" and model_name == "llama-3.1-tulu-3-405b":
            return "llama-3.1-405b"
        return model_name

    def _detect_query_type(self, query: str) -> str:
        """
        Score-based approach for edu, sales, finance, with some logic 
        for multi-company or specialized triggers => deep_research,
        but this short version is typically overshadowed by the LLM route in practice.
        """
        query_lower = query.lower()

        # If user explicitly says "fundamental analysis" or "technical analysis" => finance
        if "fundamental analysis" in query_lower or "technical analysis" in query_lower:
            return "financial_analysis"

        # Tally normal keywords
        edu_score = sum(1 for keyword in self.edu_keywords if keyword in query_lower)
        sales_score = sum(1 for keyword in self.sales_keywords if keyword in query_lower)
        fin_score = sum(1 for keyword in self.financial_keywords if keyword in query_lower)

        # Additional check if "analysis"/"analyze" plus big co/ticker => finance
        if ("analysis" in query_lower or "analyze" in query_lower):
            if any(big_co in query_lower for big_co in self.known_big_companies + self.known_tickers):
                fin_score += 5
            elif any(x in query_lower for x in ["stock", "price target", "investment strategy"]):
                fin_score += 5

        # Basic fallback
        if fin_score > edu_score and fin_score > sales_score:
            return "financial_analysis"
        if edu_score >= sales_score:
            return "educational_content"
        return "sales_leads"

    async def _call_llm(self, system_message: str, user_message: str) -> str:
        """
        Make an API call to SambaNova's LLM, returning raw string content.
        """
        headers = {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model_registry.get_model_info(model_key=self.model_name, provider=self.provider)["model"],
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.0,
            "stream": True
        }

        # If we have a websocket, send the response to the client
        planner_metadata = {
            "llm_name": payload["model"],
            "llm_provider": self.provider,
            "task": "planning",
        }   
        planner_event = {
            "event": "planner",
            "data": json.dumps({"metadata": planner_metadata}),
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "timestamp": datetime.now().isoformat(),
        }
        await self.websocket_manager.send_message(self.user_id, self.conversation_id, planner_event)

        api_url = model_registry.get_model_info(model_key=self.model_name, provider=self.provider)["long_url"]

        logger.info(logger.format_message(f"{self.user_id}:{self.conversation_id}", f"QueryRouterServiceChat calling {api_url}"))

        start_time = time.time()
        async with aiohttp.ClientSession() as session:
            accumulated_content = ""
            async with session.post(api_url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        try:
                            json_response = json.loads(line.removeprefix('data: '))
                            if json_response.get("choices") and json_response["choices"][0].get("delta", {}).get("content"):
                                content = json_response["choices"][0]["delta"]["content"]
                                accumulated_content += content
                                # Send streaming update
                                stream_data = {
                                    "event": "planner_chunk",
                                    "data": content,
                                    "message_id": self.message_id,
                                }
                                await self.websocket_manager.send_message(self.user_id, self.conversation_id, stream_data)
                        except json.JSONDecodeError:
                            continue

        end_time = time.time()
        processing_time = end_time - start_time
        if processing_time > 10:
            logger.warning(logger.format_message(f"{self.user_id}:{self.conversation_id}", f"QueryRouterServiceChat processing time: {processing_time:.2f} seconds"))
        else:
            logger.info(logger.format_message(f"{self.user_id}:{self.conversation_id}", f"QueryRouterServiceChat processing time: {processing_time:.2f} seconds"))

        parsed_content = extract_json_from_string(accumulated_content)
        planner_metadata["duration"] = processing_time

        # Send final message
        final_message_data = {
            "event": "planner",
            "data": json.dumps({"response": parsed_content, "metadata": planner_metadata}),
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "timestamp": datetime.now().isoformat(),
        }
        message_key = f"messages:{self.user_id}:{self.conversation_id}"
        self.redis_client.rpush(message_key, json.dumps(final_message_data), self.user_id)
        await self.websocket_manager.send_message(self.user_id, self.conversation_id, final_message_data)
        return parsed_content

    def _normalize_educational_params(self, params: Dict) -> Dict:
        """Normalize educational content parameters with safe defaults."""
        focus_areas = params.get("focus_areas", [])
        if isinstance(focus_areas, str):
            focus_areas = [area.strip() for area in focus_areas.split(",")]
        elif not focus_areas:
            focus_areas = ["key concepts", "practical applications"]

        valid_levels = ["beginner", "intermediate", "advanced"]
        audience_level = params.get("audience_level", "intermediate").lower()
        if audience_level not in valid_levels:
            audience_level = "intermediate"

        return {
            "topic": params.get("topic", ""),
            "audience_level": audience_level,
            "focus_areas": focus_areas
        }

    def _normalize_sales_params(self, params: Dict) -> Dict:
        """Normalize sales leads parameters with safe defaults."""
        return {
            "industry": params.get("industry", ""),
            "company_stage": params.get("company_stage", ""),
            "geography": params.get("geography", ""),
            "funding_stage": params.get("funding_stage", ""),
            "product": params.get("product", "")
        }

    def _normalize_financial_params(self, params: Dict) -> Dict:
        """Normalize financial analysis parameters with safe defaults."""
        return {
            "query_text": params.get("query_text",""),
            "ticker": params.get("ticker",""),
            "company_name": params.get("company_name","")
        }

    def _normalize_deep_research_params(self, params: Dict) -> Dict:
        """Normalize deep research parameters with safe defaults."""
        return {
            "deep_research_topic": params.get("deep_research_topic", "")
        }

    def _normalize_user_proxy_params(self, params: Dict) -> Dict:
        """Normalize user proxy parameters with safe defaults."""
        return {
            "agent_question": params.get("agent_question", "")
        }

    def _normalize_assistant_params(self, params: Dict) -> Dict:
        """Normalize assistant parameters with safe defaults."""
        return {
            "query": params.get("query", "")
        }

    def _final_override(self, user_query: str, chosen_type: str) -> str:
        """
        If user query explicitly mentions certain override phrases 
        (like 'fundamental analysis' or 'technical analysis'),
        we force 'financial_analysis'.
        """
        qlower = user_query.lower()

        for phrase in self.override_phrases:
            if phrase in qlower:
                return "financial_analysis"

        return chosen_type

    async def route_query(self, query: str, context_summary: str = "", num_docs: int = 0) -> QueryType:
        """
        Main routing method:
          1) Detect type using _detect_query_type
          2) Call LLM with few-shot system prompt
          3) Parse or fall back to a default if LLM fails
          4) Normalize parameters
          5) Final override check
        """

        system_message = f"""
        You are a query routing expert that categorizes queries and extracts structured information.
        To decide on the route take into account the user's query and the context summary.

        User query: "{query}"

        The user has uploaded {num_docs} documents that are available to the agents. 
        
        Context summary: "{context_summary}"

        Follow these steps:
        1. Identify what specific information the user is requesting, if the user asked a specific question in the context and the question was not answered, the user is likely to be referring to that question.
        2. Use the context to resolve any ambiguity in the query. Note that the context might only provide partial information, you can still use it to formulate a specific query.
        3. Try to formulate a specific query based on the information provided in the context.
        4. Generate the appropriate JSON response using the following agents:

        "type": "assistant",
        "description": "Use this agent if,
        - The query does not fit into other specific categories
        - The query is general and does not specify a destination or service
        - The query is a factual question or quick information about a company person or product
        - The user is asking about current affairs
        - The user is asking a question about uploaded documents and the documents are uploaded.",
        "examples": "'What is the weather in Tokyo?', 'What is the capital of France?' What is Tesla's stock price today? What is the latest news on Apple?",

        Query: "What is the weather in Tokyo?"
        {{
          "type": "assistant",
          "parameters": {{
            "query": "What is the weather in Tokyo?"
          }}
        }}

        Query: "Who are SambaNova?"
        {{
            "type": "assistant",
            "parameters": {{
                "query": "Who are SambaNova?"
            }}
        }}

        "type": "financial_analysis"
        "description": "Handles complex financial analysis queries ONLY, including company reports, company financials, financial statements, and market trends. This is NOT for quick information or factual answers about STOCK PRICES. For this agent to work you need at least one ticker or company name, and it must be a single public company. If the query is a factual answer or quick information about a company person or product, ALWAYS use the assistant agent instead. This is a specialized agent for complex financial analysis and NEVER use this agent for quick info or if the user references multiple companies or IPO/S-1.",
        "examples": "Tell me about Apple's financials, What's the financial statement of Tesla?, Market trends in the tech sector for a single company?"

        Query: "Analyze Google"
        {{
          "type": "financial_analysis",
          "parameters": {{
            "query_text": "Analyze Google",
            "ticker": "GOOGL",
            "company_name": "Google"
          }}
        }}

        Query: "Perform a fundamental analysis on Tesla stock"
        {{
          "type": "financial_analysis",
          "parameters": {{
            "query_text": "Perform a fundamental analysis on Tesla stock",
            "ticker": "TSLA",
            "company_name": "Tesla"
          }}
        }}

        "type": "sales_leads",
        "description": "Handles sales lead generation queries, including industry, location, and product information."
        "examples": "Find me sales leads in the tech sector, What are the sales leads in the US?, Sales leads in the retail industry?"

        Query: "Find AI startups in Boston"
        {{
          "type": "sales_leads",
          "parameters": {{
            "industry": "AI",
            "company_stage": "startup",
            "geography": "Boston",
            "funding_stage": "",
            "product": ""
          }}
        }}

        Query: "Ai chip companies based in geneva"
        {{
          "type": "sales_leads",
          "parameters": {{
            "industry": "AI chip",
            "company_stage": "",
            "geography": "Geneva",
            "funding_stage": "",
            "product": ""
          }}
        }}

        "type": "deep_research",
        "description": "Handles educational or multi-step research style queries (including multi-company financial comparisons or S-1/IPO references).",
        "examples": "Generate a thorough technical report on quantum entanglement with references, Provide a multi-section explanation with research steps, Compare the financials of multiple companies, Analyze an S-1 or IPO scenario, or referencing an index with multiple companies (like S&P).",

        Query: "Write me a report on the future of AI"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Write me a report on the future of AI"
          }}
        }}

        Query: "Dark Matter, Black Holes and Quantum Physics"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Dark Matter, Black Holes and Quantum Physics"
          }}
        }}

        Query: "Explain the relationship between quantum entanglement and teleportation"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "relationship between quantum entanglement and teleportation"
          }}
        }}

        Query: "Prepare a syllabus for a course on flowers"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Prepare a syllabus for a course on flowers"
          }}
        }}

        Query: "Analyze Coreweave and the S-1"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Analyze Coreweave and the S-1"
          }}
        }}

        Query: "Compare cloud revenue growth between Microsoft Azure and AWS only"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Compare cloud revenue growth between Microsoft Azure and AWS only"
          }}
        }}

        Query: "Analyze the stock market sell off today and tell me three S&P companies I should not invest in based on their stock price"
        {{
          "type": "deep_research",
          "parameters": {{
            "deep_research_topic": "Analyze the stock market sell off today and tell me three S&P companies I should not invest in based on their stock price"
          }}
        }}

        "type": "user_proxy",
        "description": "This is NOT an agent but a direct response back to the user. Use this type when:
        - Handling queries about conversation history (e.g., 'What did I ask before?', 'What was my last query?')
        - Responding to vague or unclear queries
        - Addressing content already discussed in the context
        - Responding to greetings, thanks, or casual conversation
        - Providing follow-up information

        When using this type, the response goes directly back to the user without invoking a specialized agent. If information is available in the context, provide it directly.",
        "examples": "Hello, How are you?, Thanks for the information, Can you tell me more about that?, What do you think?",

        Query: "Tell me about this company?"
        {{
          "type": "user_proxy",
          "parameters": {{
            "agent_question": "Please clarify the name of the company."
          }}
        }}

        Rules:
        1. For 'sales_leads': 
           - Extract specific industry, location, or other business parameters if any
        2. For 'financial_analysis': 
           - Provide 'query_text' (the user's full finance question)
           - Provide 'ticker' if recognized
           - Provide 'company_name' if recognized
           - Only valid for single public companies
        3. For 'deep_research':
           - Provide 'deep_research_topic' (the user's full research query)
           - Use if multiple companies or S-1/IPO references or indexes like S&P
        4. For 'assistant':
           - Provide 'query' (the user's full query)
        5. For 'user_proxy':
           - Provide 'agent_question' (the question that requires a response from the user)

        Return ONLY JSON with 'type' and 'parameters'. Your job depends on it. 
        """

        user_message = "Please classify and extract parameters."

        parsed_result = await self._call_llm(system_message, user_message)

        # Param normalization
        if parsed_result["type"] == "educational_content":
            parsed_result["parameters"] = self._normalize_educational_params(
                parsed_result.get("parameters", {})
            )
        elif parsed_result["type"] == "financial_analysis":
            parsed_result["parameters"] = self._normalize_financial_params(
                parsed_result.get("parameters", {})
            )
        elif parsed_result["type"] == "deep_research":
            parsed_result["parameters"] = self._normalize_deep_research_params(
                parsed_result.get("parameters", {})
            )
        elif parsed_result["type"] == "user_proxy":
            parsed_result["parameters"] = self._normalize_user_proxy_params(
                parsed_result.get("parameters", {})
            )
        elif parsed_result["type"] == "assistant":
            parsed_result["parameters"] = self._normalize_assistant_params(
                parsed_result.get("parameters", {})
            )
        else:
            parsed_result["parameters"] = self._normalize_sales_params(
                parsed_result.get("parameters", {})
            )

        # Final override check
        final_type = self._final_override(query, parsed_result["type"])
        parsed_result["type"] = final_type

        return QueryType(**parsed_result)
