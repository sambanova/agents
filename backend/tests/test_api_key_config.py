import unittest

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableLambda

from agents.components.compound.util import extract_api_key, secret_api_key


class CaptureMetadata(BaseCallbackHandler):
    def __init__(self):
        self.metadata = []

    def on_chain_start(self, serialized, inputs, *, metadata=None, **kwargs):
        self.metadata.append(dict(metadata or {}))


class TestSecretApiKey(unittest.TestCase):
    def test_key_is_readable_but_not_in_run_metadata(self):
        seen = []
        capture = CaptureMetadata()
        runnable = RunnableLambda(lambda x, config: seen.append(extract_api_key(config)) or x)
        runnable.invoke(
            1,
            {"configurable": {"api_key": secret_api_key("raw-key")}, "callbacks": [capture]},
        )
        self.assertEqual(seen, ["raw-key"])
        self.assertTrue(capture.metadata)
        self.assertNotIn("raw-key", str(capture.metadata))

    def test_plain_string_still_supported(self):
        self.assertEqual(extract_api_key({"configurable": {"api_key": "k"}}), "k")

    def test_empty_values_pass_through(self):
        self.assertEqual(secret_api_key(""), "")
        self.assertIsNone(secret_api_key(None))


if __name__ == "__main__":
    unittest.main()
