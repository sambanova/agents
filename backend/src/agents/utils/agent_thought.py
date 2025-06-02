import redis
import json
import time
from typing import Any
import os
from crewai.agents.parser import AgentFinish, AgentAction

class RedisConversationLogger:
    """
    Publishes each agent step to Redis pub/sub for real-time streaming.
    Reads REDIS_HOST/REDIS_PORT from environment to handle local vs. Docker.
    """
    def __init__(
        self,
        user_id="",
        run_id="",
        agent_name="",
        workflow_name="",
        llm_name="",
        redis_client=None,
        message_id=None,
    ):
        # Read from env or default
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))

        try:
            if redis_client:
                self.r = redis_client
            else:
                self.r = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=0,
                    decode_responses=True
                )
            self.r.ping()
            print(f"[RedisConversationLogger] Connected to Redis at {redis_host}:{redis_port} for {agent_name}")
        except redis.ConnectionError as e:
            print(f"[RedisConversationLogger] Redis connection failed: {e}")

        # Ensure proper string conversion and handle potential JSON objects
        if isinstance(user_id, (dict, list)):
            try:
                self.user_id = json.dumps(user_id)
            except:
                self.user_id = str(user_id)
        else:
            self.user_id = str(user_id) if user_id else ""

        self.run_id = str(run_id) if run_id else ""
        self.agent_name = agent_name
        self.workflow_name = workflow_name
        # Split llm_name into provider/model if "/" present
        if "/" in llm_name:
            self.llm_provider, self.llm_name = llm_name.split("/", 1)
        else:
            self.llm_provider = ""
            self.llm_name = llm_name
        self.init_timestamp = time.time()
        self._message_id = str(message_id) if message_id else None

    @property
    def message_id(self):
        return self._message_id

    @message_id.setter
    def message_id(self, value):
        self._message_id = str(value) if value else None

    def update_message_id(self, message_id):
        """Update the message_id for the next set of logs."""
        self.message_id = message_id

    # TODO: log llm usage
    def log_success_event(
                        kwargs,
                        response_obj,
                        start_time,
                        end_time,
                    ):
        pass

    def __call__(self, output: Any):
        try:
            if hasattr(output, 'text'):
                if isinstance(output, AgentAction):
                    task = output.tool
                else:
                    task = ""

                message = {
                    "user_id": self.user_id,
                    "run_id": self.run_id,
                    "agent_name": self.agent_name,
                    "text": output.text,
                    "timestamp": time.time(),
                    "message_id": self.message_id,
                    "metadata": {
                        "workflow_name": self.workflow_name,
                        "agent_name": self.agent_name,
                        "duration": time.time() - self.init_timestamp,
                        "llm_name": self.llm_name,
                        "llm_provider": self.llm_provider,
                        "task": task,
                    },
                }
                self.init_timestamp = time.time()
                channel = f"agent_thoughts:{self.user_id}:{self.run_id}"
                self.r.publish(channel, json.dumps(message))
        except Exception as e:
            print(f"Error publishing to Redis: {e}")
            print(f"Message attempted: {message if 'message' in locals() else 'No message created'}")
