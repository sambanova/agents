import datetime
import os
import unittest
import uuid
from collections import deque
from decimal import Decimal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Send

from agents.components.open_deep_research.state import Section
from agents.storage.checkpoint_serde import (
    SafeJsonPlusRedisSerializer,
    strip_sensitive_metadata,
)


CALLS = []


def record_call(*args):
    CALLS.append(args)


def roundtrip(obj):
    serde = SafeJsonPlusRedisSerializer()
    return serde.loads_typed(serde.dumps_typed(obj))


class TestSafeJsonPlusRedisSerializer(unittest.TestCase):
    def test_arbitrary_constructor_is_not_called(self):
        payload = {"lc": 2, "type": "constructor", "id": [__name__, "record_call"], "args": ["x"]}
        msg = AIMessage(content="", tool_calls=[{"name": "t", "args": {"q": payload}, "id": "1"}])
        out = roundtrip({"messages": [msg]})
        self.assertEqual(CALLS, [])
        self.assertEqual(out["messages"][0].tool_calls[0]["args"]["q"], payload)

    def test_disallowed_method_on_allowed_type_is_not_called(self):
        payload = {"lc": 2, "type": "constructor", "id": ["pathlib", "Path"], "method": "home"}
        self.assertEqual(roundtrip({"v": payload})["v"], payload)

    def test_env_secret_is_not_resolved(self):
        os.environ["CHECKPOINT_TEST_SECRET"] = "s3cret"
        payload = {"lc": 1, "type": "secret", "id": ["CHECKPOINT_TEST_SECRET"]}
        self.assertNotEqual(roundtrip({"v": payload})["v"], "s3cret")

    def test_supported_types_roundtrip(self):
        values = {
            "uuid": uuid.uuid4(),
            "dt": datetime.datetime(2026, 1, 2, 3, 4, 5),
            "date": datetime.date(2026, 1, 2),
            "delta": datetime.timedelta(seconds=5),
            "dec": Decimal("1.5"),
            "set": {1, 2},
            "deque": deque([1, 2]),
            "bytes": b"\x00\x01",
            "send": Send("node", {"a": 1}),
            "section": Section(name="n", description="d", research=True, content="c"),
            "messages": [HumanMessage(content="hi"), AIMessage(content="ok")],
        }
        out = roundtrip(values)
        for key in ("uuid", "dt", "date", "delta", "dec", "set", "deque", "bytes", "section"):
            self.assertEqual(out[key], values[key], key)
        self.assertEqual((out["send"].node, out["send"].arg), ("node", {"a": 1}))
        self.assertEqual([m.content for m in out["messages"]], ["hi", "ok"])


class TestStripSensitiveMetadata(unittest.TestCase):
    def test_credentials_are_dropped(self):
        metadata = {
            "source": "loop",
            "step": 1,
            "user_id": "u1",
            "thread_id": "t1",
            "api_key": "k",
            "apiKey": "k",
            "access_token": "k",
        }
        self.assertEqual(
            strip_sensitive_metadata(metadata),
            {"source": "loop", "step": 1, "user_id": "u1", "thread_id": "t1"},
        )


if __name__ == "__main__":
    unittest.main()
