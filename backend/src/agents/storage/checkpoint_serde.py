"""Hardened serializer and saver for the LangGraph Redis checkpointer."""

from __future__ import annotations

import dataclasses
import importlib
import re
from enum import Enum
from inspect import isclass
from typing import Any

import structlog
from langchain_core.load.load import Reviver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.checkpoint.redis.jsonplus_redis import JsonPlusRedisSerializer
from pydantic import BaseModel
from pydantic.v1 import BaseModel as BaseModelV1

logger = structlog.get_logger(__name__)

_IP_TYPES = ("IPv4Address", "IPv4Interface", "IPv4Network", "IPv6Address", "IPv6Interface", "IPv6Network")

# Constructors JsonPlusSerializer._default emits for stdlib types -> allowed methods.
_STDLIB_CONSTRUCTORS: dict[tuple[str, ...], set] = {
    ("pathlib", "Path"): {None},
    ("re", "compile"): {None},
    ("uuid", "UUID"): {None},
    ("decimal", "Decimal"): {None},
    ("builtins", "set"): {None},
    ("builtins", "frozenset"): {None},
    ("collections", "deque"): {None},
    ("builtins", "bytes"): {"fromhex"},
    ("builtins", "bytearray"): {"fromhex"},
    ("datetime", "datetime"): {"fromisoformat"},
    ("datetime", "timezone"): {None},
    ("datetime", "timedelta"): {None},
    ("datetime", "date"): {None},
    ("datetime", "time"): {None},
    ("zoneinfo", "ZoneInfo"): {None},
    **{("ipaddress", name): {None} for name in _IP_TYPES},
}

# Packages whose model classes (pydantic, dataclass, enum, namedtuple) may be revived.
_MODEL_PACKAGES = {"agents", "langchain_core", "langgraph"}
_MODEL_METHODS = {None, "model_construct", "construct"}
_FRAMEWORK_CLASSES = {("langgraph", "types", "Send")}

_SENSITIVE_METADATA_KEY = re.compile(r"api_?key|secret|password|token", re.IGNORECASE)

_LC_REVIVER = Reviver(secrets_from_env=False)


def _is_allowed_constructor(value: dict[str, Any]) -> bool:
    ident = value.get("id")
    if not isinstance(ident, list) or len(ident) < 2 or not all(isinstance(p, str) for p in ident):
        return False
    method = value.get("method")
    methods = method if isinstance(method, list) else [method]
    key = tuple(ident)

    if key in _STDLIB_CONSTRUCTORS:
        return all(m in _STDLIB_CONSTRUCTORS[key] for m in methods)

    if ident[0] not in _MODEL_PACKAGES or not all(m in _MODEL_METHODS for m in methods):
        return False
    try:
        cls = getattr(importlib.import_module(".".join(ident[:-1])), ident[-1])
    except Exception:
        return False
    if not isclass(cls):
        return False
    return (
        issubclass(cls, (BaseModel, BaseModelV1, Enum, tuple))
        or dataclasses.is_dataclass(cls)
        or key in _FRAMEWORK_CLASSES
    )


class SafeJsonPlusRedisSerializer(JsonPlusRedisSerializer):
    """Only revives the constructor forms the serializer itself produces."""

    def _reviver(self, value: dict[str, Any]) -> Any:
        if value.get("lc", None) == 2 and value.get("type", None) == "constructor":
            if not _is_allowed_constructor(value):
                logger.warning("Refused to revive checkpoint object", id=value.get("id"))
                return value
            return super()._reviver(value)
        return _LC_REVIVER(value)


def strip_sensitive_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Drop credential-like keys that LangGraph copies from ``configurable``."""
    return {k: v for k, v in metadata.items() if not _SENSITIVE_METADATA_KEY.search(k)}


class SafeAsyncRedisSaver(AsyncRedisSaver):
    """AsyncRedisSaver with the hardened serializer and no credentials in metadata."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.serde = SafeJsonPlusRedisSerializer()

    def _dump_metadata(self, metadata: dict[str, Any]) -> str:
        return super()._dump_metadata(strip_sensitive_metadata(metadata))
