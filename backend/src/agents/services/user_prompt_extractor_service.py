import os
import json
import requests
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils.envutils import EnvUtils

class UserPromptExtractor:
    def __init__(self, sambanova_api_key: str):
        """
        This class uses a raw requests approach to call the SambaNova ChatCompletion endpoint,
        extracting user prompts into a structured JSON.

        Make sure your environment includes SAMBANOVA_API_KEY.
        """
        self.env_utils = EnvUtils()
        self.api_key = sambanova_api_key

        # We'll use the model name "Meta-Llama-3.1-8B-Instruct".
        self.model_name = "Meta-Llama-3.1-8B-Instruct"  
        self.url = "https://api.sambanova.ai/v1/chat/completions"

    def extract_lead_info(self, prompt: str) -> dict:
        """
        Make a POST request to the SambaNova ChatCompletion endpoint.
        We instruct the model to return JSON with keys:
          'industry', 'company_stage', 'geography', 'funding_stage', 'product'.
        """

        system_message = (
            "You are an expert system that extracts structured JSON "
            "from a user prompt. Always respond ONLY with valid JSON "
            "containing these keys: 'industry', 'company_stage', 'geography', "
            "'funding_stage', 'product'. If a key is not found, leave it empty."
        )
        user_message = f"""
        The user prompt is:
        {prompt}

        Extract the data into a JSON object with exactly these keys:
        industry, company_stage, geography, funding_stage, product.

        Example output:
        {{
          "industry": "",
          "company_stage": "",
          "geography": "",
          "funding_stage": "",
          "product": ""
        }}

        Return ONLY that JSON object, with no extra text or markdown.
        """

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.0
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            response = requests.post(
                self.url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"HTTP error calling SambaNova ChatCompletion: {e}")
            return {
                "industry": "",
                "company_stage": "",
                "geography": "",
                "funding_stage": "",
                "product": ""
            }

        try:
            json_response = response.json()
        except json.JSONDecodeError:
            print("Error: Could not parse JSON from SambaNova response.")
            return {
                "industry": "",
                "company_stage": "",
                "geography": "",
                "funding_stage": "",
                "product": ""
            }

        if "choices" not in json_response or len(json_response["choices"]) == 0:
            print("Error: No choices found in SambaNova response.")
            return {
                "industry": "",
                "company_stage": "",
                "geography": "",
                "funding_stage": "",
                "product": ""
            }

        content = json_response["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from LLM content: {content}")
            parsed = {}

        # Ensure the five keys exist
        for key in ["industry", "company_stage", "geography", "funding_stage", "product"]:
            if key not in parsed:
                parsed[key] = ""

        return parsed

def main():
    # Example usage
    # Provide your SambaNova key as needed
    fake_key = "YOUR_SAMBANOVA_KEY_HERE"
    extractor = UserPromptExtractor(fake_key)
    prompt = "Generate leads for AI Chip Startups in Silicon Valley"
    result = extractor.extract_lead_info(prompt)
    print("Extracted lead info:")
    print(result)

if __name__ == "__main__":
    main()
