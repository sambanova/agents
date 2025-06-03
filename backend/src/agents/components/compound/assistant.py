# TODO: Remove this
from agents.components.compound.datatypes import Assistant


def get_assistant(user_id: str, llm_type: str):
    assistant = Assistant(
        config={
            "configurable": {
                f"type==default/system_message": "You are a helpful assistant.",
                f"type==default/tools": [
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
                f"type==default/llm_type": llm_type,
            }
        },
    )
    return assistant
