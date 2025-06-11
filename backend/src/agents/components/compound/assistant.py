# TODO: Remove this
from datetime import datetime
from agents.components.compound.datatypes import Assistant


def get_assistant(user_id: str, llm_type: str):
    assistant = Assistant(
        config={
            "configurable": {
                "type==default/system_message": f"You are a helpful assistant. Today's date is {datetime.now().strftime('%Y-%m-%d')}",
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
    return assistant
