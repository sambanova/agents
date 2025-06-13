from datetime import datetime
from agents.components.compound.datatypes import Assistant
from agents.tools.langgraph_tools import RETRIEVAL_DESCRIPTION


def get_assistant(user_id: str, llm_type: str, doc_ids: tuple, api_key: str):
    assistant = Assistant(
        config={
            "configurable": {
                "type==default/tools": [
                    {
                        "type": "arxiv",
                        "config": {},
                    },
                    {
                        "type": "search_tavily",
                        "config": {},
                    },
                    {
                        "type": "search_tavily_answer",
                        "config": {},
                    },
                    {
                        "type": "daytona",
                        "config": {"user_id": user_id},
                    },
                    {
                        "type": "wikipedia",
                        "config": {},
                    },
                ],
                "type==default/llm_type": llm_type,
            }
        },
    )

    if doc_ids:
        assistant.config["configurable"]["type==default/tools"].append(
            {
                "type": "retrieval",
                "config": {
                    "user_id": user_id,
                    "doc_ids": doc_ids,
                    "description": RETRIEVAL_DESCRIPTION,
                    "api_key": api_key,
                },
            }
        )
        assistant.config["configurable"][
            "type==default/system_message"
        ] = f"You are a helpful assistant. Today's date is {datetime.now().strftime('%Y-%m-%d')}. {len(doc_ids)} documents are available to you for retrieval."
    else:
        assistant.config["configurable"][
            "type==default/system_message"
        ] = f"You are a helpful assistant. Today's date is {datetime.now().strftime('%Y-%m-%d')}"
    return assistant
