from langchain_core.messages import AIMessage


class MessageInterceptor:
    def __init__(self):
        self.captured_messages = []

    def capture_and_pass(self, message):
        """Capture the message and pass it through"""
        if isinstance(message, AIMessage):
            self.captured_messages.append(message)
        return message
