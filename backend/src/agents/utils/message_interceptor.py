import time
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable, RunnableLambda


class MessageInterceptor:
    def __init__(self):
        self.captured_messages = []

    def capture_and_pass(self, message):
        """Capture the message with timing data and pass it through"""
        if isinstance(message, AIMessage):
            # Get end time when message is received
            end_time = time.time()

            # Extract duration from response_metadata (already tracked by invoke_llm_with_tracking)
            duration = 0
            if hasattr(message, 'response_metadata') and message.response_metadata:
                usage = message.response_metadata.get('usage', {})
                duration = usage.get('total_latency', 0)

            # Calculate start time from end_time - duration
            # This is accurate because duration comes from actual timing in invoke_llm_with_tracking
            start_time = end_time - duration if duration > 0 else end_time

            # Add timing data to additional_kwargs
            if not hasattr(message, 'additional_kwargs') or message.additional_kwargs is None:
                message.additional_kwargs = {}

            message.additional_kwargs['timing'] = {
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'captured_at': end_time,  # When interceptor captured it
            }

            self.captured_messages.append(message)
        return message
